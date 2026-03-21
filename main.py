import backtrader as bt
import datetime
from strategies.ema_atr_strategy import EmaAtrStrategy

def run_backtest():
    # 1. Create a Cerebro entity
    cerebro = bt.Cerebro()

    # 2. Add the Data Feed
    # Use standard pandas-compatible CSV feed
    data = bt.feeds.GenericCSVData(
        dataname='data/BTC_USDT_1d.csv',
        # Ensure dates are parsed correctly
        datetime=0,
        open=1,
        high=2,
        low=3,
        close=4,
        volume=5,
        openinterest=-1,
        dtformat=('%Y-%m-%d'),
        # Set start and end dates if needed, else it runs all
        # fromdate=datetime.datetime(2020, 1, 1),
        # todate=datetime.datetime(2023, 12, 31),
    )
    cerebro.adddata(data)

    # 3. Add the Strategy
    # Using the EmaAtrStrategy we defined
    cerebro.addstrategy(EmaAtrStrategy)

    # 4. Set Broker parameters
    # Set starting cash
    start_cash = 10000.0
    cerebro.broker.setcash(start_cash)

    # Set commission - 0.1% is standard for Binance Spot
    cerebro.broker.setcommission(commission=0.001)

    # 5. Add Analyzers
    # Analyzers provide metrics after the backtest is complete
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

    # Print out the starting conditions
    print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())

    # 6. Run the backtest
    results = cerebro.run()

    # 7. Print results
    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
    strat = results[0]

    print("\n--- Backtest Metrics ---")

    # Sharpe Ratio
    sharpe = strat.analyzers.sharpe.get_analysis()
    print(f"Sharpe Ratio: {sharpe.get('sharperatio', 'N/A')}")

    # Drawdown
    drawdown = strat.analyzers.drawdown.get_analysis()
    print(f"Max Drawdown: {drawdown.max.drawdown:.2f}%")

    # Trade Analyzer
    trades = strat.analyzers.trades.get_analysis()
    total_trades = trades.total.total
    if total_trades > 0:
        won = trades.won.total
        lost = trades.lost.total
        win_rate = (won / total_trades) * 100
        print(f"Total Trades: {total_trades}")
        print(f"Win Rate: {win_rate:.2f}% ({won} won, {lost} lost)")

        # Profit factor
        gross_profit = trades.won.pnl.total if won > 0 else 0
        gross_loss = abs(trades.lost.pnl.total) if lost > 0 else 0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')
        print(f"Profit Factor: {profit_factor:.2f}")
    else:
        print("No trades were executed.")

    # 8. Plot the result and save to file (Matplotlib setup fix for headless)
    try:
        import matplotlib.pyplot as plt
        print("\nSaving plot to backtest_result.png...")
        fig = cerebro.plot(style='candlestick', iplot=False)[0][0]
        fig.savefig('backtest_result.png')
        print("Plot saved successfully.")
    except Exception as e:
        print(f"Plotting skipped due to: {e}")

if __name__ == '__main__':
    run_backtest()
