import backtrader as bt
import datetime
from strategies.ema_atr_strategy import EmaAtrStrategy

def run_optimizer():
    print("Starting Parameter Optimization (Grid Search)...")

    # 1. Create a Cerebro engine optimized for multiprocessing
    # Set maxcpus=1 to avoid multiprocessing issues in some environments (like Windows/Sandbox),
    # or let it default if your system handles it well. We'll use 1 for stability here.
    cerebro = bt.Cerebro(maxcpus=1, optreturn=False)

    # 2. Add the Data Feed (Focusing on BTC for optimization on 4h timeframe)
    # Using full history to get better backtest coverage
    data = bt.feeds.GenericCSVData(
        dataname='data/BTC_USDT_4h.csv',
        name='BTC_USDT_4h',
        datetime=0,
        open=1,
        high=2,
        low=3,
        close=4,
        volume=5,
        openinterest=-1,
        dtformat=('%Y-%m-%d %H:%M:%S'), # 4h format includes time
    )
    cerebro.adddata(data)

    # 3. Add the Strategy with Optimization Parameters for 4h Timeframe
    # On a 4h chart, the number of bars is 6x the daily bars.
    # Therefore, EMA values should generally be larger to capture similar absolute time trends,
    # or keep them somewhat similar to capture faster micro-trends.
    print("Sweeping Fast EMA: 10 to 50 (step 10)")
    print("Sweeping Slow EMA: 50 to 200 (step 30)")

    cerebro.optstrategy(
        EmaAtrStrategy,
        fast_period=range(10, 51, 10),    # [10, 20, 30, 40, 50]
        slow_period=range(50, 201, 30),   # [50, 80, 110, 140, 170, 200]
        # Keep others constant for this test.
        # Ensure we are simulating an ALL-IN strategy on a SINGLE asset for optimization
        # (Since we are passing 1 asset, 0.95 means 95% allocation)
        atr_period=14,
        atr_multiplier=2.0,
        risk_per_trade_pct=0.95,
        printlog=False # Disable verbose logs for speed and clarity
    )

    # 4. Set Broker parameters
    start_cash = 10000.0
    cerebro.broker.setcash(start_cash)
    cerebro.broker.setcommission(commission=0.001)

    # 5. Add Analyzers
    # We need analyzers to evaluate which parameter set performed best
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='timereturn') # Needed to accurately track total equity growth per run independently

    # 6. Run the optimization
    print("Running simulations... This may take a moment.")
    optimized_runs = cerebro.run()

    # 7. Process and sort results
    print("\n--- Optimization Results ---")
    results_list = []

    for run in optimized_runs:
        for strategy in run:
            # Extract parameters
            fast = strategy.params.fast_period
            slow = strategy.params.slow_period

            # Extract analyzer results
            sharpe_analysis = strategy.analyzers.sharpe.get_analysis()
            sharpe = sharpe_analysis.get('sharperatio', 0)
            if sharpe is None:
                sharpe = 0

            drawdown_analysis = strategy.analyzers.drawdown.get_analysis()
            max_dd = drawdown_analysis.max.drawdown

            # Extract Trade data
            trades_analysis = strategy.analyzers.trades.get_analysis()
            total_trades = trades_analysis.total.total if 'total' in trades_analysis and 'total' in trades_analysis.total else 0
            win_rate = 0.0
            if total_trades > 0 and 'won' in trades_analysis and 'total' in trades_analysis.won:
                win_rate = (trades_analysis.won.total / total_trades) * 100

            # Calculate accurate final return for this specific strategy run
            # because strategy.broker.getvalue() returns the LAST run's value for all of them
            returns_analysis = strategy.analyzers.returns.get_analysis()
            # 'rtot' is the total compound return (log return). To get simple percentage:
            import math
            roi_pct = (math.exp(returns_analysis['rtot']) - 1) * 100
            final_value = start_cash * math.exp(returns_analysis['rtot'])

            # Store result
            results_list.append({
                'fast': fast,
                'slow': slow,
                'sharpe': sharpe,
                'max_dd': max_dd,
                'total_trades': total_trades,
                'win_rate': win_rate,
                'final_value': final_value,
                'roi_pct': roi_pct
            })

    # Sort results primarily by Sharpe Ratio (Industry Standard for robust optimization), then by ROI
    sorted_results = sorted(results_list, key=lambda x: (x['sharpe'], x['roi_pct']), reverse=True)

    # Print top 10 results
    print(f"{'Fast EMA':<9} | {'Slow EMA':<9} | {'Trades':<7} | {'Win%':<7} | {'ROI (%)':<9} | {'Max DD (%)':<11} | {'Sharpe':<8} | {'Final Value':<15}")
    print("-" * 95)
    for res in sorted_results[:10]:
        print(f"{res['fast']:<9} | {res['slow']:<9} | {res['total_trades']:<7} | {res['win_rate']:<7.1f} | {res['roi_pct']:<9.2f} | {res['max_dd']:<11.2f} | {res['sharpe']:<8.4f} | ${res['final_value']:<15.2f}")

if __name__ == '__main__':
    run_optimizer()
