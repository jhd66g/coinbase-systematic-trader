"""
pull_data.py
Fetches historical price data for portfolio assets and updates data.json
Usage: python pull_data.py [-date YYYY-MM-DD] [-days N]
"""

import os
import sys
import time
import json
import jwt
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

load_dotenv()

API_KEY_NAME = os.getenv('COINBASE_API_KEY_NAME')
PRIVATE_KEY = os.getenv('COINBASE_PRIVATE_KEY')
BASE_URL = 'https://api.coinbase.com'

# All portfolio products 
PRODUCTS = ['BTC-USD', 'ETH-USD', 'PAXG-USD', 'SOL-USD']

# Data file
DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs', 'data.json')


def build_jwt(request_method, request_path):
    """Build JWT token for Coinbase API authentication."""
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


def make_api_request(endpoint, method='GET', timeout=30):
    """Make authenticated request to Coinbase API."""
    jwt_token = build_jwt(method, endpoint)
    
    headers = {
        'Authorization': f'Bearer {jwt_token}',
        'Content-Type': 'application/json'
    }
    
    url = BASE_URL + endpoint
    response = requests.get(url, headers=headers, timeout=timeout)
    return response


def get_historical_candles(product_id, end_date, num_days):
    """
    Fetch historical daily candles for a product.
    
    Args:
        product_id: Trading pair (e.g., 'BTC-USD')
        end_date: End date as datetime object
        num_days: Number of days to fetch
    
    Returns:
        List of dicts with 'date' and 'close' keys, or None on failure
    """
    # Try multiple approaches to get candles
    attempts = [
        {"granularity": "ONE_DAY", "limit": num_days + 10},
        {"granularity": "DAY", "limit": num_days + 10},
        {"granularity": "ONE_DAY", "limit": 100},
    ]
    
    for attempt in attempts:
        query = f"?granularity={attempt['granularity']}&limit={attempt['limit']}"
        endpoints = [
            f"/api/v3/brokerage/products/{product_id}/candles{query}",
            f"/api/v3/brokerage/market/products/{product_id}/candles{query}",
        ]
        
        for endpoint in endpoints:
            try:
                response = make_api_request(endpoint, timeout=60)
                if response.status_code == 200:
                    data = response.json()
                    candles = data.get('candles', [])
                    
                    if candles:
                        # Convert to list of {date, close} dicts
                        result = []
                        for candle in candles:
                            timestamp = candle.get('start')
                            close = candle.get('close') or candle.get('close_price')
                            if timestamp and close:
                                date_str = datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d')
                                result.append({'date': date_str, 'close': float(close)})
                        
                        # Sort by date ascending
                        result.sort(key=lambda x: x['date'])
                        
                        # Filter to only dates up to end_date
                        end_date_str = end_date.strftime('%Y-%m-%d')
                        result = [r for r in result if r['date'] <= end_date_str]
                        
                        # Return the last num_days
                        if len(result) >= num_days:
                            return result[-num_days:]
                        elif result:
                            return result
                
            except Exception as e:
                continue
            
            time.sleep(0.2)
    
    return None


def load_data():
    """Load existing data from data.json."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            content = f.read().strip()
            if content:
                return json.loads(content)
    return {}


def save_data(data):
    """Save data to data.json."""
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def pull_data(end_date=None, num_days=60):
    """
    Pull historical price data for all risky products.
    
    Args:
        end_date: End date as datetime (default: today)
        num_days: Number of days to fetch (default: 60)
    """
    if end_date is None:
        end_date = datetime.now()
    
    print(f"Fetching {num_days} days of data ending {end_date.strftime('%Y-%m-%d')}...")
    
    # Load existing data
    data = load_data()
    
    # Fetch data for each product
    for product in PRODUCTS:
        print(f"  Fetching {product}...", end=' ')
        candles = get_historical_candles(product, end_date, num_days)
        
        if candles:
            data[product] = candles
            print(f"✓ {len(candles)} days")
        else:
            print(f"✗ Failed")
        
        time.sleep(0.3)  # Rate limiting
    
    # Save updated data
    save_data(data)
    print(f"\nData saved to {DATA_FILE}")
    
    return data


def main():
    """Main entry point with CLI argument parsing."""
    # Parse arguments
    end_date = None
    num_days = 60
    
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '-date' and i + 1 < len(sys.argv):
            try:
                end_date = datetime.strptime(sys.argv[i + 1], '%Y-%m-%d')
                i += 2
            except ValueError:
                print(f"Error: Invalid date format. Use YYYY-MM-DD")
                sys.exit(1)
        elif sys.argv[i] == '-days' and i + 1 < len(sys.argv):
            try:
                num_days = int(sys.argv[i + 1])
                i += 2
            except ValueError:
                print(f"Error: Invalid days value. Use integer.")
                sys.exit(1)
        else:
            print(f"Usage: python pull_data.py [-date YYYY-MM-DD] [-days N]")
            sys.exit(1)
    
    # Pull data
    pull_data(end_date, num_days)


if __name__ == '__main__':
    main()
