import backtrader as bt

class EmaAtrStrategy(bt.Strategy):
    """
    Trend Following Strategy using EMA Crossover and ATR Trailing Stop Loss.
    """
    params = (
        # Instead of global fast/slow periods, we provide a dictionary of params per asset.
        # Format: {'BTC_USDT_4h': (fast, slow), 'ETH_USDT_4h': (fast, slow), ...}
        # If a symbol is not in the dict, it falls back to default_periods.
        ('asset_parameters', {}),
        ('default_periods', (50, 110)),

        ('atr_period', 14),
        ('atr_multiplier', 2.0),
        ('breakeven_atr_multiplier', 1.0), # Move SL to entry if profit hits 1.0x ATR
        ('risk_per_trade_pct', 0.95), # Will allocate this total percentage across all assets (Equal Weight Cash Allocation)
        ('printlog', True),           # Flag to toggle logging off during optimization
    )

    def __init__(self):
        # Create dictionaries to hold indicators and state per data feed
        self.inds = dict()
        self.orders = dict()
        self.stop_loss_prices = dict()
        self.entry_prices = dict()

        # Dictionaries to link 15m execution feeds to their respective 4h and 1d macro filters
        self.macro_4h_data = dict()
        self.macro_1d_data = dict()
        self.macro_1d_smas = dict()

        # 1. First Pass: Identify and store the 4h and 1d macro filter feeds
        for d in self.datas:
            base_symbol = d._name.replace('_4h', '').replace('_1d', '').replace('_15m', '')

            if d._name.endswith('_4h'):
                self.macro_4h_data[base_symbol] = d

                # We need the 4h EMAs for the filter condition (Fast EMA > Slow EMA)
                fast_p, slow_p = self.params.asset_parameters.get(d._name, self.params.default_periods)
                fast_ema = bt.indicators.ExponentialMovingAverage(d, period=fast_p)
                slow_ema = bt.indicators.ExponentialMovingAverage(d, period=slow_p)

                self.inds[d] = {
                    'fast_ema': fast_ema,
                    'slow_ema': slow_ema,
                    'slow_p': slow_p
                }

            elif d._name.endswith('_1d'):
                self.macro_1d_data[base_symbol] = d

                # Daily 200 SMA Filter
                sma200 = bt.indicators.SimpleMovingAverage(d, period=200)
                sma200.plotinfo.plot = False
                self.macro_1d_smas[base_symbol] = sma200

        # 2. Second Pass: Setup the 15m execution feeds
        for d in self.datas:
            if d._name.endswith('_15m'):
                base_symbol = d._name.replace('_15m', '')

                self.orders[d] = None
                self.stop_loss_prices[d] = None
                self.entry_prices[d] = None

                # Determine parameters for this specific 15m execution asset
                fast_p, slow_p = self.params.asset_parameters.get(d._name, self.params.default_periods)

                # Execution Indicators
                fast_ema = bt.indicators.ExponentialMovingAverage(d, period=fast_p)
                slow_ema = bt.indicators.ExponentialMovingAverage(d, period=slow_p)

                atr = bt.indicators.AverageTrueRange(d, period=self.params.atr_period)
                atr.plotinfo.plot = False

                crossover = bt.indicators.CrossOver(fast_ema, slow_ema)
                crossover.plotinfo.plot = False

                # Store in dict
                self.inds[d] = {
                    'fast_ema': fast_ema,
                    'slow_ema': slow_ema,
                    'atr': atr,
                    'crossover': crossover,
                    'slow_p': slow_p,
                    'base_symbol': base_symbol
                }

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        d = order.data

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED [{d._name}], Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm {order.executed.comm:.2f}', dt=d.datetime.date(0))

                # Capture execution price for breakeven calculation
                self.entry_prices[d] = order.executed.price

                # Initial Stop Loss
                atr = self.inds[d]['atr'][0]
                self.stop_loss_prices[d] = order.executed.price - (atr * self.params.atr_multiplier)
                self.log(f'INITIAL STOP LOSS SET [{d._name}]: {self.stop_loss_prices[d]:.2f}', dt=d.datetime.date(0))

            else:  # Sell
                self.log(f'SELL EXECUTED [{d._name}], Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm {order.executed.comm:.2f}', dt=d.datetime.date(0))
                self.stop_loss_prices[d] = None
                self.entry_prices[d] = None

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'Order Canceled/Margin/Rejected [{d._name}]', dt=d.datetime.date(0))

        # Reset order tracking for this data feed
        self.orders[d] = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return

        self.log(f'OPERATION PROFIT [{trade.data._name}], GROSS {trade.pnl:.2f}, NET {trade.pnlcomm:.2f}', dt=trade.data.datetime.date(0))

    def log(self, txt, dt=None, doprint=False):
        if self.params.printlog or doprint:
            dt = dt or self.datas[0].datetime.date(0)
            print('%s, %s' % (dt.isoformat(), txt))

    def next(self):
        # We ONLY execute trades on the 15m timeframes
        trading_assets = [d for d in self.datas if d._name.endswith('_15m')]
        num_assets = len(trading_assets)

        for d in trading_assets:
            ind = self.inds[d]
            base_symbol = ind['base_symbol']

            # Retrieve the macro filters
            data_4h = self.macro_4h_data.get(base_symbol)
            data_1d = self.macro_1d_data.get(base_symbol)
            sma_1d = self.macro_1d_smas.get(base_symbol)

            if data_4h is None or data_1d is None or sma_1d is None:
                continue

            # Ensure macro indicators are fully primed
            if len(data_4h) < self.inds[data_4h]['slow_p'] or len(sma_1d) < 200:
                continue

            # Skip if 15m execution data is not mature enough yet
            if len(d) < ind['slow_p']:
                continue

            pos = self.getposition(d)

            # If an order is already pending for this asset, skip
            if self.orders[d]:
                continue

            if not pos:
                # We are NOT in the market for this asset

                # Check execution trigger: 15m Fast EMA crosses above 15m Slow EMA
                if ind['crossover'][0] > 0:

                    # Check Macro Filter 1: 4h Fast EMA > 4h Slow EMA
                    # Use [-1] to avoid lookahead bias on the intraday evaluation
                    macro_4h_up = self.inds[data_4h]['fast_ema'][-1] > self.inds[data_4h]['slow_ema'][-1]

                    # Check Macro Filter 2: Daily Close > Daily 200 SMA
                    # Use [-1] to avoid lookahead bias on the intraday evaluation
                    macro_1d_up = data_1d.close[-1] > sma_1d[-1]

                    if macro_4h_up and macro_1d_up:
                        self.log(f'BUY CREATE [{d._name}], Price: {d.close[0]:.2f} (Macro Filters Passed: 4h UP, 1d UP)', dt=d.datetime.date(0))

                        # Portfolio Position Sizing (Equal Weight Cash Allocation)
                        # Distributed equally among the 4 execution assets (15m only)
                        total_equity = self.broker.getvalue()
                        allocation_per_asset = (total_equity * self.params.risk_per_trade_pct) / num_assets

                        # Ensure we have enough actual cash before buying
                        cash = self.broker.get_cash()
                        target_value = min(allocation_per_asset, cash)

                        size = target_value / d.close[0]

                        if size > 0:
                            self.orders[d] = self.buy(data=d, size=size)
                        else:
                            self.log(f'Not enough cash to buy [{d._name}]', dt=d.datetime.date(0))
                    else:
                        self.log(f'BUY BLOCKED [{d._name}] - 15m Crossover ignored due to Macro Filters (4h UP: {macro_4h_up}, 1d UP: {macro_1d_up})', dt=d.datetime.date(0))

            else:
                # We ARE in the market for this asset

                # 1. Breakeven Stop Check
                if self.entry_prices[d] is not None:
                    breakeven_trigger = self.entry_prices[d] + (ind['atr'][0] * self.params.breakeven_atr_multiplier)

                    # If current price exceeds our profit trigger, AND our stop loss is still below entry price, move it to entry
                    if d.close[0] >= breakeven_trigger and self.stop_loss_prices[d] < self.entry_prices[d]:
                        self.stop_loss_prices[d] = self.entry_prices[d]
                        self.log(f'BREAKEVEN TRIGGERED [{d._name}]: Price {d.close[0]:.2f} > {breakeven_trigger:.2f}. Stop Loss moved to Entry {self.entry_prices[d]:.2f}', dt=d.datetime.date(0))

                # 2. Update Standard Trailing Stop Loss (Only move it up, never down)
                new_stop_loss = d.close[0] - (ind['atr'][0] * self.params.atr_multiplier)

                if self.stop_loss_prices[d] is None:
                    self.stop_loss_prices[d] = new_stop_loss
                elif new_stop_loss > self.stop_loss_prices[d]:
                    self.stop_loss_prices[d] = new_stop_loss

                # 3. Check for Exit Signals
                if d.close[0] < self.stop_loss_prices[d]:
                    self.log(f'STOP LOSS HIT [{d._name}]: Close {d.close[0]:.2f} < SL {self.stop_loss_prices[d]:.2f}. SELL CREATE.', dt=d.datetime.date(0))
                    self.orders[d] = self.sell(data=d, size=pos.size)
                elif ind['crossover'][0] < 0:
                    self.log(f'SELL CREATE (Trend Reversal) [{d._name}], Price: {d.close[0]:.2f}', dt=d.datetime.date(0))
                    self.orders[d] = self.sell(data=d, size=pos.size)
