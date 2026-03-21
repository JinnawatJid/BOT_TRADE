import backtrader as bt

class EmaAtrStrategy(bt.Strategy):
    """
    Trend Following Strategy using EMA Crossover and ATR Trailing Stop Loss.
    """
    params = (
        ('fast_period', 20),
        ('slow_period', 50),
        ('atr_period', 14),
        ('atr_multiplier', 2.0),
        ('risk_per_trade_pct', 0.02), # 2% risk per trade
    )

    def __init__(self):
        # Data feeds
        self.dataclose = self.datas[0].close
        self.datahigh = self.datas[0].high
        self.datalow = self.datas[0].low

        # Indicators
        self.fast_ema = bt.indicators.ExponentialMovingAverage(
            self.datas[0], period=self.params.fast_period
        )
        self.slow_ema = bt.indicators.ExponentialMovingAverage(
            self.datas[0], period=self.params.slow_period
        )
        self.atr = bt.indicators.AverageTrueRange(
            self.datas[0], period=self.params.atr_period
        )
        # Hide ATR from the plot to reduce clutter
        self.atr.plotinfo.plot = False

        # Crossover signal
        self.crossover = bt.indicators.CrossOver(self.fast_ema, self.slow_ema)
        # Hide the Crossover 1/-1 line from the plot to reduce clutter
        self.crossover.plotinfo.plot = False

        # To keep track of pending orders and buy price/commission
        self.order = None
        self.buyprice = None
        self.buycomm = None
        self.stop_loss_price = None

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            # Buy/Sell order submitted/accepted to/by broker - Nothing to do
            return

        # Check if an order has been completed
        # Attention: broker could reject order if not enough cash
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    'BUY EXECUTED, Price: %.2f, Cost: %.2f, Comm %.2f' %
                    (order.executed.price,
                     order.executed.value,
                     order.executed.comm))

                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm

                # Initial Stop Loss
                self.stop_loss_price = self.buyprice - (self.atr[0] * self.params.atr_multiplier)
                self.log(f'INITIAL STOP LOSS SET: {self.stop_loss_price:.2f}')

            else:  # Sell
                self.log('SELL EXECUTED, Price: %.2f, Cost: %.2f, Comm %.2f' %
                         (order.executed.price,
                          order.executed.value,
                          order.executed.comm))
                # Reset stop loss
                self.stop_loss_price = None

            self.bar_executed = len(self)

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')

        # Write down: no pending order
        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return

        self.log('OPERATION PROFIT, GROSS %.2f, NET %.2f' %
                 (trade.pnl, trade.pnlcomm))

    def log(self, txt, dt=None):
        ''' Logging function fot this strategy'''
        dt = dt or self.datas[0].datetime.date(0)
        print('%s, %s' % (dt.isoformat(), txt))

    def next(self):
        # Simply log the closing price of the series from the reference
        # self.log('Close, %.2f' % self.dataclose[0])

        # Check if an order is pending ... if yes, we cannot send a 2nd one
        if self.order:
            return

        # Check if we are in the market
        if not self.position:

            # Not yet ... we MIGHT BUY if ...
            if self.crossover > 0:
                # Fast EMA crosses above Slow EMA -> BUY SIGNAL
                self.log('BUY CREATE, %.2f' % self.dataclose[0])

                # Calculate Position Size based on Risk
                # Risk per trade = Capital * Risk%
                # Risk = (Entry - Stop Loss) -> ATR * Multiplier
                # Size = Risk per trade / (ATR * Multiplier)

                # Use current equity
                equity = self.broker.getvalue()
                risk_amount = equity * self.params.risk_per_trade_pct
                risk_per_coin = self.atr[0] * self.params.atr_multiplier

                if risk_per_coin > 0:
                    size = risk_amount / risk_per_coin
                    # Check if we have enough cash (simplified, broker does strict check)

                    # Keep track of the created order to avoid a 2nd order
                    self.order = self.buy(size=size)
                else:
                    self.log('Cannot calculate position size (ATR too small)')

        else:
            # We are already in the market

            # 1. Update Trailing Stop Loss
            # Stop Loss moves UP with the price, but never goes down
            new_stop_loss = self.dataclose[0] - (self.atr[0] * self.params.atr_multiplier)
            if new_stop_loss > self.stop_loss_price:
                self.stop_loss_price = new_stop_loss
                # self.log(f'STOP LOSS MOVED UP TO: {self.stop_loss_price:.2f}')

            # 2. Check for Exit Signals
            # Exit if price drops below Trailing Stop Loss OR if Fast EMA crosses below Slow EMA (Trend Change)
            if self.dataclose[0] < self.stop_loss_price:
                self.log(f'STOP LOSS HIT: Close {self.dataclose[0]:.2f} < SL {self.stop_loss_price:.2f}. SELL CREATE.')
                self.order = self.sell(size=self.position.size)
            elif self.crossover < 0:
                self.log('SELL CREATE (Trend Reversal), %.2f' % self.dataclose[0])
                self.order = self.sell(size=self.position.size)
