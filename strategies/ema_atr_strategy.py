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
        ('risk_per_trade_pct', 0.95), # Will allocate this total percentage across all assets (Equal Weight Cash Allocation)
        ('printlog', True),           # Flag to toggle logging off during optimization
    )

    def __init__(self):
        # Create dictionaries to hold indicators and state per data feed
        self.inds = dict()
        self.orders = dict()
        self.stop_loss_prices = dict()

        # We need to separate 4h feeds (for trading) and 1d feeds (for regime filter)
        self.daily_smas = dict()
        self.daily_data = dict()

        # First pass to identify daily feeds and calculate 200 SMA
        for d in self.datas:
            if d._name.endswith('_1d'):
                # Calculate 200 SMA on the daily feed
                sma200 = bt.indicators.SimpleMovingAverage(d, period=200)
                sma200.plotinfo.plot = False

                # We extract the base symbol (e.g., 'BTC_USDT')
                base_symbol = d._name.replace('_1d', '')
                self.daily_smas[base_symbol] = sma200
                self.daily_data[base_symbol] = d

        # Second pass to setup 4h feeds
        for d in self.datas:
            if d._name.endswith('_4h'):
                self.orders[d] = None
                self.stop_loss_prices[d] = None

                # Determine parameters for this specific asset
                fast_p, slow_p = self.params.asset_parameters.get(d._name, self.params.default_periods)

                # Indicators per feed
                fast_ema = bt.indicators.ExponentialMovingAverage(d, period=fast_p)
                slow_ema = bt.indicators.ExponentialMovingAverage(d, period=slow_p)

                atr = bt.indicators.AverageTrueRange(d, period=self.params.atr_period)
                atr.plotinfo.plot = False

                crossover = bt.indicators.CrossOver(fast_ema, slow_ema)
                crossover.plotinfo.plot = False

                base_symbol = d._name.replace('_4h', '')

                # Store in dict
                self.inds[d] = {
                    'fast_ema': fast_ema,
                    'slow_ema': slow_ema,
                    'atr': atr,
                    'crossover': crossover,
                    'slow_p': slow_p, # Save this for minimum bar checks
                    'base_symbol': base_symbol
                }

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        d = order.data

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED [{d._name}], Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm {order.executed.comm:.2f}', dt=d.datetime.date(0))

                # Initial Stop Loss
                atr = self.inds[d]['atr'][0]
                self.stop_loss_prices[d] = order.executed.price - (atr * self.params.atr_multiplier)
                self.log(f'INITIAL STOP LOSS SET [{d._name}]: {self.stop_loss_prices[d]:.2f}', dt=d.datetime.date(0))

            else:  # Sell
                self.log(f'SELL EXECUTED [{d._name}], Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm {order.executed.comm:.2f}', dt=d.datetime.date(0))
                self.stop_loss_prices[d] = None

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
        # We only want to process the 4h data feeds for trading logic
        # Count only the 4h feeds for the equal weight allocation
        trading_assets = [d for d in self.datas if d._name.endswith('_4h')]
        num_assets = len(trading_assets)

        for d in trading_assets:
            ind = self.inds[d]
            base_symbol = ind['base_symbol']

            # Make sure we have enough daily data for the 200 SMA
            daily_data_feed = self.daily_data.get(base_symbol)
            daily_sma = self.daily_smas.get(base_symbol)

            if daily_data_feed is None or daily_sma is None or len(daily_sma) < 200:
                continue

            # Skip if data is not mature enough yet for this specific asset's slow EMA
            if len(d) < ind['slow_p']:
                continue

            pos = self.getposition(d)

            # If an order is already pending for this asset, skip
            if self.orders[d]:
                continue

            if not pos:
                # We are NOT in the market for this asset
                if ind['crossover'][0] > 0:

                    # --- Multi-Timeframe Regime Filter ---
                    # To avoid lookahead bias, we must check the LAST CLOSED daily bar (-1)
                    # rather than the currently building daily bar (0) which we wouldn't know intra-day.
                    last_daily_close = daily_data_feed.close[-1]
                    last_daily_sma = daily_sma[-1]

                    if last_daily_close > last_daily_sma:
                        self.log(f'BUY CREATE [{d._name}], Price: {d.close[0]:.2f} (Daily Regime Filter Passed: Close {last_daily_close:.2f} > SMA {last_daily_sma:.2f})', dt=d.datetime.date(0))

                        # Portfolio Position Sizing (Equal Weight Cash Allocation):
                        # We allocate equal weight to each asset based on available total equity.
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
                        self.log(f'BUY BLOCKED [{d._name}] - Daily Regime Filter Failed (Close {last_daily_close:.2f} <= SMA {last_daily_sma:.2f})', dt=d.datetime.date(0))

            else:
                # We ARE in the market for this asset

                # 1. Update Trailing Stop Loss
                new_stop_loss = d.close[0] - (ind['atr'][0] * self.params.atr_multiplier)

                if self.stop_loss_prices[d] is None:
                    self.stop_loss_prices[d] = new_stop_loss
                elif new_stop_loss > self.stop_loss_prices[d]:
                    self.stop_loss_prices[d] = new_stop_loss

                # 2. Check for Exit Signals
                if d.close[0] < self.stop_loss_prices[d]:
                    self.log(f'STOP LOSS HIT [{d._name}]: Close {d.close[0]:.2f} < SL {self.stop_loss_prices[d]:.2f}. SELL CREATE.', dt=d.datetime.date(0))
                    self.orders[d] = self.sell(data=d, size=pos.size)
                elif ind['crossover'][0] < 0:
                    self.log(f'SELL CREATE (Trend Reversal) [{d._name}], Price: {d.close[0]:.2f}', dt=d.datetime.date(0))
                    self.orders[d] = self.sell(data=d, size=pos.size)
