import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
import sys
import os
# MSAL-based in-app authentication for Streamlit Community Cloud (Azure AD)
import msal
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

def build_auth_url(state: str) -> str:
    cca = msal.ConfidentialClientApplication(
        CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET
    )
    return cca.get_authorization_request_url(scopes=SCOPES_SANITIZED, state=state, redirect_uri=REDIRECT_URI)

# Ensure the secrets are configured
if not CLIENT_ID or not TENANT_ID or not REDIRECT_URI:
    st.error("Authentication is not configured. Add AZURE_CLIENT_ID, AZURE_TENANT_ID and AZURE_REDIRECT_URI to app secrets.")
    st.stop()

# If token present in session, use it
token = st.session_state.get(SESSION_TOKEN_KEY)
if token and token.get("access_token"):
    pass
else:
    # Use the stable `st.query_params` API
    qp = st.query_params
    if "code" in qp:
        code = qp["code"][0]
        cca = msal.ConfidentialClientApplication(
            CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET
        )
        # Use sanitized scopes for the token exchange as well (remove reserved OIDC scopes)
        result = cca.acquire_token_by_authorization_code(
            code, scopes=SCOPES_SANITIZED, redirect_uri=REDIRECT_URI
        )
        if result and result.get("access_token"):
            st.session_state[SESSION_TOKEN_KEY] = result
            # clear query params from URL
            st.experimental_set_query_params()
            token = result
        else:
            st.error("Authentication failed. Please try signing in again.")
            st.stop()
    else:
        state = str(uuid4())
        st.session_state[SESSION_STATE_KEY] = state
        auth_url = build_auth_url(state)
        st.markdown("🔒 Please sign in with your Microsoft account to continue.")
        st.markdown(f"[Sign in with Microsoft]({auth_url})")
        st.stop()

# Show a friendly welcome using identity claims (if available)
id_claims = st.session_state.get(SESSION_TOKEN_KEY, {}).get("id_token_claims", {})
user_name = id_claims.get("name") or id_claims.get("preferred_username") or id_claims.get("email", "User")
st.sidebar.success(f"Welcome, {user_name}!")

# Logout action clears the session token and optionally provides Azure logout link
if st.sidebar.button("Log out"):
    st.session_state.pop(SESSION_TOKEN_KEY, None)
    st.experimental_set_query_params()
    logout_url = (
        f"https://login.microsoftonline.com/common/oauth2/v2.0/logout?post_logout_redirect_uri={REDIRECT_URI}"
    )
    st.info("You have been logged out.")
    st.markdown(f"[Sign in again]({logout_url})")

# Add current directory to path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils import load_env, load_config
from ramp_client import RampClient
from transform import (ramp_to_bc_rows, ramp_bills_to_bc_rows,
                      ramp_reimbursements_to_bc_rows, ramp_cashbacks_to_bc_rows,
                      ramp_statements_to_bc_rows)
from bc_export import export

st.set_page_config(
    page_title="Ramp → Business Central Export",
    page_icon="💳",
    layout="wide"
)

st.title("💳 Ramp → Business Central Journal Export")
st.markdown("Export Ramp transactions, bills, reimbursements, and statements to Business Central General Journal format.")

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
    st.success("✅ Configuration loaded successfully")
except Exception as e:
    st.error("❌ Configuration error. Please contact administrator.")
    st.stop()

# Sidebar for configuration
st.sidebar.header("Export Settings")

# Date range selection
st.sidebar.subheader("Date Range")
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
st.sidebar.subheader("Data Types to Export")
data_types = {
    'transactions': 'Transactions',
    'bills': 'Bills',
    'reimbursements': 'Reimbursements',
    'cashbacks': 'Cashbacks',
    'statements': 'Statements'
}

selected_types = []
for key, label in data_types.items():
    if st.sidebar.checkbox(label, value=True, key=f"checkbox_{key}"):
        selected_types.append(key)

def run_export(selected_types, start_date, end_date, cfg, env):
    """Run the export process and display results"""

    with st.spinner("🔑 Authenticating with Ramp API..."):
        try:
            client = RampClient(
                base_url=cfg['ramp']['base_url'],
                token_url=cfg['ramp']['token_url'],
                client_id=env['RAMP_CLIENT_ID'],
                client_secret=env['RAMP_CLIENT_SECRET']
            )
            client.authenticate()
            st.success("✅ Successfully authenticated with Ramp")
        except Exception as e:
            st.error("❌ Authentication failed. Please contact administrator.")
            return

    # Check available endpoints
    with st.spinner("🔍 Checking API availability..."):
        available_endpoints = check_available_endpoints(client, cfg)

    # Filter selected types to only available ones
    available_selected_types = [t for t in selected_types if available_endpoints.get(t, False)]

    if not available_selected_types:
        st.error("❌ None of the selected data types are available with your current API permissions")
        return

    if len(available_selected_types) < len(selected_types):
        unavailable = [t for t in selected_types if t not in available_selected_types]
        st.warning(f"⚠️ Some data types are not available: {', '.join(unavailable)}")

    # Progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()

    # Fetch and combine data
    combined_df = None
    total_records = 0
    processed_types = 0

    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')

    for data_type in available_selected_types:
        status_text.text(f"📊 Fetching {data_type} from {start_date_str} to {end_date_str}...")

        try:
            data, df = fetch_data_for_type(client, data_type, start_date_str, end_date_str, cfg)

            if data:
                st.success(f"✅ Found {len(data)} {data_type} records")
                total_records += len(data)

                # Combine dataframes
                if combined_df is None:
                    combined_df = df
                else:
                    combined_df = pd.concat([combined_df, df], ignore_index=True)
            else:
                st.info(f"ℹ️ No {data_type} data found for the specified period")

        except Exception as e:
            st.error(f"❌ Error fetching {data_type}: {str(e)}")
            continue

        processed_types += 1
        progress_bar.progress(processed_types / len(available_selected_types))

    progress_bar.empty()
    status_text.empty()

    if combined_df is None or combined_df.empty:
        st.error("❌ No data found for any of the specified types and periods.")
        return

    # Display summary
    st.success(f"🎉 Successfully processed {total_records} total records across {len(available_selected_types)} data types")

    # Display data preview
    st.subheader("📋 Data Preview")
    st.dataframe(combined_df.head(10), use_container_width=True)

    # Export files
    st.subheader("📁 Download Files")

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
            label="📊 Download Excel (.xlsx)",
            data=excel_buffer,
            file_name=f"Ramp_BC_Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    with col2:
        st.download_button(
            label="📄 Download CSV (.csv)",
            data=csv_buffer,
            file_name=f"Ramp_BC_Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )

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
    """Fetch data for a specific type and return (data, dataframe)"""
    if data_type == 'transactions':
        data = client.get_transactions(
            status=cfg['ramp'].get('status_filter'),
            start_date=start_date,
            end_date=end_date,
            page_size=cfg['ramp'].get('page_size', 200)
        )
        df = ramp_to_bc_rows(data, cfg)
    elif data_type == 'bills':
        data = client.get_bills(
            status='APPROVED',
            start_date=start_date,
            end_date=end_date,
            page_size=cfg['ramp'].get('page_size', 200)
        )
        df = ramp_bills_to_bc_rows(data, cfg)
    elif data_type == 'reimbursements':
        data = client.get_reimbursements(
            status='PAID',
            start_date=start_date,
            end_date=end_date,
            page_size=cfg['ramp'].get('page_size', 200)
        )
        df = ramp_reimbursements_to_bc_rows(data, cfg)
    elif data_type == 'cashbacks':
        data = client.get_cashbacks(
            start_date=start_date,
            end_date=end_date,
            page_size=cfg['ramp'].get('page_size', 200)
        )
        df = ramp_cashbacks_to_bc_rows(data, cfg)
    elif data_type == 'statements':
        data = client.get_statements(
            start_date=start_date,
            end_date=end_date,
            page_size=cfg['ramp'].get('page_size', 200)
        )
        df = ramp_statements_to_bc_rows(data, cfg)
    else:
        raise ValueError(f"Unknown data type: {data_type}")

    return data, df

# Export button
if st.sidebar.button("🚀 Run Export", type="primary", use_container_width=True):
    if not selected_types:
        st.error("❌ Please select at least one data type to export")
    elif start_date >= end_date:
        st.error("❌ Start date must be before end date")
    else:
        run_export(selected_types, start_date, end_date, cfg, env)

# Footer
st.markdown("---")
st.markdown("Built with ❤️ for Northwest Area Foundation")
st.markdown("*This tool exports Ramp data to Business Central General Journal format with proper accounting treatment.*")