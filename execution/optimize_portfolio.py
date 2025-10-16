# optimize_portfolio.py
# Implement Markowitz MVO, EWMA covariance, and portfolio optimization

import numpy as np
from globals import (
    RISK_FREE_RATE, TARGET_VOLATILITY, REBALANCE_BAND, 
    TURNOVER_CAP, EWMA_HALFLIFE, MOMENTUM_SHRINKAGE
)


def compute_log_returns(prices):
    """
    Compute daily log returns: ri,t = ln(Pi,t / Pi,t-1)
    
    Args:
        prices: Array of shape (n_days, n_assets) or (n_days,)
    
    Returns:
        Log returns array of shape (n_days-1, n_assets) or (n_days-1,)
    """
    return np.diff(np.log(prices), axis=0)


def compute_excess_returns(returns, rf_annual=None, rf_daily=None):
    """
    Compute excess returns: rex,t = ri,t - rf,t
    
    Args:
        returns: Asset returns array
        rf_annual: Annual risk-free rate (default: RISK_FREE_RATE)
        rf_daily: Daily risk-free rate (overrides rf_annual if provided)
    
    Returns:
        Excess returns array
    """
    if rf_daily is None:
        if rf_annual is None:
            rf_annual = RISK_FREE_RATE
        rf_daily = rf_annual / 252  # Use 252 trading days
    return returns - rf_daily


def compute_ewma_covariance(excess_returns, halflife=None):
    """
    Compute EWMA covariance matrix: Σt = (1-λ) Σ [λ^(k-1) * (r_ex,t-k - r̄)(r_ex,t-k - r̄)ᵀ]
    
    Args:
        excess_returns: Array of shape (n_days, n_assets)
        halflife: Half-life for decay (default: EWMA_HALFLIFE)
    
    Returns:
        Covariance matrix of shape (n_assets, n_assets)
    """
    if halflife is None:
        halflife = EWMA_HALFLIFE
    
    lambda_decay = 2 ** (-1 / halflife)
    n_days, n_assets = excess_returns.shape
    
    mean_return = excess_returns.mean(axis=0)
    cov_matrix = np.zeros((n_assets, n_assets))
    
    for t in range(n_days):
        deviation = excess_returns[t] - mean_return
        weight = lambda_decay ** (n_days - 1 - t)
        cov_matrix += weight * np.outer(deviation, deviation)
    
    cov_matrix *= (1 - lambda_decay)
    
    # Add small ridge for numerical stability
    cov_matrix += 1e-8 * np.eye(n_assets)
    
    return cov_matrix


def compute_expected_returns(excess_returns, shrinkage=None):
    """
    Compute expected returns using momentum + shrinkage: μi,t = γ * mi,t
    where mi,t = Σₖ₌₁⁶⁰ r_ex,t-k
    
    Args:
        excess_returns: Array of shape (n_days, n_assets)
        shrinkage: Shrinkage factor γ (default: MOMENTUM_SHRINKAGE)
    
    Returns:
        Expected returns array of shape (n_assets,)
    """
    if shrinkage is None:
        shrinkage = MOMENTUM_SHRINKAGE
    
    momentum = excess_returns.sum(axis=0)
    expected_returns = shrinkage * momentum
    
    return expected_returns


def compute_tangency_weights(cov_matrix, expected_returns):
    """
    Compute tangency portfolio weights: gt ∝ Σt⁻¹ μt
    Set negatives to 0 and normalize to sum to 1.
    
    Args:
        cov_matrix: Covariance matrix of shape (n_assets, n_assets)
        expected_returns: Array of shape (n_assets,)
    
    Returns:
        Normalized weights array of shape (n_assets,)
    """
    # Solve for tangency vector
    tangency = np.linalg.solve(cov_matrix, expected_returns)
    
    # Set negatives to zero (long-only constraint)
    tangency[tangency < 0] = 0
    
    # Normalize to sum to 1
    if tangency.sum() > 0:
        weights = tangency / tangency.sum()
    else:
        # Equal weights fallback
        weights = np.ones(len(expected_returns)) / len(expected_returns)
    
    return weights


def scale_by_volatility(weights, cov_matrix, target_vol=None):
    """
    Scale portfolio by target volatility: xt = min(1, target_vol / σrisky,t)
    where σrisky,t = sqrt(gt~ᵀ Σt gt~)
    
    Args:
        weights: Portfolio weights array
        cov_matrix: Covariance matrix
        target_vol: Target volatility (default: TARGET_VOLATILITY)
    
    Returns:
        Scaled weights and risk exposure factor
    """
    if target_vol is None:
        target_vol = TARGET_VOLATILITY
    
    # Compute portfolio volatility (annualized)
    portfolio_variance = weights.T @ cov_matrix @ weights
    portfolio_vol = np.sqrt(portfolio_variance * 365)  # Annualize (365 trading days)

    # Risk exposure scaling
    risk_exposure = min(1.0, target_vol / portfolio_vol) if portfolio_vol > 0 else 1.0
    
    scaled_weights = risk_exposure * weights
    
    return scaled_weights, risk_exposure


def apply_rebalancing_bands(target_weights, current_weights, band=None):
    """
    Apply rebalancing bands: If |Δwi| ≤ band → Δwi = 0
    
    Args:
        target_weights: Target portfolio weights
        current_weights: Current portfolio weights
        band: Rebalancing band threshold (default: REBALANCE_BAND)
    
    Returns:
        Delta weights after applying bands
    """
    if band is None:
        band = REBALANCE_BAND
    
    delta_weights = target_weights - current_weights
    delta_weights[np.abs(delta_weights) <= band] = 0
    
    return delta_weights


def apply_turnover_cap(delta_weights, turnover_cap=None):
    """
    Apply turnover cap: If Σ|Δwi| > cap → scale Δw by (cap / Σ|Δwi|)
    
    Args:
        delta_weights: Portfolio weight changes
        turnover_cap: Maximum turnover allowed (default: TURNOVER_CAP)
    
    Returns:
        Scaled delta weights
    """
    if turnover_cap is None:
        turnover_cap = TURNOVER_CAP
    
    total_turnover = np.abs(delta_weights).sum()
    
    if total_turnover > turnover_cap:
        scale_factor = turnover_cap / total_turnover
        delta_weights = delta_weights * scale_factor
    
    return delta_weights


def optimize_portfolio(prices, current_weights=None):
    """
    Main optimization function: compute optimal portfolio weights.
    
    Args:
        prices: Price array of shape (n_days, n_assets)
        current_weights: Current portfolio weights (optional)
    
    Returns:
        dict with:
            - 'weights': Optimal portfolio weights
            - 'delta_weights': Weight changes (if current_weights provided)
            - 'expected_returns': Expected returns
            - 'cov_matrix': Covariance matrix
            - 'portfolio_vol': Portfolio volatility
            - 'risk_exposure': Risk exposure factor
    """
    # Step 1: Compute log returns
    returns = compute_log_returns(prices)
    
    # Step 2: Compute excess returns
    excess_returns = compute_excess_returns(returns)
    
    # Step 3: Compute EWMA covariance
    cov_matrix = compute_ewma_covariance(excess_returns)
    
    # Step 4: Compute expected returns (momentum + shrinkage)
    expected_returns = compute_expected_returns(excess_returns)
    
    # Step 5: Compute tangency weights
    tangency_weights = compute_tangency_weights(cov_matrix, expected_returns)
    
    # Step 6: Scale by target volatility
    scaled_weights, risk_exposure = scale_by_volatility(tangency_weights, cov_matrix)
    
    # Step 7: Apply rebalancing constraints (if current weights provided)
    delta_weights = None
    final_weights = scaled_weights
    
    if current_weights is not None:
        delta_weights = apply_rebalancing_bands(scaled_weights, current_weights)
        delta_weights = apply_turnover_cap(delta_weights)
        final_weights = current_weights + delta_weights
    
    # Compute final portfolio volatility
    portfolio_variance = final_weights.T @ cov_matrix @ final_weights
    portfolio_vol = np.sqrt(portfolio_variance * 365)
    
    return {
        'weights': final_weights,
        'delta_weights': delta_weights,
        'expected_returns': expected_returns,
        'cov_matrix': cov_matrix,
        'portfolio_vol': portfolio_vol,
        'risk_exposure': risk_exposure
    }
