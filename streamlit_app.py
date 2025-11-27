import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
import sys
import os
import streamlit.components.v1 as components

# Page configuration must be the first Streamlit command in the script
st.set_page_config(
    page_title="Ramp → Business Central Export",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Client-side fix: if Azure redirected to a subpath (e.g. /oauth2callback),
# redirect the browser to the app root while preserving query params so
# Streamlit's static assets and WebSocket endpoints load from the correct root.
components.html(
        """
        <script>
        (function() {
            try {
                const p = window.location.pathname || '/';
                if (p && p !== '/' && p.includes('oauth2callback')) {
                    const q = window.location.search || '';
                    // Replace so back button doesn't loop
                    // Use top-level navigation to avoid embedding identity provider pages inside frames
                    try {
                        if (window.top && window.top !== window) {
                            window.top.location.replace('/' + q);
                        } else {
                            window.location.replace('/' + q);
                        }
                    } catch (e) {
                        // If cross-origin access to window.top is denied, fallback to setting top location via document
                        try { document.location = '/' + q; } catch(e2) { window.location.replace('/' + q);} 
                    }
                }
            } catch (e) {
                // ignore
            }
        })();
        </script>
        """,
        height=0,
)
# MSAL-based in-app authentication for Streamlit Community Cloud (Azure AD)
import msal
import base64
import hmac
import hashlib
import time
from uuid import uuid4
from urllib.parse import urlencode

# Azure AD settings must be added to Streamlit secrets: AZURE_CLIENT_ID, AZURE_CLIENT_SECRET,
# AZURE_TENANT_ID, AZURE_REDIRECT_URI. Optionally AUTH_SCOPES (comma-separated).
CLIENT_ID = st.secrets.get("AZURE_CLIENT_ID")
CLIENT_SECRET = st.secrets.get("AZURE_CLIENT_SECRET")
TENANT_ID = st.secrets.get("AZURE_TENANT_ID")
REDIRECT_URI = st.secrets.get("AZURE_REDIRECT_URI")
# Default to a non-reserved resource scope. If you need OpenID claims, set AUTH_SCOPES
# in secrets to an appropriate scope (for example: "openid profile email User.Read").
# Default to a non-reserved resource scope. If you need OpenID claims, set AUTH_SCOPES
# in secrets to an appropriate scope (for example: "openid profile email User.Read").
SCOPES = [s.strip() for s in st.secrets.get("AUTH_SCOPES", "User.Read").split(",")]
# MSAL considers some scopes "reserved" (openid/profile/offline_access). Remove those
# from the scopes we pass to MSAL methods; these are handled implicitly by the library/provider.
_reserved = {"openid", "profile", "offline_access", "email"}
SCOPES_SANITIZED = [s for s in SCOPES if s and s.lower() not in _reserved]
if not SCOPES_SANITIZED:
    SCOPES_SANITIZED = ["User.Read"]

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SESSION_TOKEN_KEY = "msal_token"
SESSION_STATE_KEY = "msal_state"
TOKEN_ACQUIRED_TIME_KEY = "token_acquired_at"

def build_auth_url(state: str) -> str:
    cca = msal.ConfidentialClientApplication(
        CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET
    )
    return cca.get_authorization_request_url(scopes=SCOPES_SANITIZED, state=state, redirect_uri=REDIRECT_URI)


# Stateless signed state helpers
def _make_signed_state(raw_state: str, ttl: int = 600) -> str:
    """Create a URL-safe signed state token combining raw_state and timestamp.

    Format: base64url(payload) . hex(hmac)
    payload = "{raw_state}:{ts}" (ts = int seconds)
    ttl unused here; verification enforces TTL.
    """
    ts = str(int(time.time()))
    payload = f"{raw_state}:{ts}".encode("utf-8")
    b64 = base64.urlsafe_b64encode(payload).decode("utf-8").rstrip("=")
    sig = hmac.new(CLIENT_SECRET.encode("utf-8"), b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{b64}.{sig}"


def _verify_signed_state(signed_state: str, max_age: int = 600):
    """Verify the signed_state token. Returns (valid: bool, raw_state_or_none).

    Rejects if signature mismatch or timestamp older than max_age seconds.
    """
    try:
        if not signed_state or "." not in signed_state:
            return False, None
        b64, sig = signed_state.split('.', 1)
        expected_sig = hmac.new(CLIENT_SECRET.encode("utf-8"), b64.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_sig, sig):
            return False, None

        # base64 decode (add padding)
        pad = '=' * (-len(b64) % 4)
        payload = base64.urlsafe_b64decode(b64 + pad).decode("utf-8")
        raw_state, ts = payload.rsplit(':', 1)
        if int(time.time()) - int(ts) > max_age:
            return False, None
        return True, raw_state
    except Exception:
        return False, None

def get_valid_token():
    """Get a valid access token, refreshing if necessary"""
    import time
    
    token = st.session_state.get(SESSION_TOKEN_KEY)
    if not token:
        return None
    
    # Check if token is expired or about to expire (5-minute buffer)
    token_acquired_at = st.session_state.get(TOKEN_ACQUIRED_TIME_KEY, 0)
    expires_in = token.get('expires_in', 3600)
    expires_at = token_acquired_at + expires_in
    
    if time.time() >= (expires_at - 300):  # 5 minutes before expiry
        # Token expired or about to expire - try silent refresh
        cca = msal.ConfidentialClientApplication(
            CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET
        )
        
        accounts = cca.get_accounts()
        if accounts:
            result = cca.acquire_token_silent(SCOPES_SANITIZED, account=accounts[0])
            if result and result.get("access_token"):
                st.session_state[SESSION_TOKEN_KEY] = result
                st.session_state[TOKEN_ACQUIRED_TIME_KEY] = time.time()
                return result
        
        # Silent refresh failed - user needs to re-authenticate
        return None
    
    return token

# Ensure the secrets are configured
if not CLIENT_ID or not TENANT_ID or not REDIRECT_URI:
    st.error("Authentication is not configured. Add AZURE_CLIENT_ID, AZURE_TENANT_ID and AZURE_REDIRECT_URI to app secrets.")
    st.stop()

# If token present in session, use it
token = get_valid_token()
if token and token.get("access_token"):
    pass
else:
    # Use the stable `st.query_params` API
    qp = st.query_params
    if "code" in qp:
        # CRITICAL FIX: st.query_params returns a list-like object; access the full string correctly
        code_list = qp.get("code")
        if isinstance(code_list, list):
            code = code_list[0] if code_list else ""
        else:
            code = str(code_list) if code_list else ""

        # SECURITY: Validate state parameter to prevent CSRF attacks
        received_state = qp.get("state")
        if isinstance(received_state, list):
            received_state = received_state[0] if received_state else None
        expected_state = st.session_state.get(SESSION_STATE_KEY)

        valid_state = False
        # If we received a signed state (our stateless HMAC format), verify it
        if received_state and "." in str(received_state):
            ok, raw = _verify_signed_state(str(received_state))
            if ok:
                valid_state = True
                # store raw state in session for later correlation if needed
                st.session_state[SESSION_STATE_KEY] = raw
        # Fallback: if local session has expected state, compare directly
        elif received_state and expected_state and str(received_state) == str(expected_state):
            valid_state = True

        if not received_state or not valid_state:
            st.error("Security Error: Invalid state parameter detected.")
            st.warning("This could indicate a Cross-Site Request Forgery (CSRF) attempt.")
            st.info("Please try signing in again. If this persists, contact your system administrator.")
            st.session_state.clear()
            st.stop()

        cca = msal.ConfidentialClientApplication(
            CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET
        )
        # Use sanitized scopes for the token exchange as well (remove reserved OIDC scopes)
        try:
            result = cca.acquire_token_by_authorization_code(
                code, scopes=SCOPES_SANITIZED, redirect_uri=REDIRECT_URI
            )
        except Exception as ex:
            st.error('Authentication failed. Please try again.')
            # Log detailed error server-side but don't expose to user
            import logging
            logging.error(f'Token exchange exception: {str(ex)}')
            st.stop()

        # Debug & error handling: MSAL returns an error dict when token exchange fails.
        if result and result.get("access_token"):
            import time
            st.session_state[SESSION_TOKEN_KEY] = result
            st.session_state[TOKEN_ACQUIRED_TIME_KEY] = time.time()
            # clear query params from URL
            st.query_params.clear()
            token = result
        else:
            # Surface non-sensitive MSAL error fields for debugging (no secrets).
            err = {
                "error": result.get("error") if isinstance(result, dict) else str(result),
                "error_description": result.get("error_description") if isinstance(result, dict) else None,
                "claims": result.get("claims") if isinstance(result, dict) else None,
            }
            st.error("Authentication failed during token exchange.")
            st.write(err)
            st.stop()
    else:
        raw_state = str(uuid4())
        # create signed state so callback can be validated without session persistence
        signed_state = _make_signed_state(raw_state)
        # still store raw_state in session when possible (optional), to assist with extra checks
        st.session_state[SESSION_STATE_KEY] = raw_state
        auth_url = build_auth_url(signed_state)
        
        # Institutional authentication page
        st.markdown("""
        <div class="auth-container">
            <div class="auth-icon">🔒</div>
            <h1 class="auth-title">Authentication Required</h1>
            <p class="auth-subtitle">Please authenticate with your Microsoft corporate account to access the financial data export platform.</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("**Sign in options:**")
        # Clickable sign-in link opens in a new tab (stateless signed-state supports cross-tab flows)
        st.markdown(f"[Sign in with Microsoft]({auth_url})")
        st.write("If your browser prevents automatic navigation, copy the URL below and paste it into a new tab or the current tab's address bar.")
        st.code(auth_url, language=None)
        
        with st.expander("ℹ️ Security Information"):
            st.markdown("""
            **Why is this step required?**
            
            For security compliance, the authentication flow requires direct navigation to the Microsoft identity provider. 
            This ensures:
            - Secure session management
            - Proper authorization token delivery
            - CSRF protection
            - Compliance with enterprise security policies
            """)
        st.stop()

# Show a friendly welcome using identity claims (if available)
id_claims = st.session_state.get(SESSION_TOKEN_KEY, {}).get("id_token_claims", {})
# Fallback: decode id_token JWT if id_token_claims is missing
if not id_claims:
    id_token = st.session_state.get(SESSION_TOKEN_KEY, {}).get("id_token")
    if id_token:
        try:
            import jwt
            # decode without verifying signature (read-only claims extraction)
            claims = jwt.decode(id_token, options={"verify_signature": False})
            id_claims = claims
        except Exception:
            id_claims = {}

user_name = id_claims.get("name") or id_claims.get("preferred_username") or id_claims.get("email", "User")
user_email = id_claims.get("email") or id_claims.get("preferred_username", "")

# Enhanced sidebar user profile
st.sidebar.markdown("---")
st.sidebar.markdown("### 👤 User Profile")
st.sidebar.success(f"**{user_name}**")
if user_email and user_email != user_name:
    st.sidebar.caption(f"📧 {user_email}")
st.sidebar.markdown("---")

# Logout action clears the session token and optionally provides Azure logout link
if st.sidebar.button("🚪 Log out", use_container_width=True):
    st.session_state.pop(SESSION_TOKEN_KEY, None)
    st.query_params.clear()
    logout_url = (
        f"https://login.microsoftonline.com/common/oauth2/v2.0/logout?post_logout_redirect_uri={REDIRECT_URI}"
    )
    st.success("✅ You have been logged out successfully.")
    st.markdown(f"[🔐 Sign in again]({logout_url})")
    st.stop()

# Add current directory to path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils import load_env, load_config
from ramp_client import RampClient
from transform import (ramp_to_bc_rows, ramp_bills_to_bc_rows,
                      ramp_reimbursements_to_bc_rows, ramp_cashbacks_to_bc_rows,
                      ramp_statements_to_bc_rows)
from bc_export import export

# Load institutional stylesheet
def load_css():
    css_file = os.path.join(os.path.dirname(__file__), 'assets', 'styles.css')
    if os.path.exists(css_file):
        with open(css_file) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    else:
        # Fallback inline minimal styles if CSS file not found
        st.markdown("""
        <style>
        .app-header { background-color: #1a1f36; color: white; padding: 1.5rem 2rem; margin: -2rem -2rem 2rem -2rem; border-bottom: 3px solid #3498db; }
        .app-header h1 { font-size: 1.75rem; font-weight: 600; margin: 0; }
        .app-header p { margin: 0.5rem 0 0 0; color: #cbd5e0; font-size: 0.95rem; }
        </style>
        """, unsafe_allow_html=True)

load_css()

# Institutional header
st.markdown("""
<div class="app-header">
    <h1>Ramp → Business Central Export</h1>
    <p>Financial Data Integration Platform | Northwest Area Foundation</p>
</div>
""", unsafe_allow_html=True)

# Load configuration
try:
    # For local development
    if os.path.exists('.env'):
        env = load_env()
    else:
        # For Streamlit Cloud - use st.secrets
        env = {
            'RAMP_CLIENT_ID': st.secrets.get('RAMP_CLIENT_ID'),
            'RAMP_CLIENT_SECRET': st.secrets.get('RAMP_CLIENT_SECRET')
        }

    cfg = load_config()
except Exception as e:
    st.error("Configuration Error: Unable to load required settings.")
    st.markdown("Please contact your system administrator.")
    st.stop()

# Professional info card
st.markdown("""
<div class="info-card">
    <h3>System Overview</h3>
    <p>This platform provides secure, automated export of financial transaction data from Ramp to Business Central General Journal format.</p>
    <ul>
        <li>Secure Microsoft Azure AD authentication</li>
        <li>Real-time API integration with Ramp financial platform</li>
        <li>Business Central-compatible export formats (Excel, CSV)</li>
        <li>Support for multiple transaction types and date ranges</li>
    </ul>
</div>
""", unsafe_allow_html=True)

# Sidebar configuration
st.sidebar.markdown('<div class="section-header">Export Configuration</div>', unsafe_allow_html=True)

# Date range selection
st.sidebar.markdown("**Date Range**")
col1, col2 = st.sidebar.columns(2)

with col1:
    start_date = st.date_input(
        "Start Date",
        value=datetime.now().replace(day=1),  # First day of current month
        help="Start date for data export"
    )

with col2:
    end_date = st.date_input(
        "End Date",
        value=datetime.now(),
        help="End date for data export"
    )

# Data type selection
st.sidebar.markdown("")
st.sidebar.markdown("**Data Types**")
data_types = {
    'transactions': 'Card Transactions',
    'bills': 'Bill Payments',
    'reimbursements': 'Reimbursements',
    'cashbacks': 'Cashback Credits',
    'statements': 'Account Statements'
}

selected_types = []
for key, label in data_types.items():
    if st.sidebar.checkbox(label, value=True, key=f"checkbox_{key}"):
        selected_types.append(key)

# Post-export sync options
st.sidebar.markdown("")
mark_transactions_after_export = st.sidebar.checkbox(
    "Mark exported transactions in Ramp as synced",
    value=False,
    help="If checked, the app will mark exported transactions as synced in Ramp. This is a dry-run unless 'Enable live Ramp sync' is checked."
)
enable_live_ramp_sync = st.sidebar.checkbox(
    "Enable live Ramp sync (will POST to Ramp)",
    value=False,
    help="Enable sending a request to Ramp to mark transactions as synced. Requires accounting:write scope and should be used cautiously."
)

def run_export(selected_types, start_date, end_date, cfg, env):
    """Run the export process and display results"""

    with st.spinner("Authenticating with Ramp API..."):
        try:
            client = RampClient(
                base_url=cfg['ramp']['base_url'],
                token_url=cfg['ramp']['token_url'],
                client_id=env['RAMP_CLIENT_ID'],
                client_secret=env['RAMP_CLIENT_SECRET'],
                enable_sync=enable_live_ramp_sync
            )
            client.authenticate()
            st.success("Authentication successful")
        except Exception as e:
            st.error("Authentication failed. Please contact administrator.")
            return

    # Check available endpoints
    with st.spinner("Checking API availability..."):
        available_endpoints = check_available_endpoints(client, cfg)

    # Filter selected types to only available ones
    available_selected_types = [t for t in selected_types if available_endpoints.get(t, False)]

    if not available_selected_types:
        st.error("None of the selected data types are available with your current API permissions")
        return

    if len(available_selected_types) < len(selected_types):
        unavailable = [t for t in selected_types if t not in available_selected_types]
        st.warning(f"Some data types are not available: {', '.join(unavailable)}")

    # Progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()

    # Fetch and combine data
    combined_df = None
    total_records = 0
    processed_types = 0

    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')

    exported_transaction_ids = set()

    for data_type in available_selected_types:
        status_text.text(f"Fetching {data_type} from {start_date_str} to {end_date_str}...")

        try:
            data, df, processed_ids = fetch_data_for_type(client, data_type, start_date_str, end_date_str, cfg)

            if data:
                st.success(f"Retrieved {len(data)} {data_type} records")
                total_records += len(data)

                # Combine dataframes
                if combined_df is None:
                    combined_df = df
                else:
                    combined_df = pd.concat([combined_df, df], ignore_index=True)
                # Collect processed transaction ids for sync marking
                if processed_ids and data_type == 'transactions':
                    for tid in processed_ids:
                        exported_transaction_ids.add(str(tid))
            else:
                st.info(f"No {data_type} data found for the specified period")

        except Exception as e:
            st.error(f"Error fetching {data_type}: {str(e)}")
            continue

        processed_types += 1
        progress_bar.progress(processed_types / len(available_selected_types))

    progress_bar.empty()
    status_text.empty()

    if combined_df is None or combined_df.empty:
        st.error("No data found for any of the specified types and periods.")
        return

    # Display summary
    st.success(f"Export complete: {total_records} records processed from {len(available_selected_types)} data sources")

    # Display data preview
    st.subheader("Data Preview")
    st.dataframe(combined_df.head(10), use_container_width=True)

    # Export files
    st.subheader("Download Export Files")

    # Create Excel file
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        combined_df.to_excel(writer, sheet_name='Journal_Entries', index=False)
    excel_buffer.seek(0)

    # Create CSV file
    csv_buffer = BytesIO()
    combined_df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)

    col1, col2 = st.columns(2)

    with col1:
        st.download_button(
            label="Download Excel (.xlsx)",
            data=excel_buffer,
            file_name=f"Ramp_BC_Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    with col2:
        st.download_button(
            label="Download CSV (.csv)",
            data=csv_buffer,
            file_name=f"Ramp_BC_Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    # Show a manual button to mark exported transactions as synced
    if exported_transaction_ids:
        st.markdown("---")
        st.subheader("Post-export actions")
        st.write(f"{len(exported_transaction_ids)} exported transaction IDs collected for potential sync with Ramp.")
        st.caption("Use the button below to mark exported transactions as synced in Ramp. This will be a dry run unless 'Enable live Ramp sync' is checked in the sidebar.")

        if st.button("Mark as synced in Ramp", key="mark_synced_button"):
            st.info("Starting marking process — this may take a moment...")
            successes = 0
            failures = 0
            sync_ref = f"BCExport_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            progress = st.progress(0)
            total = len(exported_transaction_ids)
            i = 0
            for tid in list(exported_transaction_ids):
                i += 1
                ok = client.mark_transaction_synced(tid, sync_reference=sync_ref)
                if ok:
                    successes += 1
                else:
                    failures += 1
                progress.progress(i / total)

            if enable_live_ramp_sync:
                st.success(f"Ramp sync complete: {successes} succeeded, {failures} failed.")
            else:
                st.info(f"Dry run complete: {successes} would be marked synced (no live requests were sent).")

    # If requested, mark exported transactions in Ramp (dry-run unless live sync enabled)
    if mark_transactions_after_export and exported_transaction_ids:
        st.info(f"Preparing to mark {len(exported_transaction_ids)} exported transactions as synced in Ramp...")
        successes = 0
        failures = 0
        sync_ref = f"BCExport_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        for tid in exported_transaction_ids:
            ok = client.mark_transaction_synced(tid, sync_reference=sync_ref)
            if ok:
                successes += 1
            else:
                failures += 1

        if enable_live_ramp_sync:
            st.success(f"Ramp sync complete: {successes} succeeded, {failures} failed.")
        else:
            st.info(f"Dry run complete: {successes} would be marked synced (no live requests were sent).")

def check_available_endpoints(client, cfg):
    """Check which API endpoints are available based on OAuth scopes."""
    endpoints_to_check = {
        'transactions': 'transactions:read',
        'bills': 'bills:read',
        'reimbursements': 'reimbursements:read',
        'cashbacks': 'cashbacks:read',
        'statements': 'statements:read',
        'accounting': 'accounting:read'
    }

    available = {}

    for endpoint, required_scope in endpoints_to_check.items():
        try:
            if endpoint == 'accounting':
                # For accounting, test a different endpoint or method
                url = f"{cfg['ramp']['base_url']}/transactions"
                resp = client.session.get(url, params={'limit': 1})
                available[endpoint] = resp.status_code == 200
            else:
                url = f"{cfg['ramp']['base_url']}/{endpoint}"
                resp = client.session.get(url, params={'limit': 1})
                available[endpoint] = resp.status_code == 200
        except Exception:
            available[endpoint] = False

    return available

def fetch_data_for_type(client, data_type, start_date, end_date, cfg):
    """Fetch data for a specific type and return (data, dataframe, processed_ids)

    processed_ids is a list of string ids for the items that were successfully
    transformed into DataFrame rows (parsed from the "Document No." column when present).
    """
    if data_type == 'transactions':
        data = client.get_transactions(
            status=cfg['ramp'].get('status_filter'),
            start_date=start_date,
            end_date=end_date,
            page_size=cfg['ramp'].get('page_size', 200)
        )
        # Filter out already-synced items when possible
        if isinstance(data, list) and data:
            before = len(data)
            data = [d for d in data if not client.is_transaction_synced(d)]
            after = len(data)
            if after < before:
                st.info(f"Skipped {before-after} transactions that were already marked synced in Ramp")

        df = ramp_to_bc_rows(data, cfg)
    elif data_type == 'bills':
        data = client.get_bills(
            status='APPROVED',
            start_date=start_date,
            end_date=end_date,
            page_size=cfg['ramp'].get('page_size', 200)
        )
        if isinstance(data, list) and data:
            before = len(data)
            data = [d for d in data if not client.is_transaction_synced(d)]
            after = len(data)
            if after < before:
                st.info(f"Skipped {before-after} bills that were already marked synced in Ramp")
        df = ramp_bills_to_bc_rows(data, cfg)
    elif data_type == 'reimbursements':
        data = client.get_reimbursements(
            status='PAID',
            start_date=start_date,
            end_date=end_date,
            page_size=cfg['ramp'].get('page_size', 200)
        )
        if isinstance(data, list) and data:
            before = len(data)
            data = [d for d in data if not client.is_transaction_synced(d)]
            after = len(data)
            if after < before:
                st.info(f"Skipped {before-after} reimbursements that were already marked synced in Ramp")
        df = ramp_reimbursements_to_bc_rows(data, cfg)
    elif data_type == 'cashbacks':
        data = client.get_cashbacks(
            start_date=start_date,
            end_date=end_date,
            page_size=cfg['ramp'].get('page_size', 200)
        )
        if isinstance(data, list) and data:
            before = len(data)
            data = [d for d in data if not client.is_transaction_synced(d)]
            after = len(data)
            if after < before:
                st.info(f"Skipped {before-after} cashbacks that were already marked synced in Ramp")
        df = ramp_cashbacks_to_bc_rows(data, cfg)
    elif data_type == 'statements':
        data = client.get_statements(
            start_date=start_date,
            end_date=end_date,
            page_size=cfg['ramp'].get('page_size', 200)
        )
        if isinstance(data, list) and data:
            before = len(data)
            data = [d for d in data if not client.is_transaction_synced(d)]
            after = len(data)
            if after < before:
                st.info(f"Skipped {before-after} statements that were already marked synced in Ramp")
        df = ramp_statements_to_bc_rows(data, cfg)
    else:
        raise ValueError(f"Unknown data type: {data_type}")

    # Derive processed ids from DataFrame if possible
    processed_ids = []
    try:
        if df is not None and not df.empty and 'Document No.' in df.columns:
            for val in df['Document No.'].tolist():
                if not val:
                    continue
                # Often Document No. values are formatted like PREFIX-<id>
                if isinstance(val, str) and '-' in val:
                    _id = val.split('-', 1)[1]
                else:
                    _id = str(val)
                processed_ids.append(_id)
    except Exception:
        processed_ids = []

    return data, df, processed_ids

# Export button
st.sidebar.markdown("")
if st.sidebar.button("Execute Export", type="primary", use_container_width=True):
    if not selected_types:
        st.error("Please select at least one data type to export.")
    elif start_date >= end_date:
        st.error("Start date must be before end date.")
    else:
        run_export(selected_types, start_date, end_date, cfg, env)

# Footer
st.markdown("""
<div class="footer">
    <div class="footer-title">Northwest Area Foundation</div>
    <p>Financial Data Integration Platform | Ramp → Business Central Export</p>
    <div class="footer-meta">Secure Enterprise Solution | Protected by Microsoft Azure AD</div>
</div>
""", unsafe_allow_html=True)