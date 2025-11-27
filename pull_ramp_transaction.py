
#!/usr/bin/env python3
import os
import sys
import time
import json
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter, Retry
import pandas as pd
from dotenv import load_dotenv


# ---- Configuration ----
DEFAULT_BASE_URL = "https://api.ramp.com/v1"
# Common endpoints: 'transactions', 'card_transactions', etc. Change if needed:
TRANSACTIONS_ENDPOINT = "transactions"  # e.g., /v1/transactions


def make_http_session() -> requests.Session:
    """Create a requests Session with robust retry/backoff."""
    s = requests.Session()
    retries = Retry(
        total=6,
        backoff_factor=0.8,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))
    return s


def iso_now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fetch_ramp_transactions(
    api_key: str,
    base_url: str,
    updated_after: Optional[str] = None,
    page_size: int = 200,
    max_pages: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Pull Ramp transactions with pagination.

    Pagination strategies vary by API:
    - Some use `page_token` (ampersand `page_token` in response).
    - Others use `starting_after` (cursor id).
    This function attempts a generic approach; adjust param names if needed.

    Returns a list of transaction dicts.
    """
    s = make_http_session()
    headers = {"Authorization": f"Bearer {api_key}"}

    url = f"{base_url.rstrip('/')}/{TRANSACTIONS_ENDPOINT}"
    params: Dict[str, Any] = {}

    # Common filters; adjust to match your API contract:
    if updated_after:
        params["updated_after"] = updated_after
    # Many APIs use page_size/limit:
    params["page_size"] = page_size

    all_items: List[Dict[str, Any]] = []
    page_count = 0
    next_token: Optional[str] = None

    while True:
        if next_token:
            # If your API uses `page_token`/`next_page_token`, set here:
            params["page_token"] = next_token
            # If your API uses `starting_after`, change key accordingly:
            # params["starting_after"] = next_token

        resp = s.get(url, headers=headers, params=params, timeout=30)
        # If 429 still returns after retries, consider sleeping more:
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            sleep_sec = int(retry_after) if retry_after and retry_after.isdigit() else 5
            time.sleep(sleep_sec)
            resp = s.get(url, headers=headers, params=params, timeout=30)

        resp.raise_for_status()
        data = resp.json()

        # Expected shapes:
        # A) { "data": [...], "next_page_token": "abc" }
        # B) { "transactions": [...], "next": "abc" }
        # C) flat list [...], with Link headers for pagination (less common for JSON APIs)
        items: List[Dict[str, Any]] = []
        next_token = None

        if isinstance(data, dict):
            if "data" in data and isinstance(data["data"], list):
                items = data["data"]
                next_token = data.get("next_page_token") or data.get("next")
            elif "transactions" in data and isinstance(data["transactions"], list):
                items = data["transactions"]
                next_token = data.get("next_page_token") or data.get("next")
            else:
                # If the API returns a dict per page but with a different key:
                # Try to find the first list value:
                lists = [v for v in data.values() if isinstance(v, list)]
                if lists:
                    items = lists[0]
                # Try common token keys:
                next_token = data.get("next_page_token") or data.get("next")
        elif isinstance(data, list):
            items = data
            # If pagination uses headers/links, you'd parse here.

        if not items:
            break

        all_items.extend(items)
        page_count += 1

        if max_pages is not None and page_count >= max_pages:
            break

        # If no next token, we’re done
        if not next_token:
            break

    return all_items


def normalize_transactions(raw: List[Dict[str, Any]]) -> Tuple[pd.DataFrame, List[str]]:
    """
    Flatten transactions to a tabular form suitable for CSV, while
    returning any unexpected fields in `notes`.
    Adjust the mapping to match your Ramp schema.
    """
    rows: List[Dict[str, Any]] = []
    notes: List[str] = []

    for tx in raw:
        row = {}

        # Common fields seen in card transaction APIs (adjust to actual Ramp schema):
        row["id"] = tx.get("id")
        row["created_at"] = tx.get("created_at") or tx.get("date") or tx.get("posted_at")
        row["updated_at"] = tx.get("updated_at")
        row["amount"] = tx.get("amount") or tx.get("amount_cents")
        row["currency"] = tx.get("currency") or tx.get("currency_code")
        row["status"] = tx.get("status")
        row["merchant_name"] = (
            tx.get("merchant_name")
            or (tx.get("merchant") or {}).get("name")
        )
        row["category"] = tx.get("category") or (tx.get("merchant") or {}).get("category")
        row["cardholder"] = (
            tx.get("cardholder")
            or (tx.get("user") or {}).get("name")
            or (tx.get("employee") or {}).get("name")
        )
        row["card_last4"] = tx.get("card_last4") or (tx.get("card") or {}).get("last4")
        row["memo"] = tx.get("memo") or tx.get("description")
        row["receipt_status"] = tx.get("receipt_status") or tx.get("has_receipt")
        row["source"] = tx.get("source")  # e.g., 'card', 'reimbursement', etc.

        # Dimensions/tags (custom fields):
        custom = tx.get("custom_fields") or tx.get("metadata") or {}
        if isinstance(custom, dict):
            for k, v in custom.items():
                # Prefix custom fields to avoid collisions:
                row[f"custom_{k}"] = v

        # Keep a note of unexpected keys for inspection:
        unexpected_keys = [k for k in tx.keys() if k not in {
            "id", "created_at", "updated_at", "amount", "currency", "status",
            "merchant_name", "category", "cardholder", "card_last4", "memo",
            "receipt_status", "source", "custom_fields", "metadata", "merchant", "user", "employee", "card"
        }]
        if unexpected_keys:
            notes.append(f"id={row['id']}: extra={unexpected_keys}")

        rows.append(row)

    df = pd.DataFrame(rows)
    # Sort for readability:
    if "created_at" in df.columns:
        df = df.sort_values(by=["created_at", "id"], ascending=[True, True])
    return df, notes


def save_outputs(df: pd.DataFrame, raw: List[Dict[str, Any]], out_prefix: str) -> None:
    """Save to JSON (raw) and CSV (normalized)."""
    json_path = f"{out_prefix}.json"
    csv_path = f"{out_prefix}.csv"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)

    # For CSV, ensure safe dtype handling:
    df.to_csv(csv_path, index=False)
    print(f"Saved {len(raw)} transactions:")
    print(f"  Raw JSON: {json_path}")
    print(f"  CSV     : {csv_path}")


def main():
    load_dotenv()
    api_key = os.getenv("RAMP_API_KEY")
    base_url = os.getenv("RAMP_BASE_URL", DEFAULT_BASE_URL)

    if not api_key:
        print("ERROR: RAMP_API_KEY is not set (env or .env).")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Pull transactions from Ramp API.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--updated-after", type=str, help="ISO 8601 timestamp for incremental loads, e.g., 2025-11-01T00:00:00Z")
    group.add_argument("--all", action="store_true", help="Pull all available transactions (paginated).")

    parser.add_argument("--page-size", type=int, default=200, help="Page size/limit per request (adjust to API constraints).")
    parser.add_argument("--max-pages", type=int, default=None, help="Optional cap on pages for testing.")
    parser.add_argument("--out-prefix", type=str, default=f"ramp_transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}", help="Prefix for output files (JSON & CSV).")

    args = parser.parse_args()

    updated_after = args.updated_after if not args.all else None

    print(f"[{iso_now_utc()}] Fetching Ramp transactions...")
    txs = fetch_ramp_transactions(
        api_key=api_key,
        base_url=base_url,
        updated_after=updated_after,
        page_size=args.page_size,
        max_pages=args.max_pages
    )

    print(f"[{iso_now_utc()}] Retrieved {len(txs)} transactions.")
    df, notes = normalize_transactions(txs)
    if notes:
        print(f"Notes on unexpected fields ({len(notes)}):")
        for n in notes[:10]:
            print(f"  {n}")
        if len(notes) > 10:
            print(f"  ... {len(notes)-10} more")

    save_outputs(df, txs, args.out_prefix)
    print(f"[{iso_now_utc()}] Done.")


if __name__ == "__main__":
    main()
