# api_test.py
# Test Coinbase API connectivity and endpoint functionality

import os
import time
import jwt
import requests
from dotenv import load_dotenv
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

load_dotenv()

API_KEY_NAME = os.getenv('COINBASE_API_KEY_NAME')
PRIVATE_KEY = os.getenv('COINBASE_PRIVATE_KEY')
BASE_URL = 'https://api.coinbase.com'

PRODUCTS = ['BTC-USD', 'ETH-USD', 'PAXG-USD', 'EURC-USDC']

def build_jwt(request_method, request_path):
    """Build JWT token for Coinbase API authentication."""
    try:
        private_key = serialization.load_pem_private_key(
            PRIVATE_KEY.encode('utf-8'), password=None, backend=default_backend()
        )
        
        uri = f"{request_method} api.coinbase.com{request_path}"
        payload = {
            'sub': API_KEY_NAME,
            'iss': 'coinbase-cloud',
            'nbf': int(time.time()),
            'exp': int(time.time()) + 120,
            'uri': uri
        }
        
        return jwt.encode(payload, private_key, algorithm='ES256', 
                         headers={'kid': API_KEY_NAME, 'nonce': str(int(time.time()))})
    except Exception:
        return None

def make_api_request(endpoint, method='GET', body=None, timeout=30):
    """Make authenticated request to Coinbase API."""
    try:
        jwt_token = build_jwt(method, endpoint)
        if not jwt_token:
            return None
        
        headers = {
            'Authorization': f'Bearer {jwt_token}',
            'Content-Type': 'application/json'
        }
        
        url = BASE_URL + endpoint
        
        if method == 'GET':
            return requests.get(url, headers=headers, timeout=timeout)
        elif method == 'POST':
            return requests.post(url, headers=headers, json=body or {}, timeout=timeout)
    except:
        return None

def test_api_connection():
    """Test 1: API Connection - Account Balances"""
    print("\n" + "="*60)
    print("TEST 1: API Connection - Account Balances")
    print("="*60)
    
    response = make_api_request('/api/v3/brokerage/accounts')
    
    if response and response.status_code == 200:
        accounts = response.json().get('accounts', [])
        print(f"Status: SUCCESS\nAccounts: {len(accounts)}")
        for account in accounts:
            currency = account.get('currency', 'N/A')
            balance = account.get('available_balance', {}).get('value', '0')
            print(f"  {currency}: {balance}")
        return True
    
    print(f"Status: FAILED")
    return False

def get_ticker_price(product_id):
    """Get current spot price for a product."""
    response = make_api_request(f'/api/v3/brokerage/products/{product_id}/ticker')
    
    if response and response.status_code == 200:
        data = response.json()
        price = data.get('best_ask') or data.get('best_bid')
        if not price and 'trades' in data and data['trades']:
            price = data['trades'][0].get('price')
        return True, price
    return False, None


def test_portfolio_products():
    """Test 2: Current Prices - Portfolio Products"""
    print("\n" + "="*60)
    print("TEST 2: Current Prices - Portfolio Products")
    print("="*60)
    
    results = []
    for product in PRODUCTS:
        success, price = get_ticker_price(product)
        results.append((product, success, price))
        print(f"  {product}: ${price}" if success else f"  {product}: FAILED")
        time.sleep(0.3)
    
    success_count = sum(1 for _, success, _ in results if success)
    print(f"\nResult: {success_count}/{len(PRODUCTS)} successful")
    return success_count == len(PRODUCTS)


def get_historical_price(product_id, days_ago=60):
    """Get closing price from ~days_ago using daily candles."""
    attempts = [
        {"granularity": "ONE_DAY", "extra": ""},
        {"granularity": "DAY", "extra": ""},
        {"granularity": "ONE_DAY", "extra": "&limit=90"},
    ]

    for attempt in attempts:
        qp = f"?granularity={attempt['granularity']}" + attempt['extra']
        endpoints = [
            f"/api/v3/brokerage/products/{product_id}/candles{qp}",
            f"/api/v3/brokerage/market/products/{product_id}/candles{qp}",
        ]
        
        for ep in endpoints:
            response = make_api_request(ep, timeout=60)
            if response and response.status_code == 200:
                data = response.json()
                candles = data.get('candles', [])
                if candles:
                    idx = max(0, len(candles) - days_ago)
                    close = candles[idx].get('close') or candles[idx].get('close_price')
                    if close:
                        return True, close
            time.sleep(0.2)
    
    return False, None


def test_historical_prices():
    """Test 3: Historical Prices (60 days ago)"""
    print("\n" + "="*60)
    print("TEST 3: Historical Prices (60 days ago)")
    print("="*60)

    results = []
    for product in PRODUCTS:
        success, price = get_historical_price(product, days_ago=60)
        results.append((product, success, price))
        print(f"  {product}: ${price}" if success else f"  {product}: FAILED")
        time.sleep(0.3)

    success_count = sum(1 for _, ok, _ in results if ok)
    print(f"\nResult: {success_count}/{len(PRODUCTS)} successful")
    return success_count == len(PRODUCTS)


def preview_order(product_id, side, size):
    """Preview an order without executing. Returns (success, info)."""
    body = {
        "product_id": product_id,
        "side": side.upper(),
        "order_configuration": {
            "market_market_ioc": {"quote_size" if side.upper() == "BUY" else "base_size": str(size)}
        }
    }
    
    response = make_api_request('/api/v3/brokerage/orders/preview', method='POST', body=body)
    
    if response and response.status_code == 200:
        data = response.json()
        return True, data
    return False, response.text if response else 'No response'


def test_order_preview():
    """Test 4: Order Preview (No Real Trades)"""
    print("\n" + "="*60)
    print("TEST 4: Order Preview - Portfolio Products (No Capital Risk)")
    print("="*60)
    
    # Test buy orders for each product
    test_orders = [
        ('BTC-USD', '1.00'),
        ('ETH-USD', '1.00'),
        ('PAXG-USD', '1.00'),
        ('EURC-USDC', '1.00')
    ]
    
    results = []
    for product, amount in test_orders:
        success, info = preview_order(product, 'BUY', amount)
        results.append((product, success))
        
        if success:
            quote_value = info.get('order_total', 'N/A')
            base_size = info.get('base_size', 'N/A')
            print(f"  Preview BUY ${amount} {product}: SUCCESS")
            print(f"    Cost: ${quote_value} | Size: {base_size}")
        else:
            print(f"  Preview BUY ${amount} {product}: FAILED")
        
        time.sleep(0.3)
    
    success_count = sum(1 for _, success in results if success)
    print(f"\nResult: {success_count}/{len(test_orders)} successful")
    
    return success_count == len(test_orders)

def main():
    """Run all API tests."""
    print("\n" + "="*60)
    print("COINBASE API TEST SUITE")
    print("="*60)
    print(f"API Key: {API_KEY_NAME[:50]}..." if API_KEY_NAME else "API Key: Not configured")
    print(f"Private Key: {'Configured' if PRIVATE_KEY else 'Not configured'}")
    
    if not API_KEY_NAME or not PRIVATE_KEY:
        print("\nERROR: Missing API credentials")
        return
    
    results = [
        ("API Connection", test_api_connection()),
        ("Current Prices", test_portfolio_products()),
        ("Historical Prices", test_historical_prices()),
        ("Order Preview", test_order_preview())
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
