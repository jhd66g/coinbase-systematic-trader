"""
rebalance.py - Portfolio rebalancer
"""
import os, sys, json, time, subprocess
from datetime import datetime, UTC
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from globals import RISKY_ASSETS
from optimize_portfolio import optimize_portfolio

from dotenv import load_dotenv
import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import jwt as pyjwt

load_dotenv(Path(__file__).parent.parent / '.env')
API_KEY_NAME = os.getenv('COINBASE_API_KEY_NAME')
PRIVATE_KEY = os.getenv('COINBASE_PRIVATE_KEY')
BASE_URL = 'https://api.coinbase.com'

def build_jwt(method, path):
    pk = serialization.load_pem_private_key(PRIVATE_KEY.encode('utf-8'), None, default_backend())
    payload = {'sub': API_KEY_NAME, 'iss': 'coinbase-cloud', 'nbf': int(time.time()), 'exp': int(time.time())+120, 'uri': f"{method} api.coinbase.com{path}"}
    return pyjwt.encode(payload, pk, algorithm='ES256', headers={'kid': API_KEY_NAME, 'nonce': str(int(time.time()))})

def api_get(path):
    headers = {'Authorization': f'Bearer {build_jwt("GET", path)}'}
    r = requests.get(f'{BASE_URL}{path}', headers=headers)
    if r.status_code != 200:
        raise Exception(f"API error: {r.text}")
    return r.json()

def get_balances():
    data = api_get('/api/v3/brokerage/accounts')
    return {acc['currency']: float(acc['available_balance']['value']) for acc in data['accounts']}

def get_prices():
    prices = {}
    for pid in RISKY_ASSETS:
        data = api_get(f'/api/v3/brokerage/products/{pid}/ticker')
        prices[pid] = float(data.get('price') or data.get('best_bid') or data.get('best_ask', 0))
        time.sleep(0.1)
    return prices

def execute_order(product_id, side, base_size):
    ticker = api_get(f'/api/v3/brokerage/products/{product_id}/ticker')
    price = float(ticker['best_ask' if side=='buy' else 'best_bid'] or ticker['price'])
    base_size = round(base_size, 5)
    
    # For BTC, use 8 decimals
    if 'BTC' in product_id:
        base_size = round(base_size, 8)
    
    jwt_token = build_jwt('POST', '/api/v3/brokerage/orders')
    order = {
        'client_order_id': f"{int(time.time())}-{product_id}-{side}",
        'product_id': product_id,
        'side': side.upper(),
        'order_configuration': {'limit_limit_gtc': {'base_size': f"{base_size:.8f}" if 'BTC' in product_id else f"{base_size:.5f}", 'limit_price': f"{price:.2f}", 'post_only': False}}
    }
    r = requests.post(f'{BASE_URL}/api/v3/brokerage/orders', headers={'Authorization': f'Bearer {jwt_token}', 'Content-Type': 'application/json'}, json=order)
    if r.status_code not in [200,201]:
        raise Exception(f"Order failed: {r.text}")
    result = r.json()
    if result.get('success') is False:
        raise Exception(f"Rejected: {result.get('error_response',{}).get('message','Unknown')}")
    return result['success_response']['order_id']

def rebalance():
    print("\n"+"="*70+"\nPORTFOLIO REBALANCER\n"+"="*70)
    print(f"Timestamp: {datetime.now(UTC).isoformat()}\n")
    
    # Step 1: Current holdings
    print("STEP 1: Current Holdings\n"+"-"*70)
    balances = get_balances()
    prices = get_prices()
    
    holdings = {}
    total = 0
    for pid in RISKY_ASSETS:
        qty = balances.get(pid.split('-')[0], 0)
        val = qty * prices[pid]
        holdings[pid] = {'qty': qty, 'val': val}
        total += val
    
    usdc = balances.get('USDC', 0)
    holdings['USDC'] = {'qty': usdc, 'val': usdc}
    total += usdc
    
    current_weights = np.array([holdings[p]['val']/total for p in RISKY_ASSETS])
    
    print(f"Total: ${total:,.2f}\n")
    for pid in RISKY_ASSETS:
        print(f"  {pid:10} {holdings[pid]['qty']:>12.8f} @ ${prices[pid]:>10,.2f} = ${holdings[pid]['val']:>9,.2f} ({holdings[pid]['val']/total*100:>5.2f}%)")
    print(f"  {'USDC':10} {usdc:>12.2f} {' ':>13} = ${usdc:>9,.2f} ({usdc/total*100:>5.2f}%)")
    
    # Step 2: Optimize
    print("\n"+"="*70+"\nSTEP 2: Running Optimization\n"+"-"*70)
    subprocess.run([sys.executable, str(Path(__file__).parent/'pull_data.py'), '-days', '60'], capture_output=True)
    
    with open(Path(__file__).parent.parent/'logs'/'data.json') as f:
        data = json.load(f)
    
    price_matrix = np.array([[item['close'] for item in data[pid][-60:]] for pid in RISKY_ASSETS]).T
    result = optimize_portfolio(price_matrix, current_weights=current_weights, halflife=60)
    target_weights = result['weights']
    delta_weights = result['delta_weights']
    
    print("\nOptimal Allocation:")
    for i,pid in enumerate(RISKY_ASSETS):
        print(f"  {pid:12} {target_weights[i]*100:6.2f}% (Δ {delta_weights[i]*100:+6.2f}%)")
    print(f"  {'USDC':12} {(1-np.sum(target_weights))*100:6.2f}% (Δ {((1-np.sum(target_weights))-usdc/total)*100:+6.2f}%)")
    
    # Step 3: Execute
    print("\n"+"="*70+"\nSTEP 3: Executing Trades\n"+"-"*70)
    turnover = np.sum(np.abs(delta_weights))
    print(f"Turnover: {turnover*100:.2f}%\n")
    
    trades = []
    
    if turnover < 0.001:
        print("✓ No rebalance needed\n"+"="*70)
        # Still log even when no trades
        history_file = Path(__file__).parent.parent/'logs'/'trade_history.json'
        history = []
        if history_file.exists():
            with open(history_file) as f:
                c = f.read().strip()
                if c and c != '{}':
                    history = json.loads(c)
                    if isinstance(history, dict):
                        history = []
        
        usdc_target_weight = 1 - np.sum(target_weights)
        log_entry = {
            'timestamp': datetime.now(UTC).isoformat(),
            'portfolio_value': total,
            'current_weights': {pid: holdings[pid]['val']/total for pid in RISKY_ASSETS},
            'current_usdc_weight': usdc/total,
            'target_weights': {pid: float(target_weights[i]) for i, pid in enumerate(RISKY_ASSETS)},
            'target_usdc_weight': float(usdc_target_weight),
            'total_turnover': float(turnover),
            'trades': [],
            'final_weights': {pid: holdings[pid]['val']/total for pid in RISKY_ASSETS},
            'final_usdc_weight': usdc/total
        }
        history.append(log_entry)
        with open(history_file, 'w') as f:
            json.dump(history, f, indent=2)
        return
    
    # Sells first
    for i,pid in enumerate(RISKY_ASSETS):
        if delta_weights[i] < -0.001:
            sell_qty = holdings[pid]['qty'] - (target_weights[i]*total)/prices[pid]
            print(f"SELL {sell_qty:.8f} {pid.split('-')[0]} (${abs(delta_weights[i])*total:.2f})")
            try:
                oid = execute_order(pid, 'sell', sell_qty)
                print(f"  ✓ {oid}\n")
                trades.append({'pid': pid, 'side': 'sell', 'qty': sell_qty, 'oid': oid})
                time.sleep(0.5)
            except Exception as e:
                print(f"  ✗ {e}\n")
    
    if trades:
        print("Waiting for settlement...\n")
        time.sleep(5)  # Increased wait time for settlement
        balances = get_balances()
        usdc = balances.get('USDC', 0)
        print(f"Available USDC after sells: ${usdc:.2f}\n")
    
    # Buys - using USDC pairs
    balances = get_balances()
    usdc_balance = balances.get('USDC', 0)
    print(f"Available USDC for purchases: ${usdc_balance:.2f}\n")
    
    for i,pid in enumerate(RISKY_ASSETS):
        if delta_weights[i] > 0.001:
            target_qty = (target_weights[i]*total)/prices[pid]
            current_qty = holdings[pid]['qty']
            buy_qty = target_qty - current_qty
            usd_amount = delta_weights[i] * total
            
            print(f"BUY {buy_qty:.8f} {pid.split('-')[0]} (${usd_amount:.2f})")
            try:
                oid = execute_order(pid, 'buy', buy_qty)
                print(f"  ✓ {oid}\n")
                trades.append({'pid': pid, 'side': 'buy', 'qty': buy_qty, 'oid': oid})
                time.sleep(0.5)
            except Exception as e:
                print(f"  ✗ {e}\n")
    
    # Step 4: Final
    print("="*70+"\nSTEP 4: Final Allocation\n"+"-"*70)
    time.sleep(5)  # Longer wait for all orders to settle
    balances = get_balances()
    prices = get_prices()
    
    final_total = 0
    final_values = {}
    for pid in RISKY_ASSETS:
        qty = balances.get(pid.split('-')[0], 0)
        val = qty * prices[pid]
        final_values[pid] = {'qty': qty, 'val': val}
        final_total += val
    
    usdc_final = balances.get('USDC', 0)
    final_total += usdc_final
    
    print(f"\nFinal Holdings (Total: ${final_total:,.2f}):\n")
    for pid in RISKY_ASSETS:
        fv = final_values[pid]
        print(f"  {pid:10} {fv['qty']:>12.8f} @ ${prices[pid]:>10,.2f} = ${fv['val']:>9,.2f} ({fv['val']/final_total*100:>5.2f}%)")
    print(f"  {'USDC':10} {usdc_final:>12.2f} {' ':>13} = ${usdc_final:>9,.2f} ({usdc_final/final_total*100:>5.2f}%)")
    
    # Verify against target
    final_weights = np.array([final_values[pid]['val']/final_total for pid in RISKY_ASSETS])
    weight_diff = np.abs(final_weights - target_weights)
    max_diff = np.max(weight_diff) * 100
    
    print(f"\n  Deviation from target: {max_diff:.2f}% (max)")
    if max_diff > 2.0:
        print(f"  ⚠ WARNING: Portfolio allocation differs significantly from target!")
        print(f"             Some orders may not have filled. Check order status.")
    
    print("\n"+"="*70+f"\n✓ COMPLETE - {len(trades)} trades\n"+"="*70+"\n")
    
    # Log comprehensive trade history
    history_file = Path(__file__).parent.parent/'logs'/'trade_history.json'
    history = []
    if history_file.exists():
        with open(history_file) as f:
            c = f.read().strip()
            if c and c != '{}':
                history = json.loads(c)
                if isinstance(history, dict):
                    history = []
    
    # Build complete log entry
    usdc_target_weight = 1 - np.sum(target_weights)
    log_entry = {
        'timestamp': datetime.now(UTC).isoformat(),
        'portfolio_value': final_total,
        'current_weights': {pid: final_values[pid]['val']/final_total for pid in RISKY_ASSETS},
        'current_usdc_weight': usdc_final/final_total,
        'target_weights': {pid: float(target_weights[i]) for i, pid in enumerate(RISKY_ASSETS)},
        'target_usdc_weight': float(usdc_target_weight),
        'total_turnover': float(turnover),
        'trades': [{'product_id': t['pid'], 'side': t['side'], 'base_size': float(t['qty']), 'order_id': t['oid'], 'status': 'success'} for t in trades],
        'final_weights': {pid: final_values[pid]['val']/final_total for pid in RISKY_ASSETS},
        'final_usdc_weight': usdc_final/final_total
    }
    
    history.append(log_entry)
    with open(history_file, 'w') as f:
        json.dump(history, f, indent=2)

if __name__ == '__main__':
    try:
        rebalance()
    except Exception as e:
        print(f"\n✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
