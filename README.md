# Team110-Profit pulse (IIIT Dharwad) | APAC Quant Trading Hackathon

## 1. Problem Statement
The objective of the APAC University Quant Trading Hackathon (HK vs AU vs IN) is to build a fully autonomous quantitative trading algorithm deployed on an AWS EC2 instance. The bot executes trades via the Roostoo mock exchange API without human intervention. 

The primary evaluation criteria prioritize risk-adjusted returns over sheer aggressive profit. The final leaderboard is weighted heavily against downside volatility via a Composite Risk-Adjusted Score:
* 0.4 × Sortino Ratio
* 0.3 × Sharpe Ratio
* 0.3 × Calmar Ratio

## 2. Portfolio Strategy & Inspiration
**Strategy:** Dual Simple Moving Average (SMA) Momentum Crossover
**Rationale:** Because the composite scoring system severely penalizes maximum drawdowns (Calmar) and downside variance (Sortino), we opted against high-variance predictive models. Instead, we engineered a highly defensive, medium-frequency momentum strategy designed for capital preservation.
* **Fast Trend (5-minute SMA):** Captures immediate price action and volume shifts.
* **Slow Trend (15-minute SMA):** Acts as the baseline market regime filter.
* **Trigger Logic:** The bot enters a long position only when the Fast SMA crosses above the Slow SMA (confirmed upward momentum). Crucially, it flattens the entire position back to cash when the Fast SMA drops below the Slow SMA, stepping out of the market entirely during downward trends.

## 3. Implementation & Trading Engine
The repository is kept lightweight to ensure high-performance execution on the AWS `t3.medium` instance.
* `bot.py`: The core algorithmic trading engine and Roostoo API client.
* `requirements.txt`: Python dependencies (`requests`, `python-dotenv`).
* `.env` (ignored in repo): Secure storage for Roostoo API credentials.

**Trading Engine Architecture:**
The engine operates on a continuous 60-second polling loop to respect API rate limits.
1. **Ingestion:** Fetches the latest `/v3/ticker` data for `BTC/USD` and dynamically manages a 15-minute rolling memory array.
2. **Authentication:** Implements a custom HMAC-SHA256 signature generator to satisfy Roostoo's `RCL_TopLevelCheck` security level.
3. **Execution:** Evaluates the rolling arrays and dispatches authenticated HTTP POST requests to `/v3/place_order` when strict crossover thresholds are breached.

## 4. Transaction Fee Management (Maker vs. Taker)
The Roostoo exchange fee tier charges 0.1% for Taker (Market) orders and 0.05% for Maker (Limit) orders. 

In momentum-based trend-following, the financial cost of a missed fill during a violent downward crash exponentially outweighs a 0.05% fee difference. To fiercely protect our Calmar Ratio, the engine deliberately utilizes **Taker (MARKET) orders** to guarantee immediate execution. We modeled the 0.1% taker fee as an acceptable insurance premium against slippage and stranded limit orders during sudden market regime shifts.

## 5. Risk Management Framework
Our risk management protocols are directly embedded into the strategy logic to maximize the composite score:
* **Zero-Leverage Spot Only:** Entirely eliminates liquidation risk.
* **Flat-by-Default:** The bot holds cash (USD) during uncertain or downward-trending regimes, minimizing overall market exposure.
* **Dynamic Stop-Loss:** The downward crossover (Fast < Slow) acts as an automated circuit breaker. If the market suddenly crashes, the bot automatically cuts the position within 5 minutes, enforcing a strict mathematical ceiling on maximum drawdowns.

## 6. Backtesting
Before live deployment, the strategy logic was validated against historical Binance Vision 1-minute Klines. The backtest intentionally prioritized periods of high volatility (e.g., flash crashes). Results confirmed that while absolute returns may lag behind a pure buy-and-hold strategy during parabolic bull runs, the crossover algorithm drastically cuts Max Drawdown by systematically exiting positions before structural crashes, yielding vastly superior Sortino and Calmar ratios.

## 7. AWS Cloud Deployment
This system is actively deployed on the provisioned AWS infrastructure:
* **Region:** `ap-southeast-2` (Sydney)
* **Instance:** `t3.medium`
* **Session Management:** The process runs continuously inside a detached `tmux` session, ensuring 24/7 autonomous uptime independent of local SSH/browser sessions.

  Your Team's Roostoo General Portfolio API credentials (For Testing):
– API Key: 3zC8uTj17OwYBKt0HaQZ4vXPJs6oS3A2f3wIrzQpqeLWlDijWdHpp4yUbG7doPUG
– API Secret: jOShCFmC0tsYUgdglOtJjTGpmcZ0vujEXMPejngGicCPMEKz8zvxQx6DBnlpI9EN
Your Team's Roostoo Competition API credentials (For Actual Competition):
– API Key: o5J2ZEqQeCDiuJfEYxM145D3lwHoHA4S0BR4xIAyC1FOEVpav1M4jydFnSuCfeq3
– API Secret: xfiybOuFdVi13EjznngbNT3eEM70gBJTR2hOfxjHspBIJRtaXjHGhsrMuGjQv7Fj
