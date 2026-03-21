import backtrader as bt
import datetime
from strategies.ema_atr_strategy import EmaAtrStrategy

def run_optimizer():
    print("Starting Parameter Optimization (Grid Search)...")

    # 1. Create a Cerebro engine optimized for multiprocessing
    # Set maxcpus=1 to avoid multiprocessing issues in some environments (like Windows/Sandbox),
    # or let it default if your system handles it well. We'll use 1 for stability here.
    cerebro = bt.Cerebro(maxcpus=1, optreturn=False)

    # 2. Add the Data Feed (Focusing on BTC for optimization)
    # Using full history to get better backtest coverage
    data = bt.feeds.GenericCSVData(
        dataname='data/BTC_USDT_1d.csv',
        name='BTC_USDT',
        datetime=0,
        open=1,
        high=2,
        low=3,
        close=4,
        volume=5,
        openinterest=-1,
        dtformat=('%Y-%m-%d'),
    )
    cerebro.adddata(data)

    # 3. Add the Strategy with Optimization Parameters
    # Instead of addstrategy, we use optstrategy
    # We will test fast_period from 10 to 30 (steps of 5)
    # and slow_period from 40 to 80 (steps of 10)
    print("Sweeping Fast EMA: 10 to 30 (step 5)")
    print("Sweeping Slow EMA: 40 to 80 (step 10)")

    cerebro.optstrategy(
        EmaAtrStrategy,
        fast_period=range(10, 31, 5),    # [10, 15, 20, 25, 30]
        slow_period=range(40, 81, 10),   # [40, 50, 60, 70, 80]
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
                'final_value': final_value,
                'roi_pct': roi_pct
            })

    # Sort results primarily by Sharpe Ratio (Industry Standard for robust optimization), then by ROI
    sorted_results = sorted(results_list, key=lambda x: (x['sharpe'], x['roi_pct']), reverse=True)

    # Print top 10 results
    print(f"{'Fast EMA':<10} | {'Slow EMA':<10} | {'ROI (%)':<10} | {'Max DD (%)':<12} | {'Sharpe':<10} | {'Final Value':<15}")
    print("-" * 75)
    for res in sorted_results[:10]:
        print(f"{res['fast']:<10} | {res['slow']:<10} | {res['roi_pct']:<10.2f} | {res['max_dd']:<12.2f} | {res['sharpe']:<10.4f} | ${res['final_value']:<15.2f}")

if __name__ == '__main__':
    run_optimizer()
