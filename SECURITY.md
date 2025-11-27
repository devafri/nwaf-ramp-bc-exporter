# SECURITY.md — Ramp → Business Central Export

Last updated: 2025-11-27

This repository contains a Streamlit application used by Northwest Area Foundation teams to export Ramp financial data into Business Central General Journal format.

This document explains the app's security posture, responsible disclosure, and operational guidelines for safe use and maintenance.

---

## Summary / Scope

- Authentication: Microsoft Azure Active Directory (OAuth 2.0 Authorization Code flow via MSAL) with a device-code fallback if needed.
- CSRF protection: state parameter validation using a server-side-state AND stateless signed state (HMAC + timestamp) so redirects are safe across tabs.
- Token management: tokens are stored in user session state and refreshed silently with a short buffer before expiry.
- Ramp sync operations: The app filters out already-synced items and supports post-export marking of transactions as synced in Ramp. Live writes are disabled by default and require explicit opt-in.
- Auditability: each sync run produces an audit CSV (exports/sync_audit_<timestamp>.csv) listing per-transaction outcomes.

---

## Responsible Disclosure / Security Contact

If you discover a vulnerability in this application, please follow these steps:

1. Do not exploit the issue. Avoid unauthorized data access or modification.
2. Contact the security owner: security@nwaf.org (or your internal security channel).
3. Provide: brief description, steps to reproduce, potential impact, any relevant logs/screenshots, and your suggested mitigation if possible.
4. If you don’t receive a response within 48 hours, escalate to the project owner or manager listed in the project README.

This repository does not publish a public bug bounty — handle disclosures privately.

---

## Safe Operation Rules (for administrators and operators)

- Keep "Enable live Ramp sync" turned OFF unless you explicitly intend to mark Ramp transactions as synced. The default operation is dry-run (no writes).
- In order to perform live writes, the Azure AD token used must have the `accounting:write` scope. The app will (or should) validate that the current granted scopes include the required write scope before enabling or performing any write operations.
- Limit production live sync permission: allow only authorized finance team members to toggle live sync. Implement group-based RBAC in Azure AD (recommended group: financial-sync-ad-group) and check `id_token` groups before allowing live writes.
- Ensure that Ramp client ID/secret and Azure client secret are stored in the Streamlit Cloud secrets (never in source, never in logs).

---

## Operational Controls & Monitoring

- Audit CSVs: After any sync run (manual or automated), an audit CSV is produced in `exports/` and offered for download. These files should be retained and uploaded to a protected, centralized log store (e.g., Azure Blob Storage or S3) for long-term retention and compliance.
- Access logs: Use Azure AD sign-in logs to examine user activity and suspicious attempts.
- Secret rotation: Rotate Azure and Ramp client secrets regularly (every 90 days recommended). Store rotation dates in operational runbooks.
- Vulnerability scanning: Run `pip-audit` or similar tools in CI to scan dependency vulnerabilities and schedule periodic upgrades.

---

## Code-level Security Notes (high-level)

- CSRF: The stateless signed-state uses HMAC over a timestamped payload with the Azure client secret as HMAC key; tokens are short-lived (default TTL 10 minutes). The app still attempts session-based state validation where available.
- Tokens: The app stores tokens in `st.session_state` (server-side) and uses MSAL's `acquire_token_silent()` to refresh tokens. For the device flow the app uses a PublicClientApplication flow.
- Audit: The app writes sync audit CSV files (no secrets written) and shows generic error messages in the UI while logging details server-side.
- Mutations: Ramp write operations are gated behind `enable_sync` and should require the `accounting:write` permission.

---

## Recommended Next Steps / Hardening

1. Enforce write-scope validation in the UI/backend before allowing `enable_sync` or executing write operations.
2. Implement RBAC: require a specific Azure AD group to enable live sync.
3. Centralize audit file storage and configure retention (upload audit CSVs to a protected object store automatically).
4. Add stronger session timeout and re-authentication on critical actions.
5. Add automated dependency scanning + a security-runbook for rotating secrets and handling incidents.

---

## Changes in this repository related to security (recent)

- Implemented a stateless signed-state to support cross-tab OAuth redirects and protect against CSRF.
- Added device-code authentication flow.
- Implemented token refresh, improved error handling, and dependency pinning.
- Added unsynced-only exports, safe dry-run post-export sync, manual sync button, and downloadable sync audit CSVs.
- Provided SECURITY_POST_DEPLOYMENT_ASSESSMENT.md and SECURITY_IMPLEMENTATION.md for detailed operational info.

---

## Maintainers

- Project lead: Felix Isuk <Fisuk@nwaf.org>
- Security contact: security@nwaf.org

---

If you need me to add enforcement gates (scope checks and RBAC) to prevent accidental live syncs, I can implement those next and push changes to the repository.
