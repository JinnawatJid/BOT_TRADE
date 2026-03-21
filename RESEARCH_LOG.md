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