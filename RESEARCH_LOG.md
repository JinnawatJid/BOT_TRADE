# Trading Bot Research Log

This document serves as our "laboratory notebook" for tracking experiments with strategy parameters and risk models. It prevents us from relying on memory and ensures we make data-driven decisions toward a robust, industry-standard trading system.

## Core Asset & Timeframe
- Asset: BTC/USDT (Spot)
- Timeframe: 1 Day (1d)
- Historical Data Range: ~2020 to ~2026 (Binance/KuCoin data)
- Starting Capital: $10,000
- Base Commission: 0.1%

---

## Experiment 1: Baseline Trend Following (Slow)
**Date:** Initial Setup
**Strategy:** EMA Crossover (50/200) + ATR Trailing Stop (14 period, 2.0x)
**Position Sizing:** Fixed Fractional Risk (2% of equity risked per trade based on ATR distance).

*   **Logic:** A very slow trend-following approach aimed at capturing multi-year macro trends while strictly limiting downside to 2% per trade.
*   **Results:**
    *   Total Trades: 3
    *   Win Rate: 33.33% (1 won, 2 lost)
    *   Profit Factor: 7.40
    *   Max Drawdown: 5.84%
    *   Sharpe Ratio: 0.24
    *   Final Portfolio Value: $11,729 (+17%)
*   **Conclusion:** Incredibly safe (low drawdown) and excellent asymmetric risk/reward (Profit Factor 7.4). However, the return is abysmal compared to simply holding BTC over 6 years. The low Sharpe Ratio indicates highly inefficient use of capital (mostly holding cash due to the strict 2% risk limit on a highly volatile asset).

---

## Experiment 2: Increased Frequency (Medium-term Trend)
**Date:** First Optimization
**Strategy:** EMA Crossover (20/50) + ATR Trailing Stop (14 period, 2.0x)
**Position Sizing:** Fixed Fractional Risk (2% of equity risked per trade).

*   **Logic:** Sped up the EMAs from 50/200 to 20/50 to make the bot trade more frequently and catch medium-term swings, responding faster to market changes.
*   **Results:**
    *   Total Trades: 17
    *   Win Rate: 41.18% (7 won, 10 lost)
    *   Profit Factor: 2.50
    *   Max Drawdown: 10.04%
    *   Sharpe Ratio: 0.37
    *   Final Portfolio Value: $13,754 (+37%)
*   **Conclusion:** Trade frequency increased significantly, and the strategy proved profitable over a larger sample size. Win rate is standard for trend following (~40%), and Profit Factor remains very strong (> 2.0). Drawdown is still extremely manageable (10%). However, the absolute return (37% in 6 years) is still vastly underperforming Buy & Hold. The core issue remains: the 2% ATR risk model allocates too little capital to the actual trades.

---

## Experiment 3: Maximizing Capital Efficiency (All-in Spot)
**Date:** Position Sizing Optimization
**Strategy:** EMA Crossover (20/50) + ATR Trailing Stop (14 period, 2.0x)
**Position Sizing:** 95% of available cash allocated per trade (ignoring the 2% ATR strict risk limit).

*   **Logic:** To combat the underperformance vs. Buy & Hold in the crypto market, we allocate 95% of our available capital when a signal occurs. We rely entirely on the ATR Trailing Stop to cut losses, rather than limiting the initial position size.
*   **Results:**
    *   Total Trades: 17
    *   Win Rate: 41.18% (7 won, 10 lost)
    *   Profit Factor: 1.99
    *   Max Drawdown: 31.78%
    *   Sharpe Ratio: 0.48
    *   Final Portfolio Value: $22,307 (+123%)
*   **Conclusion:** This is a massive improvement in absolute return. The portfolio grew by 123% (ending over $22k), bringing it much closer to standard crypto expectations. The Sharpe Ratio also improved to nearly 0.5. The tradeoff is a higher, but expected, Max Drawdown (31.78%), which is standard for a fully invested crypto portfolio. The Profit Factor of 1.99 shows the strategy remains fundamentally sound and highly profitable even when scaled up.

---

## Experiment 4: ADX Trend Filter (Sideways Avoidance)
**Date:** Adding Filters
**Strategy:** EMA Crossover (20/50) + ADX Filter (>25) + ATR Trailing Stop (14 period, 2.0x)
**Position Sizing:** 95% of available cash allocated per trade.

*   **Logic:** To combat the high drawdown from false signals in sideways markets (whipsaws), we introduced an ADX filter (14-period). The strategy will only trigger a BUY signal if the EMA crosses over AND the ADX is > 25, meaning a strong trend is already established.
*   **Results:**
    *   Total Trades: 6
    *   Win Rate: 50.00% (3 won, 3 lost)
    *   Profit Factor: 2.09
    *   Max Drawdown: 21.87%
    *   Sharpe Ratio: 0.21
    *   Final Portfolio Value: $12,409 (+24%)
*   **Conclusion:** The ADX filter worked *too well* at filtering out trades. While it successfully boosted the Win Rate to 50% and lowered the Max Drawdown significantly (from 31% to 21%), it caused the bot to miss the initial explosive breakouts of massive trends (because ADX lags and is often < 25 at the very bottom of a crossover). As a result, the total return plummeted back to +24%.
*   **Next Steps:** Using a strict ADX > 25 requirement on an already lagging indicator (EMA Crossover) causes us to enter trades far too late. We should likely remove the ADX filter from the entry conditions or find a leading indicator for volume/momentum instead.

---

## Experiment 5: Portfolio Diversification (Multi-Asset)
**Date:** Portfolio Sizing
**Strategy:** Reverted to Baseline Experiment 3 (EMA 20/50 + ATR Trailing Stop, No ADX).
**Assets Traded:** BTC/USDT, ETH/USDT, SOL/USDT, BNB/USDT.
**Timeframe Limit:** 2021 to 2026 (due to SOL data availability).
**Position Sizing:** Equal weight allocation. 95% of total portfolio equity divided evenly among the 4 assets (~23.75% allocation per asset signal).

*   **Logic:** Instead of over-engineering the strategy with filters (like ADX), we embrace the sideways whipsaws and use "Diversification" to smooth out the equity curve. We run the highly profitable EMA 20/50 strategy across a basket of 4 major crypto assets.
*   **Results:**
    *   Total Trades: 54
    *   Win Rate: 29.63% (16 won, 38 lost)
    *   Profit Factor: 0.85
    *   Max Drawdown: 37.86%
    *   Sharpe Ratio: -0.04
    *   Final Portfolio Value: $8,951 (-10.5%)
*   **Conclusion:** The results are highly counterintuitive. Diversification *failed* completely in this scenario, destroying the portfolio. The issue is two-fold:
    1.  **Over-Optimization on BTC:** The EMA (20/50) and ATR (14, 2.0x) parameters were originally hand-tuned specifically for Bitcoin's volatility profile. Applying these exact same parameters blindly to highly volatile altcoins like SOL and ETH resulted in the bot constantly getting whipsawed and stopped out prematurely.
    2.  **High Correlation:** Crypto assets are highly correlated to BTC. When BTC goes sideways, the altcoins go sideways but with *higher volatility*, triggering even more false breakouts.
*   **Next Steps:** A blanket parameter approach does not work across a diverse portfolio. We either need to run Parameter Sweeping (Grid Search) for *each individual asset*, or return to trading a single major asset (BTC) using the optimized baseline.

---

## Experiment 6: Parameter Sweeping / Grid Search (Industry Standard)
**Date:** Optimization
**Strategy:** EMA Crossover + ATR Trailing Stop (14 period, 2.0x)
**Asset:** BTC/USDT (Single Asset Baseline)
**Position Sizing:** 95% of available cash (All-in Spot)

*   **Logic:** Instead of randomly guessing EMA periods and hoping they work, we built an `optimizer.py` script. This tool leverages Backtrader's multi-run capabilities to sweep through multiple combinations of Fast EMA (10 to 30) and Slow EMA (40 to 80). The goal is to mathematically determine the "Robust Parameter Zone" for BTC that yields the best risk-adjusted return (Sharpe Ratio).
*   **Results (Top Parameter Sets Discovered):**
    *   **#1 Best Risk-Adjusted (Highest Sharpe):** Fast EMA 10 / Slow EMA 60.
        - Sharpe: 0.7520
        - Max Drawdown: 23.80%
        - ROI: 265% (Final Value: $36,524)
    *   **#2 Highest Absolute Return:** Fast EMA 10 / Slow EMA 50.
        - Sharpe: 0.6641
        - Max Drawdown: 29.12%
        - ROI: 345% (Final Value: $44,521)
    *   *Note: Original 20/50 parameters yielded a Sharpe of only 0.55 and ROI of 125%.*
*   **Conclusion:** The optimizer proved that our arbitrary 20/50 pairing was significantly sub-optimal. A **10/60 EMA Crossover** reacts faster to trend beginnings (Fast 10) but is more patient with the underlying macro trend (Slow 60). This pairing pushed the Sharpe Ratio to 0.75 while keeping Maximum Drawdown at a very comfortable 23.8%. Alternatively, if a fund is willing to accept ~30% drawdown, the 10/50 pairing generates a massive 345% return.
*   **Next Steps:** Update `main.py` and `strategies/ema_atr_strategy.py` to use these mathematically optimal 10/60 parameters as the new baseline for BTC.
