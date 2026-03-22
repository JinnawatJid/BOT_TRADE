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

        for d in self.datas:
            self.orders[d] = None
            self.stop_loss_prices[d] = None
            self.entry_prices[d] = None

            # Determine parameters for this specific asset
            fast_p, slow_p = self.params.asset_parameters.get(d._name, self.params.default_periods)

            # Indicators per feed
            fast_ema = bt.indicators.ExponentialMovingAverage(d, period=fast_p)
            slow_ema = bt.indicators.ExponentialMovingAverage(d, period=slow_p)

            atr = bt.indicators.AverageTrueRange(d, period=self.params.atr_period)
            atr.plotinfo.plot = False

            crossover = bt.indicators.CrossOver(fast_ema, slow_ema)
            crossover.plotinfo.plot = False

            # Indicator for Pullback Re-Entry: Price crossing above Fast EMA
            price_fast_cross = bt.indicators.CrossOver(d.close, fast_ema)
            price_fast_cross.plotinfo.plot = False

            # Store in dict
            self.inds[d] = {
                'fast_ema': fast_ema,
                'slow_ema': slow_ema,
                'atr': atr,
                'crossover': crossover,
                'price_fast_cross': price_fast_cross,
                'slow_p': slow_p # Save this for minimum bar checks
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
        # In a portfolio, we loop through all available data feeds
        num_assets = len(self.datas)

        for d in self.datas:
            ind = self.inds[d]

            # Skip if data is not mature enough yet for this specific asset's slow EMA
            if len(d) < ind['slow_p']:
                continue

            pos = self.getposition(d)

            # If an order is already pending for this asset, skip
            if self.orders[d]:
                continue

            if not pos:
                # We are NOT in the market for this asset

                # Condition 1: Macro Trend Crossover Entry
                is_macro_entry = ind['crossover'][0] > 0

                # Condition 2: Pullback Re-Entry (Macro Trend is UP, and Price just crossed back above Fast EMA)
                is_macro_up = ind['fast_ema'][0] > ind['slow_ema'][0]
                is_pullback_recovery = ind['price_fast_cross'][0] > 0
                is_reentry = is_macro_up and is_pullback_recovery

                if is_macro_entry or is_reentry:
                    entry_type = "MACRO CROSSOVER" if is_macro_entry else "PULLBACK RE-ENTRY"
                    self.log(f'BUY CREATE ({entry_type}) [{d._name}], Price: {d.close[0]:.2f}', dt=d.datetime.date(0))

                    # Portfolio Position Sizing (Equal Weight Cash Allocation):
                    # We allocate equal weight to each asset based on available total equity.
                    # E.g., if total risk is 95% and we have 8 assets (4 coins * 2 timeframes), each gets ~11.87%
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
