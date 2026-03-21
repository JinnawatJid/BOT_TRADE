import backtrader as bt

class EmaAtrStrategy(bt.Strategy):
    """
    Trend Following Strategy using EMA Crossover and ATR Trailing Stop Loss.
    """
    params = (
        ('fast_period', 50),
        ('slow_period', 110),
        ('atr_period', 14),
        ('atr_multiplier', 2.0),
        ('risk_per_trade_pct', 0.95), # Will allocate this total percentage across all assets
        ('printlog', True),           # Flag to toggle logging off during optimization
    )

    def __init__(self):
        # Create dictionaries to hold indicators and state per data feed
        self.inds = dict()
        self.orders = dict()
        self.stop_loss_prices = dict()

        for d in self.datas:
            self.orders[d] = None
            self.stop_loss_prices[d] = None

            # Indicators per feed
            fast_ema = bt.indicators.ExponentialMovingAverage(d, period=self.params.fast_period)
            slow_ema = bt.indicators.ExponentialMovingAverage(d, period=self.params.slow_period)

            atr = bt.indicators.AverageTrueRange(d, period=self.params.atr_period)
            atr.plotinfo.plot = False

            crossover = bt.indicators.CrossOver(fast_ema, slow_ema)
            crossover.plotinfo.plot = False

            # Store in dict
            self.inds[d] = {
                'fast_ema': fast_ema,
                'slow_ema': slow_ema,
                'atr': atr,
                'crossover': crossover
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
        # In a portfolio, we loop through all available data feeds
        num_assets = len(self.datas)

        for d in self.datas:
            # Skip if data is not mature enough yet
            if len(d) < self.params.slow_period:
                continue

            pos = self.getposition(d)
            ind = self.inds[d]

            # If an order is already pending for this asset, skip
            if self.orders[d]:
                continue

            if not pos:
                # We are NOT in the market for this asset
                if ind['crossover'][0] > 0:
                    self.log(f'BUY CREATE [{d._name}], Price: {d.close[0]:.2f}', dt=d.datetime.date(0))

                    # Portfolio Position Sizing:
                    # We allocate equal weight to each asset.
                    # E.g., if total risk is 95% and we have 4 assets, each asset gets ~23.75% of TOTAL equity.
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
