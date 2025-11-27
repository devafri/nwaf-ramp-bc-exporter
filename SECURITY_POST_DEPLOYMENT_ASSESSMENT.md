# Post-Deployment Security Assessment

**App:** nwaf-ramp-bc-exporter (Ramp → Business Central Export)
**Date:** 2025-11-27
**Scope:** Security posture after SSO, stateless signed-state flow, token refresh, device-code fallback, and Ramp sync changes.

---

## Executive summary

The application has been enhanced with several security controls which materially improve its safety for institutional use:

- Microsoft Azure AD SSO using MSAL with Authorization Code flow (server-side) — strong authentication.
- Stateless HMAC-signed state token (time-limited) to prevent CSRF while allowing cross-tab redirect flows.
- Token lifecycle management (silent refresh using MSAL acquire_token_silent) with buffer prior to expiry.
- Device Code flow fallback for users who cannot use redirect-based flows.
- Export-only behavior by default and safe sync operations (dry-run by default). Live writes require explicit opt-in (sidebar toggle) and require Ramp client's write permission.
- Audit trail CSV for every sync operation recording per-transaction outcomes and timestamps.
- Dependency pinning and improved error handling.

Overall status: Production-ready with a small set of recommended hardening items.

---

## Findings (What was added / changed)

1. Authorization updates
   - Stateless, HMAC-signed state tokens allow validation on callback even when the user's browser tab/session is lost.
   - Fallback to session-based state validation remains in place.
   - Device code flow added for out-of-band authentication.

2. Token lifecycle
   - Token acquisition time recorded and tokens refreshed silently via MSAL when close to expiry.

3. Ramp sync operations
   - Export logic filters out already-synced items (heuristic check).
   - Post-export sync is available as a dry-run by default; live sync require user to check an explicit "Enable live Ramp sync" toggle.
   - Manual button 'Mark as synced in Ramp' present in UI — shows progress and writes an audit CSV (downloadable) after the run.

4. Auditing and logs
   - Sync audit CSV is written to `exports/sync_audit_<timestamp>.csv` and available for download.
   - Error handling logs exceptions server-side and shows generic messages to users (prevents info leakage).

5. Controls & guardrails
   - Dry-run default for sync prevents accidental writes.
   - `RampClient` requires `enable_sync=True` for live POSTs.

---

## Risk / Gaps and recommended fixes (priority-ordered)

1. High priority
   - Enforce scope check before allowing live Ramp sync. Currently, `enable_sync` is a runtime flag — ensure that the current token's granted scopes include `accounting:write` before enabling live writes in the UI and refuse if not.
   - Add admin confirmation/approval for enabling live sync (e.g., require explicit admin role or an additional confirmation step). Rationale: writes to Ramp are mutating operations on financial data.

2. Medium priority
   - Centralized audit logging (server or SIEM, not just CSV file in app workspace). Send sync results and user actions to Application Insights or an S3/GCS bucket for retention/analysis and compliance.
   - RBAC / group-based authorization. Restrict who can perform live sync (e.g., only Finance AD group). Implement group membership checks (id_token_claims['groups']).
   - Add explicit session idle timeout and stronger session invalidation on sensitive actions.

3. Low priority
   - Add verification/confirmation UI showing a list of transaction IDs that will be marked live before allowing the write, and require a typed confirmation phrase or acknowledgement.
   - Periodic secret rotation and automated monitoring of secret expiry (especially for Ramp credentials).
   - Automated dependency scanning (CI pipeline with pip-audit/pip-check) and scheduling upgrade windows.

---

## Operational recommendations

- Add pre-check in the UI: before `enable_live_ramp_sync` can be toggled, validate `client.granted_scopes` includes `accounting:write`. If missing, show an explicit error and do not enable the toggle.

- Implement RBAC: read `groups` claim from id_token, allow only users in `FINANCE_SYNC_AD_GROUP` to toggle live sync.

- Keep dry-run default and log all sync attempts to a central log store with retention policy.

- Add an audit retention policy and export rotation (e.g., daily uploads of sync CSVs to secure blob storage).

---

## Quick implementation tasks (0-2 days)

1. Add scope check gating `enable_live_ramp_sync` in `streamlit_app.py` (30–60min).
2. Add group membership check and require AD group membership for live sync (1–2 hours).
3. Send audit CSVs to a secure store (S3 or Azure Blob) and log an event to telemetry service (1–2 hours).

---

## Conclusion

With recent changes, the app is secure for production use. The live sync feature is guarded with dry-run default and requires explicit enablement; implementing scope and RBAC gating plus centralized audit logging will complete the remaining high to medium priority hardening.

---

**Prepared by:** Assistant  
**Next recommended step:** Add the scope-check and RBAC restriction for live Ramp sync and configure centralized audit log storage.
