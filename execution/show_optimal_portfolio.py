"""
show_optimal_portfolio.py
Display the optimal portfolio allocation based on recent price data
"""
import json, sys, subprocess
import numpy as np
from pathlib import Path
from optimize_portfolio import optimize_portfolio
from globals import RISKY_ASSETS

# Pull latest data
print("Fetching latest 60 days of price data...\n")
subprocess.run([sys.executable, str(Path(__file__).parent / 'pull_data.py'), '-days', '60'], 
               capture_output=True)

# Load data
data_file = Path(__file__).parent.parent / 'logs' / 'data.json'
with open(data_file) as f:
    data = json.load(f)

# Build price matrix (same as rebalance.py)
price_matrix = np.array([[item['close'] for item in data[pid][-60:]] for pid in RISKY_ASSETS]).T

# Run optimization WITHOUT current_weights to get unconstrained optimal
# This bypasses rebalancing bands and turnover caps
result_fresh = optimize_portfolio(price_matrix, current_weights=None, halflife=60)

print("="*60)
print("OPTIMAL PORTFOLIO (Unconstrained)")
print("="*60)
print("If starting from scratch with no current holdings\n")

total_risky = np.sum(result_fresh['weights'])
for i, asset in enumerate(RISKY_ASSETS):
    print(f"  {asset:12s} {result_fresh['weights'][i]*100:6.2f}%")
print(f"  {'USDC':12s} {(1-total_risky)*100:6.2f}%")
print("\n" + "="*60 + "\n")
