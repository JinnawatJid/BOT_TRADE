import backtrader as bt
import datetime
from strategies.ema_atr_strategy import EmaAtrStrategy

def run_backtest():
    # 1. Create a Cerebro entity
    cerebro = bt.Cerebro()

    # 2. Add the Data Feeds for Multiple Assets
    # Expanding to Timeframe Diversification (1h + 4h) for the Elite 4 Portfolio
    symbols = ['BTC_USDT', 'ETH_USDT', 'SOL_USDT', 'BNB_USDT']
    for sym in symbols:
        # Add 1h Data First (Master Clock for Execution)
        try:
            data_1h = bt.feeds.GenericCSVData(
                dataname=f'data/{sym}_1h.csv',
                name=f'{sym}_1h',
                datetime=0,
                open=1,
                high=2,
                low=3,
                close=4,
                volume=5,
                openinterest=-1,
                dtformat=('%Y-%m-%d %H:%M:%S'),
                # Start 1h from 2022 to align the actual trading period
                fromdate=datetime.datetime(2022, 1, 1),
            )
            # Add 1h data first so it acts as the master clock, executing next() every hour
            cerebro.adddata(data_1h)
        except Exception as e:
            print(f"Skipping {sym} 1h data feed due to error: {e}")
            continue

        # Add 4h Data (for Macro Execution)
        try:
            data_4h = bt.feeds.GenericCSVData(
                dataname=f'data/{sym}_4h.csv',
                name=f'{sym}_4h',
                datetime=0,
                open=1,
                high=2,
                low=3,
                close=4,
                volume=5,
                openinterest=-1,
                dtformat=('%Y-%m-%d %H:%M:%S'),
                # Start 4h from 2022 to align the actual trading period
                fromdate=datetime.datetime(2022, 1, 1),
            )
            cerebro.adddata(data_4h)
        except Exception as e:
            print(f"Skipping {sym} 4h data feed due to error: {e}")

    # 3. Add the Strategy with Asset/Timeframe-Specific Optimized Parameters
    # We pass the best Fast/Slow EMA combinations found by our optimizer for the Elite 4 assets
    # 1h parameters are 4x the 4h parameters to ensure equivalent macro trend filtering.
    optimized_params = {
        'BTC_USDT_4h': (50, 110),
        'ETH_USDT_4h': (40, 50),
        'SOL_USDT_4h': (40, 170),
        'BNB_USDT_4h': (30, 170),

        'BTC_USDT_1h': (200, 440),
        'ETH_USDT_1h': (160, 200),
        'SOL_USDT_1h': (160, 680),
        'BNB_USDT_1h': (120, 680)
    }

    cerebro.addstrategy(EmaAtrStrategy, asset_parameters=optimized_params)

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

        # Adjust Matplotlib figure size globally to make the chart bigger and easier to read
        plt.rcParams['figure.figsize'] = [15, 8]
        plt.rcParams['figure.dpi'] = 100

        print("\nSaving plot to backtest_result.png...")

        # Turn off volume overlay on the main chart to reduce clutter
        # We also pass volume=False to the plot
        fig = cerebro.plot(style='candlestick', iplot=False, volume=False)[0][0]
        fig.savefig('backtest_result.png')
        print("Plot saved successfully.")
    except Exception as e:
        print(f"Plotting skipped due to: {e}")

if __name__ == '__main__':
    run_backtest()
