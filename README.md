
# Coinbase Systematic Trader

## About
This project creates a **systematic trading program** using the **Coinbase API** to trade a basket of cryptocurrencies.  
It follows **Markowitz Portfolio Theory** and **Mean Variance Optimization (MVO)** to maximize expected return for a given volatility, using the **Sharpe Ratio** as the performance metric.  
The system trades on a **medium-frequency** basis (daily) using automated Python scripts.

---

## Table of Contents
- [System Requirements](#system-requirements)
- [Coins in Portfolio](#coins-in-portfolio)
- [Constraints](#constraints)
- [Financial Engineering Theory](#financial-engineering-theory)
- [Dependencies](#dependencies)
- [Repository Organization](#repository-organization)
- [Workflow / Deployment](#workflow--deployment)
- [Results](#results)
- [Licenses](#licenses)
- [Contact](#contact)

---

## System Requirements

### Functional
- Make trades through the **Coinbase API**  
- Track daily trading decisions and send updates  
- Simulate trading strategy *x* days in the past to the present  

### Non-Functional
- Runs daily at **00:00:00 UTC**  
- Legible, easily understandable code  
- Easily editable hyperparameters  

---

## Coins in Portfolio
*(Data as of October 15, 2025)*

### Bitcoin (BTC)
- Current Price ≈ **$110,774**
- All-Time High ≈ **$126,210.50** (October 6, 2025)
- Market Cap ≈ **$2.21 trillion**
- The original cryptocurrency — highly liquid with capped supply (21 million)

### Ethereum (ETH)
- Current Price ≈ **$3,978.76**
- All-Time High ≈ **$4,946.05** (August 24, 2025)
- Market Cap ≈ **$480–490 billion**
- Used in smart contract platforms and decentralized apps; offers staking

### Paxos Gold (PAXG)
- Current Price ≈ **$4,246.12**
- All-Time High ≈ **$4,246.12** (October 15, 2025)
- Market Cap ≈ **$1.31 billion**
- Stablecoin pegged to the price of gold

### Solana (SOL)
- Current Price ≈ **$183.41**
- All-Time High ≈ **$293.31** (January 19, 2025)
- Market Cap ≈ **$113.6 billion**

### US Dollar Coin (USDC)
- Current Price ≈ **$0.9996**
- Max Price ≈ **$1.00**
- Market Cap ≈ **$76.1 billion**
- Regulated stablecoin fully backed by liquid reserves, redeemable 1:1 with USD

---

## Constraints

### Risk-Free Rate (rf)
- **rf = 4.10%** (annualized APY of holding cash in USDC on Coinbase)

### Trading Rules
- Long-only — no shorting
- Sum of holdings = 1
- Daily rebalance at **00:00:00 UTC**
- Turnover cap: **50%**
- Rebalance bands: **±20%**
- Model Coinbase maker/taker fees; use **post-only** where possible
- Respect minimum order sizes and increments
- **Post-only TWAP** over 30–60 minutes, with market-order failsafe

### Optimization
- Target volatility ≤ **15%**
- Objective: **maximize Sharpe ratio**

### Portfolio
- Starting capital: **$200**
- **Self-financing:** can only trade within portfolio value

---

## Financial Engineering Theory

### Data Aggregation
- Pull daily close prices for each coin (look back 60+ days)
- Compute **daily log returns** for coins:  
  `ri,t = ln(Pi,t / Pi,t−1)`
- Compute **daily risk-free log return** from USDC:  
  `rf,t = ln(1 + APYt) / 365`
- Compute **excess returns** for risky coins:  
  `rex,t = ri,t − rf,t`

### Risk Estimation — EWMA Covariance
Estimate covariance matrix **Σ** using **Exponentially Weighted Moving Average (EWMA)** with a 60-day half-life.

- Decay factor:  
  `λ = 2^(−1/60)`
- Covariance matrix:  
  `Σt = (1−λ) Σ [λ^(k−1) * (r_ex,t−k − r̄)(r_ex,t−k − r̄)ᵀ]`

### Expected Excess Returns — Momentum + Shrinkage
- **Momentum:**  
  `mi,t = Σₖ₌₁⁶⁰ r_ex,t−k`
- **Shrinkage to avoid overfitting:**  
  `μi,t = γ * mi,t`, where `γ = 0.1`

### Optimal Sharpe (Tangency) Direction
- Compute **tangency vector:**  
  `gt ∝ Σt⁻¹ μt`  
  (Set negatives in gt → 0)
- Normalize to sum to 1:  
  ```
  if Σ gt > 0:
      gt~ = gt / Σ gt
  else:
      set equal weights
  ```

### Volatility Scaling and Risky Sleeve
- Risky sleeve volatility:  
  `σrisky,t = sqrt(gt~ᵀ Σt gt~)`
- Risk exposure:  
  `xt = min(1, 0.15 / σrisky,t)`
- Target weights:  
  `wcoins,t = xt * gt~`

### Rebalancing Constraints
**20% Bands:**  
If |Δwi| ≤ 0.20 → Δwi = 0

**Turnover Cap 50%:**  
If Σ |Δwi| > 0.5 → scale Δw by (0.5 / Σ |Δwi|)

Round orders to Coinbase’s step sizes and minimum notional limits.

### Cost Modeling & Performance Tracking
- Daily net return:  
  `Rp,t = Σ (wi,t−1 * ri,t) + wUSDC,t−1 * rf,t − fees − slippage`
- Track:
  - Equity curve
  - CAGR
  - Sharpe vs. rf
  - Max drawdown
  - Turnover

---

## Dependencies

### Python Libraries
- **NumPy** — core numerical operations:
  - Array ops & math: `np.array`, `np.log`, `np.diff`, `np.sqrt`, `np.clip`, etc.
  - Linear algebra: `np.linalg.solve`, `np.linalg.eigh`
  - Covariance operations: `np.outer`, `np.tensordot`, `np.einsum`
  - Stability: ridge regularization with `eps * np.eye(N)`
  - Rolling windows: `np.lib.stride_tricks.sliding_window_view` (optional)

### Coinbase REST API Endpoints

**Authentication:** All endpoints use JWT (ES256) authentication with Cloud API Keys

**Account Management:**
- `GET /api/v3/brokerage/accounts` → Retrieve all account balances and available funds

**Market Data:**
- `GET /api/v3/brokerage/products/{product_id}/ticker` → Current best bid/ask and recent trades
- `GET /api/v3/brokerage/products/{product_id}/candles?granularity=ONE_DAY` → Historical OHLCV candles
  - Returns array of candles with: `start`, `open`, `high`, `low`, `close`, `volume`
  - Multiple granularity options: `ONE_DAY`, `DAY`, with optional `&limit=N` parameter

**Trading:**
- `POST /api/v3/brokerage/orders/preview` → Preview order without execution (no capital risk)
  - Returns estimated costs, fees, and sizes before placing real orders
  - Supports market orders with `quote_size` (USD amount) or `base_size` (crypto amount)
- `POST /api/v3/brokerage/orders` → Create and execute buy/sell orders
  - Order types: market (IOC), limit (post-only for maker fees)
- `GET /api/v3/brokerage/orders/{order_id}` → Check order status and fill details

---

## Repository Organization
```
/logs
  ├── back_test_log.json
  ├── data.json
  └── trade_history.json

/execution
  ├── pull_data.py
  ├── globals.py
  ├── optimize_portfolio.py
  ├── rebalance.py
  └── daily_trade.py

/testing
  ├── back_test.py
  ├── back_test_harness.py
  ├── api_test.py
  └── math_test.py
```

---

## Workflow / Deployment

### pull_data.py -date -days
- Fetches price data for each risky coin for *x* days from *y* date
- Updates `data.json`

### globals.py
- Defines:
  - Turnover cap = 50%
  - Rebalance bands = 20%
  - Target volatility = 15%
  - Risk-free rate = 4.10% (manual update)
  - Maker fee = 0.6%
  - Taker fee = 1.2%

### optimize_portfolio.py
- Calculates optimal portfolio given input data
- Outputs preferred weights

### back_test.py -days
- Runs simulation from *x* days in past to present
- Calls:
  - `pull_data.py` for each day
  - `optimize_portfolio.py` for daily optimization
- Outputs:
  - Initial and final portfolios
  - Number of trades
  - Net Sharpe (after fees)
  - Transaction/slippage costs
  - P&L
- Saves results to `back_test_log.json`

### back_test_harness.py
- Runs `back_test.py` over different scenarios to determine preferred window size
- Specify numbers of days to look back with `-days ` tag
  - Test window sizes 15, 30, 45, 60, and 75
  - `back_test.py -days x -window y`
  - Move `back_test_log.json` and `backtest_pnl.png` to `\logs\x day back test` for each back test window
- Compares performance against other baskets - generate graphs on 90 day performances and calculate pnl and volatility
  - Portfolio of equal weights to all coins
  - Portfolio of just BTC
  - Portfolio of just ETH
  - Portfolio of just PAXG
  - Portfolio of just SOL
  - Portfolio gaining interest at risk free rate
- Store summary of results in `back_test_summary.json` in the `\logs\x day back test` directory

### rebalance.py
- Rebalances the portfolio in line with the trading rules
  - Calls the API to systematically trade holdings
- Executes:
  - `pull_data.py` (past 60 days)
  - `optimize_portfolio.py`

### show_optimal_portfolio.py
- Displays optimal portfolio allocation based on latest 60 days of data
- Shows "fresh start" allocation (if starting from zero)
- Useful for checking target weights without rebalance band constraints
- Does not execute any trades

### daily_trade.py
- Runs automatically at **00:00:00 UTC** via `launchd` (macOS) every day
- Executes `rebalance.py`
- Logs:
  - Trades
  - Portfolio weights
  - P&L
  - Total portfolio value
- Sends daily execution summary in an email
  - My portfolio holdings
  - Trades
  - Optimal portfolio
  - Day over day PnL
  - Lifetime PnL

### api_test.py
- Connects to Coinbase API using JWT authentication from `.env`
- Tests 4 core functionalities:
  1. **API Connection** - Retrieves account balances
  2. **Current Prices** - Fetches real-time ticker data for BTC, ETH, PAXG, SOL
  3. **Historical Prices** - Pulls closing prices from 60 days ago using candle data
  4. **Order Preview** - Tests buy order generation for all portfolio products (no capital risk)

### math_test.py
- Runs mathematical validations for `optimize_portfolio.py`

---

## Results

**Backtest period:** 2025-07-20 → 2025-10-17  
**Tested windows:** 15 d, 30 d, 45 d, 60 d, 75 d  
**Initial portfolio value:** \$10,000  
**Assets:** BTC-USDC, ETH-USDC, PAXG-USDC, SOL-USDC, USDC  

All results include transaction fees and slippage.

### Results by Window

#### 15-Day Window  
![Backtest 15](./logs/90%20day%20back%20test/backtest_15.png)  
- **Final value:** \$8 848.49 (−11.52 %)  
- **Sharpe:** 0.457 **Max DD:** 12.63 %  
- **Rebalances:** 34 **Fees:** \$1 494 (14.9 %)  
- **Final allocation:** BTC 12.2 % | ETH 3.9 % | PAXG 27.9 % | SOL 6.0 % | USDC 50.0 %  
> This short-term window was far too reactive—high turnover and heavy costs erased returns.

#### 30-Day Window  
![Backtest 30](./logs/90%20day%20back%20test/backtest_30.png)  
- **Final value:** \$10 649.55 (+6.50 %)  
- **Sharpe:** 1.899 **Max DD:** 7.56 %  
- **Rebalances:** 18 **Fees:** \$723 (7.2 %)  
- **Final allocation:** BTC 23.8 % | ETH 4.3 % | PAXG 64.0 % | SOL 7.9 % | USDC 0 %  
> Moderate improvement—reduced churn stabilized results, driven largely by PAXG exposure.

#### 45-Day Window  
![Backtest 45](./logs/90%20day%20back%20test/backtest_45.png)  
- **Final value:** \$10 524.22 (+5.24 %)  
- **Sharpe:** 1.303 **Max DD:** 8.57 %  
- **Rebalances:** 13 **Fees:** \$469 (4.7 %)  
- **Final allocation:** BTC 14.4 % | ETH 7.2 % | PAXG 33.2 % | SOL 14.7 % | USDC 30.5 %  
> A balanced compromise—still profitable but slightly less efficient than the 30-day version.

#### 60-Day Window  
![Backtest 60](./logs/90%20day%20back%20test/backtest_60.png)  
- **Final value:** \$11 672.24 (+16.72 %)  
- **Sharpe:** 2.904 **Max DD:** 5.35 %  
- **Rebalances:** 11 **Fees:** \$374 (3.7 %)  
- **Final allocation:** BTC 0 % | ETH 9.9 % | PAXG 44.9 % | SOL 0 % | USDC 45.2 %  
> This window achieved the **best overall performance**—highest return, best Sharpe, and low drawdown with minimal turnover.  
> The optimizer consistently leaned into **PAXG** and **USDC**, balancing defensive assets against crypto volatility.

#### 75-Day Window  
![Backtest 75](./logs/90%20day%20back%20test/backtest_75.png)  
- **Final value:** \$11 580.81 (+15.81 %)  
- **Sharpe:** 2.629 **Max DD:** 5.47 %  
- **Rebalances:** 9 **Fees:** \$294 (2.9 %)  
- **Final allocation:** BTC 0 % | ETH 11.8 % | PAXG 53.2 % | SOL 0 % | USDC 35.0 %  
> Slightly lower return than 60 d but similar risk profile. A strong alternative if I prefer an even slower rebalance cadence.

### Window Comparison

| Window | Return | Sharpe | Max DD | Trades | Fees % |
|:--:|--:|--:|--:|--:|--:|
| 15 d | −11.52 % | 0.457 | 12.63 % | 34 | 14.94 % |
| 30 d | +6.50 %  | 1.899 | 7.56 %  | 18 | 7.23 % |
| 45 d | +5.24 %  | 1.303 | 8.57 %  | 13 | 4.69 % |
| **60 d** | **+16.72 %** | **2.904** | **5.35 %** | **11** | **3.74 %** |
| 75 d | +15.81 % | 2.629 | 5.47 % | 9 | 2.94 % |

> **Best Window:** I will deploy the **60-day window**. It produced the highest Sharpe, strong absolute return, and the lowest drawdown among all windows with minimal transaction drag.

### Benchmark Comparison

| Portfolio | Return | Volatility | Sharpe |
|:--|--:|--:|--:|
| Equal-weight (BTC, ETH, PAXG, SOL, USDC) | 3.75 % | 38.74 % | 0.390 |
| BTC-only | −9.47 % | 34.62 % | −1.178 |
| ETH-only | 0.90 % | 73.59 % | 0.050 |
| PAXG-only | 25.58 % | 20.53 % | 4.549 |
| SOL-only | 0.74 % | 86.90 % | 0.035 |
| Risk-free | 1.02 % | 0.00 % | 0.000 |

> The 60-day MVO portfolio outperformed every diversified or crypto-only benchmark except the pure **PAXG** position, which benefited from a strong gold rally during this period.  
> Despite moderate fees, my optimized basket achieved a **higher risk-adjusted return (Sharpe 2.90)** than any single-asset or equal-weight portfolio.

### Key Insights
- **Rebalance Bands:** I had originally set the rebalance bans to 2% but noticed that my trading fees were getting very high (given my high maker and taker fees) even for the 60 and 75 day windows. I experimented with different band sizes but found 20% to generally improve portfolio performance across the board.
- **Risk definition:** Within the MVO framework, risk is modeled as portfolio **volatility**, not directional loss.  
- **Stability:** Longer look-back windows (60 – 75 days) produced smoother allocations, lower turnover, and better out-of-sample behavior.  
- **Asset bias:** The optimizer favored **PAXG + USDC**, signaling capital preservation bias during this 3-month window of crypto uncertainty.  
- **Next steps:** Expand testing to longer periods, PAXG is a relatively new asset, so there is only around 165 days of data on it as of this test.


---

## Licenses

### MIT License
```
MIT License

Copyright (c) 2025 Jack Duncan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Contact
**Name:** Jack Duncan  
**Email:** [jack_duncan@berkeley.edu](mailto:jack_duncan@berkeley.edu)
