"""
back_test.py
Simulate trading strategy on historical data
Usage: python back_test.py [-days N] [-window W]
  -days N: Number of days to simulate (default: 30)
  -window W: Lookback window for optimization (default: 60)
"""

import os
import sys
import json
import numpy as np
import subprocess
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# Add execution directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'execution'))

from optimize_portfolio import optimize_portfolio
from globals import (
    MAKER_FEE, TAKER_FEE, LOOKBACK_DAYS, RISKY_ASSETS,
    TURNOVER_CAP, REBALANCE_BAND, TARGET_VOLATILITY, RISK_FREE_RATE
)

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs', 'data.json')
LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs', 'back_test_log.json')
PLOT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs', 'backtest_pnl.png')
PULL_DATA_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'execution', 'pull_data.py')


def pull_historical_data(num_days, window):
    """Call pull_data.py to fetch window + num_days."""
    total_days = window + num_days
    print(f"Pulling {total_days} days of historical data...")
    venv_python = sys.executable
    result = subprocess.run([venv_python, PULL_DATA_SCRIPT, '-days', str(total_days)], 
                          capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error pulling data: {result.stderr}")
        return False
    return True


def load_price_data():
    """Load price data from data.json."""
    with open(DATA_FILE, 'r') as f:
        return json.load(f)


def get_prices_on_date(data, date_str, lookback_days):
    """
    Get price data for all assets up to and including a specific date.
    
    Args:
        data: Full price data dict
        date_str: Date string 'YYYY-MM-DD'
        lookback_days: Number of days of history to return
    
    Returns:
        Dict of {product: [prices]} or None if insufficient data
    """
    result = {}
    
    for product in RISKY_ASSETS:
        if product not in data:
            return None
        
        # Filter data up to date_str
        prices = [entry for entry in data[product] if entry['date'] <= date_str]
        
        if len(prices) < lookback_days:
            return None
        
        # Get last lookback_days of prices
        result[product] = np.array([p['close'] for p in prices[-lookback_days:]])
    
    return result


def compute_portfolio_value_with_rf(risky_weights, risky_prices, portfolio_value):
    """
    Compute total portfolio value including USDC (risk-free) holdings.
    
    Args:
        risky_weights: Weights allocated to risky assets
        risky_prices: Current prices of risky assets
        portfolio_value: Total portfolio value
    
    Returns:
        Total portfolio value
    """
    risky_allocation = np.sum(risky_weights)  # Total % in risky assets
    return portfolio_value


def compute_transaction_costs(old_weights, new_weights, portfolio_value, fee_rate):
    """
    Compute transaction costs for rebalancing.
    
    Args:
        old_weights: Current portfolio weights
        new_weights: Target portfolio weights
        portfolio_value: Total portfolio value
        fee_rate: Trading fee rate (maker or taker)
    
    Returns:
        Total transaction cost in dollars
    """
    # Turnover is sum of absolute changes in weights
    turnover = np.abs(new_weights - old_weights).sum()
    
    # Cost = turnover * portfolio_value * fee_rate
    return turnover * portfolio_value * fee_rate


def plot_pnl(dates, values, num_days, window):
    """
    Create and save P&L plot.
    
    Args:
        dates: List of date strings
        values: List of portfolio values
        num_days: Number of days in backtest
        window: Optimization window size
    """
    plt.figure(figsize=(12, 6))
    plt.plot(dates, values, linewidth=2, color='#2E86AB')
    plt.axhline(y=values[0], color='gray', linestyle='--', alpha=0.5, label='Initial Value')
    
    plt.title(f'Portfolio P&L - {num_days} Day Backtest (Window: {window} days)', 
              fontsize=14, fontweight='bold')
    plt.xlabel('Date', fontsize=12)
    plt.ylabel('Portfolio Value ($)', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.legend()
    
    # Format y-axis as currency
    ax = plt.gca()
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
    
    # Rotate x-axis labels for readability
    plt.xticks(rotation=45, ha='right')
    
    # Show every nth date label to avoid crowding
    n = max(1, len(dates) // 10)
    ax.set_xticks([dates[i] for i in range(0, len(dates), n)])
    
    plt.tight_layout()
    plt.savefig(PLOT_FILE, dpi=150, bbox_inches='tight')
    plt.close()


def run_backtest(num_days, window=60, initial_value=10000):
    """
    Run backtest simulation.
    
    Args:
        num_days: Number of days to backtest (rebalancing period)
        window: Lookback window for optimization (default: 60)
        initial_value: Starting portfolio value in USD
    
    Returns:
        Dict with backtest results
    """
    print(f"\n{'='*60}")
    print(f"BACKTEST: {num_days} Days | Window: {window} Days")
    print(f"{'='*60}\n")
    
    # Pull data (window + num_days)
    if not pull_historical_data(num_days, window):
        return None
    
    # Load price data
    data = load_price_data()
    
    # Get all available dates (use first product as reference)
    all_dates = sorted([entry['date'] for entry in data[RISKY_ASSETS[0]]])
    
    # Need window for first optimization + num_days for backtest
    required_days = window + num_days
    if len(all_dates) < required_days:
        max_days = len(all_dates) - window
        print(f"Error: Insufficient data. Need {required_days} days, have {len(all_dates)}")
        print(f"\nCoinbase API limit: ~{len(all_dates)} days of historical data")
        print(f"Your request: window={window} + days={num_days} = {required_days} days")
        if max_days > 0:
            print(f"\nSuggestion: With window={window}, maximum days = {max_days}")
            print(f"  Try: python back_test.py -days {max_days} -window {window}")
        else:
            max_window = len(all_dates) - num_days
            print(f"\nSuggestion: With days={num_days}, maximum window = {max(0, max_window)}")
            print(f"  Try: python back_test.py -days {num_days} -window {max(1, max_window)}")
            print(f"  Or try: python back_test.py -days 290 -window 60  (recommended)")
        return None
    
    # Backtest period: last num_days
    backtest_dates = all_dates[-num_days:]
    
    print(f"Backtest period: {backtest_dates[0]} to {backtest_dates[-1]}")
    print(f"Optimization window: {window} days")
    print(f"Initial portfolio value: ${initial_value:,.2f}\n")
    
    # Initialize portfolio: 100% in USDC (risk-free)
    n_assets = len(RISKY_ASSETS)
    risky_weights = np.zeros(n_assets)  # Start with 0% in risky assets
    usdc_weight = 1.0  # 100% in USDC
    portfolio_value = initial_value
    
    # Track metrics
    daily_returns = []
    daily_values = [initial_value]
    daily_dates = [backtest_dates[0]]
    total_trades = 0
    total_fees = 0
    rebalance_log = []
    
    # Daily risk-free rate
    daily_rf = RISK_FREE_RATE / 365
    
    # Run simulation day by day
    for i, date_str in enumerate(backtest_dates):
        # Get historical prices for optimization (window days ending on this date)
        prices_dict = get_prices_on_date(data, date_str, window)
        
        if prices_dict is None:
            print(f"Skipping {date_str}: insufficient data")
            continue
        
        # Current prices (last price in each series)
        current_prices = np.array([prices_dict[asset][-1] for asset in RISKY_ASSETS])
        
        # Calculate returns from previous day
        if len(daily_values) > 0:
            # Get previous day's prices (need to find last valid day)
            prev_date = daily_dates[-1] if daily_dates else backtest_dates[0]
            prev_prices_dict = get_prices_on_date(data, prev_date, window)
            
            # Only calculate returns if we have previous prices
            if prev_prices_dict is not None:
                prev_prices = np.array([prev_prices_dict[asset][-1] for asset in RISKY_ASSETS])
                
                # Price returns for risky assets
                price_returns = current_prices / prev_prices - 1
                
                # Portfolio return: risky assets + USDC
                risky_portfolio_return = np.dot(risky_weights, price_returns)
                usdc_return = usdc_weight * daily_rf
                portfolio_return = risky_portfolio_return + usdc_return
                
                portfolio_value *= (1 + portfolio_return)
                daily_returns.append(portfolio_return)
        
        # Record current portfolio value and date
        daily_values.append(portfolio_value)
        daily_dates.append(date_str)
        
        # Run optimization to get target weights
        try:
            # Convert prices dict to array (n_days, n_assets)
            price_matrix = np.column_stack([prices_dict[asset] for asset in RISKY_ASSETS])
            
            result = optimize_portfolio(price_matrix, current_weights=risky_weights, halflife=window)
            target_risky_weights = result['weights']
            
            # Check if rebalancing occurred
            if not np.allclose(target_risky_weights, risky_weights):
                # Calculate transaction costs (use taker fee for market orders)
                trade_cost = compute_transaction_costs(risky_weights, target_risky_weights, 
                                                      portfolio_value, TAKER_FEE)
                total_fees += trade_cost
                portfolio_value -= trade_cost
                
                total_trades += 1
                rebalance_log.append({
                    'date': date_str,
                    'old_risky_weights': risky_weights.tolist(),
                    'new_risky_weights': target_risky_weights.tolist(),
                    'old_usdc_weight': usdc_weight,
                    'new_usdc_weight': 1.0 - np.sum(target_risky_weights),
                    'cost': trade_cost,
                    'portfolio_value': portfolio_value
                })
                
                # Update weights
                risky_weights = target_risky_weights
                usdc_weight = 1.0 - np.sum(risky_weights)
        
        except Exception as e:
            print(f"Error on {date_str}: {e}")
            continue
    
    # Calculate final metrics
    final_value = daily_values[-1]
    total_return = (final_value - initial_value) / initial_value
    
    # Calculate Sharpe ratio
    if len(daily_returns) > 1:
        excess_returns = np.array(daily_returns) - daily_rf
        sharpe_ratio = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(365)
    else:
        sharpe_ratio = 0
    
    # Calculate max drawdown
    peak = initial_value
    max_dd = 0
    for value in daily_values:
        if value > peak:
            peak = value
        dd = (peak - value) / peak
        if dd > max_dd:
            max_dd = dd
    
    # Create P&L plot
    plot_pnl(daily_dates, daily_values, num_days, window)
    
    # Prepare results
    results = {
        'backtest_period': {
            'start_date': backtest_dates[0],
            'end_date': backtest_dates[-1],
            'num_days': num_days,
            'window': window
        },
        'portfolio': {
            'initial_value': initial_value,
            'final_value': final_value,
            'total_return': total_return,
            'total_return_pct': total_return * 100
        },
        'performance': {
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_dd,
            'max_drawdown_pct': max_dd * 100
        },
        'trading': {
            'num_rebalances': total_trades,
            'total_fees': total_fees,
            'fees_pct_of_initial': (total_fees / initial_value) * 100
        },
        'final_weights': {
            'risky_assets': {asset: float(w) for asset, w in zip(RISKY_ASSETS, risky_weights)},
            'usdc': float(usdc_weight)
        },
        'rebalance_history': rebalance_log
    }
    
    # Print summary
    print(f"\n{'='*60}")
    print("BACKTEST RESULTS")
    print(f"{'='*60}")
    print(f"\nPortfolio:")
    print(f"  Initial value:  ${initial_value:,.2f}")
    print(f"  Final value:    ${final_value:,.2f}")
    print(f"  Total return:   {total_return*100:,.2f}%")
    print(f"\nPerformance:")
    print(f"  Sharpe ratio:   {sharpe_ratio:.3f}")
    print(f"  Max drawdown:   {max_dd*100:.2f}%")
    print(f"\nTrading:")
    print(f"  Rebalances:     {total_trades}")
    print(f"  Total fees:     ${total_fees:,.2f}")
    print(f"  Fees (% initial): {(total_fees/initial_value)*100:.2f}%")
    print(f"\nFinal Allocation:")
    for asset, weight in zip(RISKY_ASSETS, risky_weights):
        print(f"  {asset:12s} {weight*100:6.2f}%")
    print(f"  {'USDC':12s} {usdc_weight*100:6.2f}%")
    print(f"\nPlot saved to: {PLOT_FILE}")
    print(f"{'='*60}\n")
    
    return results


def main():
    """Main entry point with CLI argument parsing."""
    num_days = 30  # Default to 30 days
    window = 60  # Default to 60 days window
    
    # Parse arguments
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '-days' and i + 1 < len(sys.argv):
            try:
                num_days = int(sys.argv[i + 1])
                i += 2
            except ValueError:
                print(f"Error: Invalid days value. Use integer.")
                sys.exit(1)
        elif sys.argv[i] == '-window' and i + 1 < len(sys.argv):
            try:
                window = int(sys.argv[i + 1])
                i += 2
            except ValueError:
                print(f"Error: Invalid window value. Use integer.")
                sys.exit(1)
        else:
            print(f"Usage: python back_test.py [-days N] [-window W]")
            sys.exit(1)
    
    # Run backtest
    results = run_backtest(num_days, window)
    
    if results:
        # Save to log file
        with open(LOG_FILE, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to {LOG_FILE}")


if __name__ == '__main__':
    main()
