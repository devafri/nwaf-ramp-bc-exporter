"""Fetch live transactions from Ramp and export to the credit-card CSV format.

This script reads Ramp credentials from a local `.env` file (use python-dotenv),
loads `config.toml` for API endpoints, authenticates with Ramp, fetches recent
transactions (last 30 days by default), transforms them using
`ramp_credit_card_to_bc_rows`, and writes an export CSV plus an audit CSV.

Notes:
- This will perform READ operations only. Live writes to Ramp remain disabled by
  default (see `enable_sync` flags elsewhere in the repo).
- Do NOT print secrets. Output is limited to counts and filenames.
"""

import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import toml
from ramp_client import RampClient
from transform import ramp_credit_card_to_bc_rows

# Load environment variables from .env
load_dotenv()
env = os.environ

RAMP_CLIENT_ID = env.get('RAMP_CLIENT_ID')
RAMP_CLIENT_SECRET = env.get('RAMP_CLIENT_SECRET')
if not RAMP_CLIENT_ID or not RAMP_CLIENT_SECRET:
    raise SystemExit('RAMP_CLIENT_ID and RAMP_CLIENT_SECRET must be set in the environment or .env file')

# Load config.toml
cfg = toml.load('config.toml')

base_url = cfg['ramp'].get('base_url')
token_url = cfg['ramp'].get('token_url')
page_size = cfg['ramp'].get('page_size', 200)
status_filter = cfg['ramp'].get('status_filter')

# Initialize Ramp client (reads only)
client = RampClient(base_url=base_url, token_url=token_url,
                    client_id=RAMP_CLIENT_ID, client_secret=RAMP_CLIENT_SECRET,
                    enable_sync=False)

print('Authenticating with Ramp (READ-only)...')
client.authenticate()

# Fetch recent transactions (last 30 days)
end_date = datetime.utcnow().date()
start_date = end_date - timedelta(days=30)
start_str = start_date.strftime('%Y-%m-%d')
end_str = end_date.strftime('%Y-%m-%d')

print(f'Fetching transactions from {start_str} to {end_str} (status={status_filter})...')
try:
    transactions = client.get_transactions(status=status_filter, start_date=start_str, end_date=end_str, page_size=page_size)
except Exception as e:
    raise SystemExit(f'Failed to fetch transactions from Ramp: {e}')

print(f'Fetched {len(transactions)} transactions from Ramp')

# Transform to credit-card export format
df = ramp_credit_card_to_bc_rows(transactions, {'business_central': cfg.get('business_central', {}), 'exports_path': 'exports'})

# Write export CSV
os.makedirs('exports', exist_ok=True)
ts = datetime.now().strftime('%Y%m%dT%H%M%S')
export_path = os.path.join('exports', f'Ramp_CC_Export_{ts}.csv')
try:
    df.to_csv(export_path, index=False)
    print(f'Wrote credit-card export: {export_path} (rows: {len(df)})')
except Exception as e:
    print(f'Failed to write export CSV: {e}')

print('Done.')
