
import requests
from typing import Dict, List, Optional
from urllib.parse import urljoin

class RampClient:
    def __init__(self, base_url: str, token_url: str, client_id: str, client_secret: str):
        self.base_url = base_url.rstrip('/')
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.session = requests.Session()
        self._token = None


    def authenticate(self):
        # Request all possible scopes - OAuth will grant only the ones allowed for this client
        all_scopes = "transactions:read bills:read reimbursements:read cashbacks:read statements:read accounting:read accounting:write"
        resp = self.session.post(
            self.token_url,
            data={"grant_type": "client_credentials", "scope": all_scopes},
            auth=(self.client_id, self.client_secret)  # Use Basic Auth
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data.get("access_token")
        
        # Log which scopes were actually granted (if available in response)
        granted_scopes = data.get("scope", "unknown")
        print(f"🔑 OAuth token granted with scopes: {granted_scopes}")
        
        self.session.headers.update({"Authorization": f"Bearer {self._token}"})
        return self._token

    def get_transactions(self, status: Optional[str] = None,
                        start_date: Optional[str] = None, end_date: Optional[str] = None,
                        page_size: int = 200) -> List[Dict]:
        """Fetch transactions from Ramp API"""
        return self._get_paginated_data("transactions", status, start_date, end_date, page_size)


    def get_bills(self, status: Optional[str] = None,
                  start_date: Optional[str] = None, end_date: Optional[str] = None,
                  page_size: int = 200) -> List[Dict]:
        """Fetch bills from Ramp API"""
        return self._get_paginated_data("bills", status, start_date, end_date, page_size)

    def get_reimbursements(self, status: Optional[str] = None,
                          start_date: Optional[str] = None, end_date: Optional[str] = None,
                          page_size: int = 200) -> List[Dict]:
        """Fetch reimbursements from Ramp API"""
        return self._get_paginated_data("reimbursements", status, start_date, end_date, page_size)

    def get_cashbacks(self, status: Optional[str] = None,
                      start_date: Optional[str] = None, end_date: Optional[str] = None,
                      page_size: int = 200) -> List[Dict]:
        """Fetch cashbacks from Ramp API"""
        return self._get_paginated_data("cashbacks", status, start_date, end_date, page_size)

    def get_statements(self, status: Optional[str] = None,
                       start_date: Optional[str] = None, end_date: Optional[str] = None,
                       page_size: int = 200) -> List[Dict]:
        """Fetch statements from Ramp API"""
        return self._get_paginated_data("statements", status, start_date, end_date, page_size)

    def mark_transaction_synced(self, transaction_id: str, sync_reference: str = None) -> bool:
        """
        Mark a transaction as synced to Business Central.
        This would typically update transaction metadata to indicate sync status.
        
        NOTE: Currently in testing mode - does not actually update Ramp.
        Requires accounting:write scope to be enabled.
        """
        # TESTING MODE: Do not actually mark as synced
        print(f"🔍 [TESTING] Would mark transaction {transaction_id} as synced (sync_reference: {sync_reference})")
        print("💡 To enable actual syncing, remove the testing safeguard in mark_transaction_synced()")
        return True  # Pretend it worked for testing purposes
        
        # PRODUCTION CODE (uncomment when ready):
        # url = f"{self.base_url}/transactions/{transaction_id}/sync"
        # data = {"synced": True, "sync_system": "business_central"}
        # if sync_reference:
        #     data["sync_reference"] = sync_reference
        #     
        # try:
        #     resp = self.session.post(url, json=data)
        #     return resp.status_code == 200
        # except Exception:
        #     return False

    def get_sync_status(self, transaction_id: str) -> Dict:
        """
        Get sync status for a transaction.
        Returns sync metadata if available.
        """
        try:
            url = f"{self.base_url}/transactions/{transaction_id}"
            resp = self.session.get(url)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("sync_status", {})
            return {}
        except Exception:
            return {}

    def _get_paginated_data(self, endpoint: str, status: Optional[str] = None,
                           start_date: Optional[str] = None, end_date: Optional[str] = None,
                           page_size: int = 200) -> List[Dict]:
        """Generic method for paginated API calls"""
        url = urljoin(self.base_url + '/', endpoint.lstrip('/'))
        params = {}
        if status:
            params["status"] = status
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        params["limit"] = page_size

        results: List[Dict] = []
        next_cursor = None
        while True:
            if next_cursor:
                params["cursor"] = next_cursor
            resp = self.session.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data") or []
            results.extend(items)
            next_cursor = data.get("next") or data.get("next_cursor")
            if not next_cursor:
                break
        return results
