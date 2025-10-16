# api_test.py
# Test Coinbase API connectivity and endpoint functionality

import os
import json
import time
import jwt
import requests
from dotenv import load_dotenv
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

# Load environment variables
load_dotenv()

# Coinbase API configuration
API_KEY_NAME = os.getenv('COINBASE_API_KEY_NAME')
PRIVATE_KEY = os.getenv('COINBASE_PRIVATE_KEY')
BASE_URL = 'https://api.coinbase.com'

# Portfolio products to test
PRODUCTS = ['BTC-USD', 'ETH-USD', 'PAXG-USD', 'EURC-USDC']

def build_jwt(request_method, request_path):
    """
    Build JWT token for Coinbase Advanced Trade API authentication.
    """
    try:
        # Load the private key
        private_key = serialization.load_pem_private_key(
            PRIVATE_KEY.encode('utf-8'),
            password=None,
            backend=default_backend()
        )
        
        # Create JWT token
        uri = f"{request_method} api.coinbase.com{request_path}"
        payload = {
            'sub': API_KEY_NAME,
            'iss': 'coinbase-cloud',
            'nbf': int(time.time()),
            'exp': int(time.time()) + 120,  # Token expires in 2 minutes
            'uri': uri
        }
        
        token = jwt.encode(
            payload, 
            private_key, 
            algorithm='ES256', 
            headers={'kid': API_KEY_NAME, 'nonce': str(int(time.time()))}
        )
        
        return token
    except Exception as e:
        print(f"Error building JWT: {e}")
        return None

def make_api_request(endpoint, method='GET', body=None, timeout=30):
    """
    Make an authenticated request to the Coinbase API.
    """
    try:
        # Build JWT token
        jwt_token = build_jwt(method, endpoint)
        
        if not jwt_token:
            return None
        
        headers = {
            'Authorization': f'Bearer {jwt_token}',
            'Content-Type': 'application/json'
        }
        
        url = BASE_URL + endpoint
        
        if method == 'GET':
            response = requests.get(url, headers=headers, timeout=timeout)
        elif method == 'POST':
            body_str = json.dumps(body) if body else '{}'
            response = requests.post(url, headers=headers, data=body_str, timeout=timeout)
        
        return response
    except requests.exceptions.Timeout:
        return None
    except requests.exceptions.RequestException:
        return None
    except Exception:
        return None

def test_api_connection():
    """
    Test 1: Basic API connection - Get account balances
    """
    print("\n" + "="*60)
    print("TEST 1: API Connection - Account Balances")
    print("="*60)
    
    endpoint = '/api/v3/brokerage/accounts'
    response = make_api_request(endpoint)
    
    if response and response.status_code == 200:
        data = response.json()
        accounts = data.get('accounts', [])
        print(f"Status: SUCCESS")
        print(f"Accounts: {len(accounts)}")
        
        for account in accounts:
            currency = account.get('currency', 'N/A')
            balance = account.get('available_balance', {}).get('value', '0')
            print(f"  {currency}: {balance}")
        
        return True
    else:
        status = response.status_code if response else 'No response'
        print(f"Status: FAILED ({status})")
        if response:
            print(f"Error: {response.text}")
        return False

def test_get_ticker(product_id='BTC-USD'):
    """
    Get current spot price for a product
    """
    endpoint = f'/api/v3/brokerage/products/{product_id}/ticker'
    response = make_api_request(endpoint)
    
    if response and response.status_code == 200:
        data = response.json()
        price = data.get('best_ask') or data.get('best_bid', 'N/A')
        if price == 'N/A' and 'trades' in data and len(data['trades']) > 0:
            price = data['trades'][0].get('price', 'N/A')
        return True, price
    return False, None


def test_portfolio_products():
    """
    Test 2: Current prices for all portfolio products
    """
    print("\n" + "="*60)
    print("TEST 2: Current Prices - Portfolio Products")
    print("="*60)
    
    results = []
    for product in PRODUCTS:
        success, price = test_get_ticker(product)
        results.append((product, success, price))
        
        if success:
            print(f"  {product}: ${price}")
        else:
            print(f"  {product}: FAILED")
        
        time.sleep(0.3)
    
    success_count = sum(1 for _, success, _ in results if success)
    print(f"\nResult: {success_count}/{len(PRODUCTS)} successful")
    
    return success_count == len(PRODUCTS)

def main():
    """
    Run all API tests
    """
    print("\n" + "="*60)
    print("COINBASE API TEST SUITE")
    print("="*60)
    print(f"API Key: {API_KEY_NAME[:50]}..." if API_KEY_NAME else "API Key: Not configured")
    print(f"Private Key: {'Configured' if PRIVATE_KEY else 'Not configured'}")
    
    if not API_KEY_NAME or not PRIVATE_KEY:
        print("\nERROR: Missing API credentials in .env file")
        print("Required: COINBASE_API_KEY_NAME and COINBASE_PRIVATE_KEY")
        return
    
    # Run core tests
    results = []
    
    results.append(("API Connection", test_api_connection()))
    time.sleep(0.5)
    
    results.append(("Current Prices", test_portfolio_products()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for test_name, result in results:
        status = "PASSED" if result else "FAILED"
        print(f"{test_name}: {status}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\nAll tests passed successfully.")
    else:
        print("\nSome tests failed. Review errors above.")

if __name__ == "__main__":
    main()
