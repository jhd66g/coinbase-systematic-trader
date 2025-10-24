# globals.py
# Define global constants and configuration parameters

# Trading constraints
TURNOVER_CAP = 0.50  # Maximum 50% turnover per rebalance
REBALANCE_BAND = 0.20  # ±20% rebalancing bands
TARGET_VOLATILITY = 0.15  # 15% annualized volatility target

# Risk-free rate
RISK_FREE_RATE = 0.0385  # 4.10% annualized APY (USDC yield on Coinbase)

# Trading fees
MAKER_FEE = 0.006  # 0.6% maker fee
TAKER_FEE = 0.012  # 1.2% taker fee

# Portfolio optimization parameters
LOOKBACK_DAYS = 60  # Days of historical data for optimization
EWMA_HALFLIFE = 60  # Half-life for EWMA covariance (days)
MOMENTUM_SHRINKAGE = 0.1  # Shrinkage factor γ for expected returns

# Portfolio products
RISKY_ASSETS = ['BTC-USDC', 'ETH-USDC', 'PAXG-USDC', 'SOL-USDC']
RISK_FREE_ASSET = 'USDC'
