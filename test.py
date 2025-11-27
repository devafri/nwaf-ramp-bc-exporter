
from utils import load_env, load_config
from ramp_client import RampClient
import json

def main():
    # Load environment variables and config
    env = load_env()
    cfg = load_config()

    # Initialize Ramp client
    client = RampClient(
        base_url=cfg['ramp']['base_url'],
        token_url=cfg['ramp']['token_url'],
        client_id=env['RAMP_CLIENT_ID'],
        client_secret=env['RAMP_CLIENT_SECRET']
    )

    # Authenticate
    print("Authenticating with Ramp...")
    token = client.authenticate()
    print(f"Access token: {token[:10]}...")  # Show first 10 chars for confirmation

    # Pull transactions
    print("Fetching all transactions from Ramp...")
    transactions = client.get_transactions(
        endpoint=cfg['ramp']['transactions_endpoint'],
        status=cfg['ramp'].get('status_filter'),
        page_size=cfg['ramp'].get('page_size', 200)
    )

    # Display sample output
    print(f"Total transactions fetched: {len(transactions)}")
    
    # Export all transactions to JSON file
    import json
    output_file = "ramp_transactions.json"
    with open(output_file, 'w') as f:
        json.dump(transactions, f, indent=2, default=str)
    print(f"All transactions exported to: {output_file}")
    
    if transactions:
        print("\nSample transaction (first one):")
        sample = transactions[0]
        print(json.dumps(sample, indent=2, default=str))

if __name__ == "__main__":
    main()
