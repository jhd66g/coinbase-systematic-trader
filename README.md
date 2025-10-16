
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

### Euro Stable Coin (EURC)
- Current Price ≈ **$1.16**
- All-Time High ≈ **$1.1872** (September 17, 2025)
- Market Cap ≈ **$266 million**

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
- Rebalance bands: **±2%**
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
**2% Bands:**  
If |Δwi| ≤ 0.02 → Δwi = 0

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
- `/api/v3/brokerage/accounts` → balances & USD value
- `/api/v3/brokerage/products/<product_id>/ticker` → current spot price
- `/api/v3/brokerage/products/{product_id}/candles` → historical price data
- `/api/v3/brokerage/orders` → create buy/sell orders
- `/api/v3/brokerage/orders/<order_id>` → confirm order status

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
  └── daily_trade.py

/testing
  ├── back_test.py
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
  - Rebalance bands = 2%
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

### daily_trade.py
- Runs automatically at **00:00:00 UTC** via `launchd` (macOS)
- Executes:
  - `pull_data.py` (past 60 days)
  - `optimize_portfolio.py`
  - Rebalances portfolio if within trading rules
- Logs:
  - Trades
  - Portfolio weights
  - P&L
  - Total portfolio value

### api_test.py
- Connects to Coinbase API using secrets in `.env`
- Pulls current and historical prices

### math_test.py
- Runs mathematical validations for `optimize_portfolio.py`

---

## Results

### Backtest Setup
- Historical backtest from 1 year ago to present
- Compare window sizes: **30, 60, 90, 180 days**
- Output includes:
  - Initial & final portfolio
  - Trades made
  - Net Sharpe (after fees)
  - Fees/slippage losses
  - P&L

### Comparison Benchmarks
- Equal-weight portfolio
- BTC-only
- ETH-only
- PAXG-only
- Risk-free (USDC interest)
- S&P 500

Include **graphs** of volatility and P&L, plus **written analysis**.

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
