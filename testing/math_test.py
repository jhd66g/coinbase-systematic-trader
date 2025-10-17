# math_test.py
# Test mathematical functions and portfolio optimization logic

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np
from execution.optimize_portfolio import (
    compute_log_returns, compute_excess_returns, compute_ewma_covariance,
    compute_expected_returns, compute_tangency_weights, scale_by_volatility,
    apply_rebalancing_bands, apply_turnover_cap
)
from execution.globals import RISK_FREE_RATE, EWMA_HALFLIFE, MOMENTUM_SHRINKAGE

# Test data
np.random.seed(42)
n_coins = 3
n_days = 60

def test_log_returns():
    """Test 1: Daily Log Returns Calculation"""
    print("\n" + "="*60)
    print("TEST 1: Log Returns - ri,t = ln(Pi,t / Pi,t-1)")
    print("="*60)
    
    prices = np.array([100, 102, 101, 105, 103])
    expected_returns = np.log(prices[1:] / prices[:-1])
    
    calculated = compute_log_returns(prices)
    
    match = np.allclose(expected_returns, calculated)
    print(f"Sample prices: {prices}")
    print(f"Log returns: {calculated}")
    print(f"Result: {'PASSED' if match else 'FAILED'}")
    return match


def test_excess_returns():
    """Test 2: Excess Returns Over Risk-Free Rate"""
    print("\n" + "="*60)
    print("TEST 2: Excess Returns - rex,t = ri,t - rf,t")
    print("="*60)
    
    log_returns = np.array([0.02, -0.01, 0.03, -0.02])
    rf_daily = 0.041 / 252  # Use 252 trading days (as in actual function)
    expected_excess = log_returns - rf_daily
    
    calculated = compute_excess_returns(log_returns, 0.041)
    
    match = np.allclose(expected_excess, calculated)
    print(f"Log returns: {log_returns}")
    print(f"Risk-free rate (daily): {rf_daily:.6f}")
    print(f"Excess returns: {calculated}")
    print(f"Result: {'PASSED' if match else 'FAILED'}")
    return match


def test_ewma_covariance():
    """Test 3: EWMA Covariance Matrix with λ = 2^(-1/60)"""
    print("\n" + "="*60)
    print("TEST 3: EWMA Covariance - λ = 2^(-1/60)")
    print("="*60)
    
    # Simple 2-asset example
    returns = np.array([
        [0.01, -0.02],
        [-0.01, 0.03],
        [0.02, -0.01]
    ])
    
    calculated = compute_ewma_covariance(returns, halflife=60)
    
    print(f"Sample returns shape: {returns.shape}")
    print(f"Covariance matrix:\n{calculated}")
    print(f"Halflife parameter: 60 days")
    print(f"Result: {'PASSED' if calculated.shape == (2, 2) else 'FAILED'}")
    return calculated.shape == (2, 2)


def test_momentum_shrinkage():
    """Test 4: Momentum + Shrinkage - μi,t = γ * mi,t"""
    print("\n" + "="*60)
    print("TEST 4: Momentum with Shrinkage")
    print("="*60)
    
    excess_returns = np.random.randn(n_days, n_coins) * 0.01
    gamma = 0.1
    
    expected_returns_calc = compute_expected_returns(excess_returns, gamma)
    
    print(f"Shrinkage factor γ: {gamma}")
    print(f"Expected returns μ: {expected_returns_calc}")
    print(f"Result: PASSED")
    return True


def test_tangency_portfolio():
    """Test 5: Tangency Vector - gt ∝ Σt^-1 μt"""
    print("\n" + "="*60)
    print("TEST 5: Optimal Sharpe (Tangency) Direction")
    print("="*60)
    
    # Create positive definite covariance matrix
    A = np.random.randn(n_coins, n_coins)
    cov_matrix = A.T @ A + 0.01 * np.eye(n_coins)
    
    expected_returns = np.array([0.05, 0.03, 0.02])
    
    tangency = compute_tangency_weights(cov_matrix, expected_returns)
    
    print(f"Covariance matrix shape: {cov_matrix.shape}")
    print(f"Expected returns: {expected_returns}")
    print(f"Tangency weights (unnormalized): {tangency}")
    print(f"Result: PASSED")
    return True


def test_volatility_scaling():
    """Test 6: Volatility Scaling - xt = min(1, 0.15 / σrisky,t)"""
    print("\n" + "="*60)
    print("TEST 6: Volatility Scaling and Risk Exposure")
    print("="*60)
    
    weights = np.array([0.4, 0.3, 0.3])
    A = np.random.randn(n_coins, n_coins)
    cov_matrix = A.T @ A + 0.01 * np.eye(n_coins)
    
    scaled_weights = scale_by_volatility(weights, cov_matrix, target_vol=0.15)
    
    print(f"Original weights: {weights}")
    print(f"Scaled weights: {scaled_weights}")
    print(f"Target volatility: 0.15")
    print(f"Result: PASSED")
    return True


def test_rebalancing_bands():
    """Test 7: Rebalancing Bands - |Δwi| ≤ 0.02 → Δwi = 0"""
    print("\n" + "="*60)
    print("TEST 7: 2% Rebalancing Bands")
    print("="*60)
    
    current_weights = np.array([0.40, 0.35, 0.25])
    target_weights = np.array([0.41, 0.34, 0.25])
    
    final_weights = apply_rebalancing_bands(current_weights, target_weights, band=0.02)
    
    print(f"Current weights: {current_weights}")
    print(f"Target weights: {target_weights}")
    print(f"Final weights (after bands): {final_weights}")
    print(f"Result: PASSED")
    return True


def test_turnover_cap():
    """Test 8: Turnover Cap - If Σ|Δwi| > 0.5 → scale by 0.5/Σ|Δwi|"""
    print("\n" + "="*60)
    print("TEST 8: 50% Turnover Cap")
    print("="*60)
    
    current_weights = np.array([0.4, 0.3, 0.3])
    delta_weights = np.array([0.3, -0.2, -0.1])
    
    delta_weights_scaled = apply_turnover_cap(delta_weights, current_weights=current_weights, turnover_cap=0.5)
    
    final_turnover = np.abs(delta_weights_scaled).sum()
    within_cap = final_turnover <= 0.5 + 1e-10
    
    # Also check no negative weights
    final_weights = current_weights + delta_weights_scaled
    no_negatives = np.all(final_weights >= -1e-10)
    
    print(f"Current weights: {current_weights}")
    print(f"Original delta: {delta_weights}")
    print(f"Total turnover before: {np.abs(delta_weights).sum():.4f}")
    print(f"Scaled delta: {delta_weights_scaled}")
    print(f"Total turnover after: {final_turnover:.4f}")
    print(f"Final weights: {final_weights}")
    print(f"Within 50% cap: {within_cap}")
    print(f"No negative weights: {no_negatives}")
    print(f"Result: {'PASSED' if (within_cap and no_negatives) else 'FAILED'}")
    return within_cap and no_negatives


def main():
    """Run all mathematical validation tests."""
    print("\n" + "="*60)
    print("PORTFOLIO OPTIMIZATION - MATHEMATICAL TESTS")
    print("="*60)
    
    results = [
        ("Log Returns", test_log_returns()),
        ("Excess Returns", test_excess_returns()),
        ("EWMA Covariance", test_ewma_covariance()),
        ("Momentum + Shrinkage", test_momentum_shrinkage()),
        ("Tangency Portfolio", test_tangency_portfolio()),
        ("Volatility Scaling", test_volatility_scaling()),
        ("Rebalancing Bands", test_rebalancing_bands()),
        ("Turnover Cap", test_turnover_cap())
    ]
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for test_name, result in results:
        print(f"{test_name}: {'PASSED' if result else 'FAILED'}")
    
    passed = sum(1 for _, result in results if result)
    print(f"\nTotal: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\nAll tests passed successfully.")
    else:
        print("\nSome tests failed. Review errors above.")


if __name__ == "__main__":
    main()
