"""
back_test_harness.py
Runs back_test.py over different scenarios to determine preferred window size
Usage: python back_test_harness.py -days <days_to_lookback>
"""

import subprocess
import shutil
import json
import os
import sys
from pathlib import Path

def run_window_tests(days):
    """Run backtests with different window sizes"""
    WINDOWS = [15, 30, 45, 60, 75]
    PYTHON = Path(__file__).parent.parent / 'venv' / 'bin' / 'python'
    BACKTEST_SCRIPT = Path(__file__).parent / 'back_test.py'
    LOGS_DIR = Path(__file__).parent.parent / 'logs'
    OUTPUT_DIR = LOGS_DIR / f'{days} day back test'
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*70}")
    print(f"RUNNING WINDOW TESTS: {days} Days Back")
    print(f"{'='*70}\n")
    
    for window in WINDOWS:
        print(f"Testing window={window}...")
        cmd = [str(PYTHON), str(BACKTEST_SCRIPT), '-days', str(days), '-window', str(window)]
        subprocess.run(cmd, cwd=BACKTEST_SCRIPT.parent.parent)
        
        # Move files
        shutil.copy2(LOGS_DIR / 'backtest_pnl.png', OUTPUT_DIR / f'backtest_{window}.png')
        shutil.copy2(LOGS_DIR / 'back_test_log.json', OUTPUT_DIR / f'back_test_log_{window}.json')
        print(f"  ✓ Saved results for window={window}\n")

def run_benchmark_tests(days):
    """Run benchmark portfolio tests"""
    PYTHON = Path(__file__).parent.parent / 'venv' / 'bin' / 'python'
    LOGS_DIR = Path(__file__).parent.parent / 'logs'
    OUTPUT_DIR = LOGS_DIR / f'{days} day back test'
    DATA_FILE = LOGS_DIR / 'data.json'
    
    print(f"\n{'='*70}")
    print(f"RUNNING BENCHMARK TESTS")
    print(f"{'='*70}\n")
    
    # Load price data
    with open(DATA_FILE, 'r') as f:
        data = json.load(f)
    
    from globals import RISKY_ASSETS, RISK_FREE_RATE
    
    # Get dates for the period
    first_asset_data = data[RISKY_ASSETS[0]]
    all_dates = sorted([item['date'] for item in first_asset_data])
    test_dates = all_dates[-days:]
    
    initial_value = 10000.0
    results = {}
    
    # Equal-weight portfolio
    print("Testing equal-weight portfolio...")
    pnl = simulate_equal_weight(data, test_dates, initial_value)
    results['equal_weight'] = pnl
    
    # Single-asset portfolios
    for asset in RISKY_ASSETS:
        print(f"Testing {asset}-only portfolio...")
        pnl = simulate_single_asset(data, asset, test_dates, initial_value)
        results[f'{asset}_only'] = pnl
    
    # Risk-free rate
    print("Testing risk-free rate...")
    rf_daily = RISK_FREE_RATE / 365
    final_value = initial_value * ((1 + rf_daily) ** days)
    results['risk_free'] = {
        'initial': initial_value,
        'final': final_value,
        'return_pct': ((final_value - initial_value) / initial_value) * 100,
        'volatility': 0.0,
        'sharpe': 0.0
    }
    
    # Save benchmark results
    with open(OUTPUT_DIR / 'benchmark_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✓ Benchmark results saved\n")
    return results

def simulate_equal_weight(data, dates, initial_value):
    """Simulate equal-weight portfolio - BUY AND HOLD (no rebalancing)"""
    from globals import RISKY_ASSETS
    import numpy as np
    
    # Initial allocation: 20% each to BTC, ETH, PAXG, SOL, USDC
    n_assets = len(RISKY_ASSETS) + 1  # +1 for USDC
    initial_allocation = initial_value / n_assets
    
    # Track each holding separately (no rebalancing)
    holdings = {asset: initial_allocation for asset in RISKY_ASSETS}
    holdings['USDC'] = initial_allocation
    
    portfolio_values = [initial_value]
    
    for i in range(1, len(dates)):
        # Calculate current value of each holding
        total_value = 0
        
        for asset in RISKY_ASSETS:
            prices = {item['date']: item['close'] for item in data[asset]}
            if dates[i-1] in prices and dates[i] in prices:
                # Holdings grow/shrink with price
                price_ratio = prices[dates[i]] / prices[dates[i-1]]
                holdings[asset] = holdings[asset] * price_ratio
                total_value += holdings[asset]
            else:
                total_value += holdings[asset]
        
        # USDC grows with risk-free rate
        from globals import RISK_FREE_RATE
        rf_daily = RISK_FREE_RATE / 365
        holdings['USDC'] = holdings['USDC'] * (1 + rf_daily)
        total_value += holdings['USDC']
        
        portfolio_values.append(total_value)
    
    # Calculate returns from portfolio values
    returns = np.diff(np.log(portfolio_values))
    
    return {
        'initial': initial_value,
        'final': portfolio_values[-1],
        'return_pct': ((portfolio_values[-1] - initial_value) / initial_value) * 100,
        'volatility': float(np.std(returns) * np.sqrt(365)),
        'sharpe': float(np.mean(returns) / np.std(returns) * np.sqrt(365)) if np.std(returns) > 0 else 0
    }

def simulate_single_asset(data, asset, dates, initial_value):
    """Simulate single-asset portfolio - BUY AND HOLD (no trading)"""
    import numpy as np
    
    prices = {item['date']: item['close'] for item in data[asset]}
    
    # Calculate portfolio value over time based on price changes
    portfolio_values = [initial_value]
    
    for i in range(1, len(dates)):
        if dates[i-1] in prices and dates[i] in prices:
            price_ratio = prices[dates[i]] / prices[dates[i-1]]
            portfolio_values.append(portfolio_values[-1] * price_ratio)
        else:
            portfolio_values.append(portfolio_values[-1])
    
    # Calculate returns from portfolio values
    returns = np.diff(np.log(portfolio_values))
    
    return {
        'initial': initial_value,
        'final': portfolio_values[-1],
        'return_pct': ((portfolio_values[-1] - initial_value) / initial_value) * 100,
        'volatility': float(np.std(returns) * np.sqrt(365)),
        'sharpe': float(np.mean(returns) / np.std(returns) * np.sqrt(365)) if np.std(returns) > 0 else 0
    }

def generate_summary(days):
    """Generate summary comparing all tests"""
    LOGS_DIR = Path(__file__).parent.parent / 'logs'
    OUTPUT_DIR = LOGS_DIR / f'{days} day back test'
    
    print(f"\n{'='*70}")
    print(f"GENERATING SUMMARY")
    print(f"{'='*70}\n")
    
    summary = {'windows': {}, 'benchmarks': {}}
    
    # Load window results
    for window in [15, 30, 45, 60, 75]:
        json_file = OUTPUT_DIR / f'back_test_log_{window}.json'
        if json_file.exists():
            with open(json_file, 'r') as f:
                data = json.load(f)
            summary['windows'][window] = {
                'return_pct': data['portfolio']['total_return_pct'],
                'sharpe': data['performance']['sharpe_ratio'],
                'max_drawdown_pct': data['performance']['max_drawdown_pct'],
                'num_rebalances': data['trading']['num_rebalances'],
                'fees_pct': data['trading']['fees_pct_of_initial']
            }
    
    # Load benchmark results
    benchmark_file = OUTPUT_DIR / 'benchmark_results.json'
    if benchmark_file.exists():
        with open(benchmark_file, 'r') as f:
            summary['benchmarks'] = json.load(f)
    
    # Save summary
    with open(OUTPUT_DIR / 'back_test_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"✓ Summary saved to {OUTPUT_DIR / 'back_test_summary.json'}\n")
    print_summary_table(summary)

def print_summary_table(summary):
    """Print formatted summary table"""
    print(f"\n{'='*70}")
    print("WINDOW COMPARISON")
    print(f"{'='*70}")
    print(f"{'Window':>8} {'Return':>10} {'Sharpe':>8} {'Max DD':>8} {'Trades':>8} {'Fees %':>8}")
    print("-"*70)
    
    for window, data in sorted(summary['windows'].items()):
        print(f"{window:>7}d {data['return_pct']:>9.2f}% {data['sharpe']:>8.3f} "
              f"{data['max_drawdown_pct']:>7.2f}% {data['num_rebalances']:>8} {data['fees_pct']:>7.2f}%")
    
    print(f"\n{'='*70}")
    print("BENCHMARK COMPARISON")
    print(f"{'='*70}")
    print(f"{'Portfolio':<20} {'Return':>10} {'Volatility':>12} {'Sharpe':>8}")
    print("-"*70)
    
    for name, data in summary['benchmarks'].items():
        # Volatility is already annualized (0.35 means 35%), so multiply by 100 for display
        vol_pct = data['volatility'] * 100
        print(f"{name:<20} {data['return_pct']:>9.2f}% {vol_pct:>11.2f}% {data['sharpe']:>8.3f}")
    
    print(f"{'='*70}\n")

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] != '-days':
        print("Usage: python back_test_harness.py -days <days_to_lookback>")
        sys.exit(1)
    
    days = int(sys.argv[2])
    
    # Add execution directory to path for imports
    sys.path.insert(0, str(Path(__file__).parent.parent / 'execution'))
    
    run_window_tests(days)
    run_benchmark_tests(days)
    generate_summary(days)
    
    print(f"\n{'='*70}")
    print("HARNESS COMPLETE")
    print(f"{'='*70}\n")
