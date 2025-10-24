"""
daily_trade.py - Automated daily trading script
Runs rebalance.py, logs results, and sends email summary
"""
import os, sys, json, subprocess, smtplib
from datetime import datetime, UTC
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import numpy as np

# Setup paths
sys.path.insert(0, str(Path(__file__).parent))
BASE_DIR = Path(__file__).parent.parent
LOG_FILE = BASE_DIR / 'logs' / 'trade_history.json'

# Load environment variables
load_dotenv(BASE_DIR / '.env')
EMAIL_FROM = os.getenv('EMAIL_FROM')
EMAIL_TO = os.getenv('EMAIL_TO')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))

# Import after path setup
from globals import RISKY_ASSETS
from optimize_portfolio import optimize_portfolio

def load_trade_history():
    """Load existing trade history"""
    if LOG_FILE.exists():
        with open(LOG_FILE, 'r') as f:
            return json.load(f)
    return []

def save_trade_history(history):
    """Save trade history to file"""
    with open(LOG_FILE, 'w') as f:
        json.dump(history, f, indent=2)

def calculate_pnl(history):
    """Calculate day-over-day and lifetime P&L"""
    if len(history) < 2:
        return 0.0, 0.0
    
    # Handle both old and new format
    latest = history[-1].get('portfolio_value') or history[-1].get('total', 0)
    previous = history[-2].get('portfolio_value') or history[-2].get('total', 0)
    initial = history[0].get('portfolio_value') or history[0].get('total', 0)
    
    day_pnl = latest - previous
    lifetime_pnl = latest - initial
    
    return day_pnl, lifetime_pnl

def format_email_body(trade_log, day_pnl, lifetime_pnl, optimal_weights=None):
    """Format the email body with trade summary"""
    timestamp = trade_log['timestamp']
    portfolio_value = trade_log.get('portfolio_value') or trade_log.get('total', 0)
    current_weights = trade_log.get('final_weights', trade_log.get('current_weights', {}))
    target_weights = trade_log.get('target_weights', {})
    trades = trade_log.get('trades', [])
    
    # Calculate percentages for display
    day_pnl_pct = (day_pnl / (portfolio_value - day_pnl)) * 100 if portfolio_value != day_pnl else 0
    lifetime_pnl_pct = (lifetime_pnl / (portfolio_value - lifetime_pnl)) * 100 if portfolio_value != lifetime_pnl else 0
    
    body = f"""
Daily Trading Summary - {timestamp}

═══════════════════════════════════════════════════════════

PORTFOLIO OVERVIEW
Total Value: ${portfolio_value:.2f}
Day P&L: ${day_pnl:+.2f} ({day_pnl_pct:+.2f}%)
Lifetime P&L: ${lifetime_pnl:+.2f} ({lifetime_pnl_pct:+.2f}%)

═══════════════════════════════════════════════════════════

CURRENT HOLDINGS
"""
    
    for asset, weight in current_weights.items():
        asset_value = portfolio_value * weight
        body += f"{asset:12s} {weight*100:6.2f}%  (${asset_value:.2f})\n"
    
    usdc_weight = trade_log.get('final_usdc_weight', trade_log.get('current_usdc_weight', 0))
    usdc_value = portfolio_value * usdc_weight
    body += f"{'USDC':12s} {usdc_weight*100:6.2f}%  (${usdc_value:.2f})\n"
    
    body += "\n═══════════════════════════════════════════════════════════\n\n"
    body += "TARGET ALLOCATION\n"
    
    for asset, weight in target_weights.items():
        target_value = portfolio_value * weight
        body += f"{asset:12s} {weight*100:6.2f}%  (${target_value:.2f})\n"
    
    target_usdc_weight = trade_log.get('target_usdc_weight', 0)
    target_usdc_value = portfolio_value * target_usdc_weight
    body += f"{'USDC':12s} {target_usdc_weight*100:6.2f}%  (${target_usdc_value:.2f})\n"
    
    body += "\n═══════════════════════════════════════════════════════════\n\n"
    
    # Add optimal allocation if provided
    if optimal_weights:
        body += "OPTIMAL ALLOCATION (Unconstrained)\n"
        body += "If starting from scratch with no holdings\n\n"
        
        for asset, weight in optimal_weights.items():
            if asset != 'USDC':
                optimal_value = portfolio_value * weight
                body += f"{asset:12s} {weight*100:6.2f}%  (${optimal_value:.2f})\n"
        
        optimal_usdc_weight = optimal_weights.get('USDC', 0)
        optimal_usdc_value = portfolio_value * optimal_usdc_weight
        body += f"{'USDC':12s} {optimal_usdc_weight*100:6.2f}%  (${optimal_usdc_value:.2f})\n"
        
        body += "\n═══════════════════════════════════════════════════════════\n\n"
    
    body += f"TRADES EXECUTED ({len(trades)})\n"
    
    if trades:
        for trade in trades:
            side = trade['side'].upper()
            product = trade['product_id']
            amount = trade.get('usd_amount', trade.get('base_size', 0))
            status = trade.get('status', 'unknown')
            body += f"{side:4s} {product:12s} ${amount:.2f}  [{status}]\n"
    else:
        body += "No trades executed (within rebalance bands)\n"
    
    body += "\n═══════════════════════════════════════════════════════════\n"
    
    return body

def send_email(subject, body):
    """Send email summary via SMTP"""
    if not all([EMAIL_FROM, EMAIL_TO, EMAIL_PASSWORD]):
        print("WARNING: Email credentials not configured in .env file")
        print("Required: EMAIL_FROM, EMAIL_TO, EMAIL_PASSWORD")
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = EMAIL_TO
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.send_message(msg)
        
        print(f"Email sent to {EMAIL_TO}")
        return True
    except Exception as e:
        print(f"ERROR: Failed to send email: {e}")
        return False

def main():
    """Main execution function"""
    print(f"\n{'='*60}")
    print(f"Daily Trade Execution - {datetime.now(UTC).isoformat()}")
    print(f"{'='*60}\n")
    
    # Run rebalance.py
    print("Running rebalance.py...")
    try:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent / 'rebalance.py')],
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Rebalance failed: {e}")
        print(e.stdout)
        print(e.stderr)
        sys.exit(1)
    
    # Load trade history
    history = load_trade_history()
    if not history:
        print("ERROR: No trade history found")
        sys.exit(1)
    
    latest_trade = history[-1]
    
    # Calculate P&L
    day_pnl, lifetime_pnl = calculate_pnl(history)
    
    # Calculate optimal (unconstrained) weights
    print("\nCalculating optimal allocation...")
    data_file = BASE_DIR / 'logs' / 'data.json'
    with open(data_file) as f:
        data = json.load(f)
    
    price_matrix = np.array([[item['close'] for item in data[pid][-60:]] for pid in RISKY_ASSETS]).T
    result_optimal = optimize_portfolio(price_matrix, current_weights=None, halflife=60)
    
    optimal_weights = {pid: float(result_optimal['weights'][i]) for i, pid in enumerate(RISKY_ASSETS)}
    optimal_weights['USDC'] = float(1 - np.sum(result_optimal['weights']))
    
    print(f"\nPortfolio Value: ${latest_trade['portfolio_value']:.2f}")
    print(f"Day P&L: ${day_pnl:+.2f}")
    print(f"Lifetime P&L: ${lifetime_pnl:+.2f}")
    
    # Format and send email
    subject = f"Coinbase Trading Summary - {datetime.now(UTC).strftime('%Y-%m-%d')}"
    body = format_email_body(latest_trade, day_pnl, lifetime_pnl, optimal_weights)
    
    print(f"\n{'='*60}")
    print("EMAIL PREVIEW:")
    print(f"{'='*60}")
    print(body)
    print(f"{'='*60}\n")
    
    send_email(subject, body)
    
    print(f"\nDaily trade execution complete\n")

if __name__ == '__main__':
    main()
