# PHASE 17B — KITE AUTHENTICATION LIFECYCLE + INTRADAY DATA LAYER AUDIT

## Executive Summary

Phase 17B transforms Nomad Analyst's Phase 17A Kite Connect integration into a robust, personal-use daily workflow and establishes the normalized intraday market-data layer.

The core design principle is:
```text
MANUAL 2FA ONCE/DAY (Zerodha Web Portal)
        ↓
AUTOMATIC REQUEST-TOKEN CAPTURE (http://127.0.0.1:8000/kite/callback/)
        ↓
AUTOMATIC ACCESS-TOKEN GENERATION (Server-Side Secret Exchange)
        ↓
ENCRYPTED LOCAL STORAGE AT REST (Fernet AES-128-CBC / SHA-256)
        ↓
KITE PROVIDER & WEBSOCKET TICKER
        ↓
NOMAD MARKET DATA LAYER
```

The user never needs to copy/paste request tokens or access tokens manually. The only manual action required is authenticating on the official Zerodha login page once per day.

---

## 1. Authentication Lifecycle Architecture

### 1.1 Secure Fernet Encryption at Rest
Zerodha Kite Connect access tokens grant read/query capabilities to live market feeds. To preserve security and prevent token leakage:
- Access tokens are **never** stored in plain text in the database.
- A dedicated model `KiteCredential` (`market/models.py`, Migration `0021_kitecredential.py`) encrypts tokens using `Fernet` symmetric encryption keyed by a SHA-256 derivation of Django's `SECRET_KEY`.
- Helper methods `set_access_token(plain)` and `get_access_token() -> str` handle encryption and decryption transparently.
- Plaintext tokens are strictly forbidden from appearing in frontend responses, loggers, or git repositories.

### 1.2 Daily 06:00 IST Expiry Enforcement
Zerodha invalidates all active sessions every morning at ~06:00 IST.
`KiteCredentialService.calculate_expiry(authenticated_at: datetime)`:
- Normalizes to `Asia/Kolkata` (IST).
- If authenticated before 06:00 IST, expires at 06:00 IST that same day.
- If authenticated after 06:00 IST, expires at 06:00 IST the following calendar day.
- Whenever `KiteCredentialService.get_valid_access_token()` is invoked, it checks current timestamp against `expires_at`. If expired, the status is automatically transitioned to `EXPIRED` and `None` is returned, preventing stale API requests.

### 1.3 OAuth Initiation, Callback & Disconnect
1. **Initiate Login**: `GET /api/v1/kite/auth/login-url/` generates:
   `https://kite.zerodha.com/connect/login?api_key={KITE_API_KEY}&v=3&redirect_url=http%3A%2F%2F127.0.0.1%3A8000%2Fkite%2Fcallback%2F`
2. **Callback Handling**: `GET /kite/callback/`:
   - Receives `request_token`, `status`, and `action`.
   - On cancellation/error, redirects to frontend with error query parameters: `?kite_auth=cancelled&error=...`.
   - On success, exchanges `request_token` server-side via `kiteconnect.generate_session(..., api_secret=KITE_API_SECRET)`.
   - Stores encrypted token, user ID, user name, and expiry in `KiteCredential`.
   - Redirects user back to frontend: `http://localhost:5173/intraday?kite_auth=success`.
3. **Safe Status**: `GET /api/v1/kite/status/`:
   - Returns `{ configured, authenticated, status, user_id, user_name, expires_at, authenticated_at, last_error }`.
   - **Zero Secrets**: `access_token`, `api_secret`, and `request_token` are strictly omitted.
4. **Session Disconnect**: `POST /api/v1/kite/auth/disconnect/`:
   - Clears encrypted token, resets status to `AUTHENTICATION_REQUIRED`.

---

## 2. Intraday Market Data Layer & Normalization

### 2.1 Plausible Trading Session & Timestamp Validation
Indian equity markets operate on strict trading hours:
- Pre-market: 09:00 – 09:15 IST
- Regular Trading: 09:15 – 15:30 IST
- Post-closing: 15:30 – 16:05 IST
- Closed / Off-hours: 16:05 – 09:00 IST next trading day, and weekends/holidays.

`TradingSessionService.is_plausible_exchange_timestamp(dt: datetime) -> bool`:
- Enforces exchange timestamp plausibility within 09:00 to 16:05 IST on active trading days.
- In `market/normalizers/kite.py`, `NomadMarketTick` contains an `is_suspicious_timestamp: bool` flag.
- Off-hours ticks (e.g. heartbeat or replayed ticks received at night like 22:24 IST) are logged with a warning and tagged `is_suspicious_timestamp=True` to prevent corrupting intraday indicators or bar aggregates.

### 2.2 Idempotent Historical Bar Ingestion
`KiteHistoricalIngestionService` (`market/services/kite_historical.py`) and command `ingest_kite_historical`:
- Fetches 1-minute, 5-minute, 15-minute, or 1-day candles via `KiteConnect.historical_data()`.
- Normalizes bars into `OHLCVBar` instances.
- Performs idempotent bulk upsert using `OHLCVBar.objects.bulk_create(..., update_conflicts=True, unique_fields=['instrument', 'interval', 'timestamp'])`.
- Verified in tests: Running ingestion twice produces 0 duplicate records.

### 2.3 System Data Health API
`GET /api/v1/kite/data-health/`:
- Computes comprehensive operational health metrics:
  - `market_session`: `REGULAR_TRADING`, `CLOSED`, `PRE_MARKET`, etc.
  - `is_market_open`: boolean indicator.
  - `kite_auth_status`: `CONNECTED`, `AUTHENTICATION_REQUIRED`, `EXPIRED`, etc.
  - `instruments_mapped`: count of mapped active instruments.
  - `last_tick_timestamp` & `last_tick_age_seconds`: live freshness.
  - `bars_today_count`: count of bars stored today.
  - `health_verdict`: `LIVE_STREAMING`, `MARKET_CLOSED_STANDBY`, `AUTH_REQUIRED`, or `FEED_STALE`.

---

## 3. Frontend Experience

1. **Top Header Status Badge**:
   - Displays real-time Kite session state (`Connected`, `Auth Required`, `Expired`).
   - Clicking the badge opens the `KiteAuthModal`.
2. **Kite Auth Modal**:
   - Shows connection status, user ID, session expiry time in IST, and instructions.
   - Provides 1-click `Authenticate with Zerodha` button that redirects to the Kite OAuth flow.
   - Allows clean `Disconnect` action to clear session tokens.
3. **Intraday Page Data Health Card**:
   - Displays Market Session, Data Health Verdict, Mapped Instruments count, and Bars Ingested count.
   - Features a banner notifying user when authentication completes successfully.

---

## 4. Test Verification Results

### 4.1 Backend Test Suite
```bash
venv/bin/python manage.py test market.tests.KiteAuthAndDataLayerTests -v 2
```
- `test_historical_ingestion_idempotent_upsert` ... OK
- `test_kite_callback_cancellation_and_error_handling` ... OK
- `test_kite_data_health_endpoint` ... OK
- `test_kite_disconnect_endpoint` ... OK
- `test_kite_login_url_generation` ... OK
- `test_kite_safe_status_endpoint_security` ... OK
- `test_kite_token_exchange_and_encryption` ... OK
- `test_kite_token_expiry_evaluation` ... OK
- `test_plausible_exchange_timestamp` ... OK
**Result**: 9/9 Passed (100%).

Full Market Test Suite:
```bash
venv/bin/python manage.py test market
```
**Result**: 262/262 Passed (100%, 0 failures, 0 errors).

### 4.2 Frontend Test Suite
```bash
npm run test
```
- 18 test files passed, 72/72 unit tests passed (100%).
- Production build (`npm run build`) succeeded with 0 TypeScript/Vite errors.

---

## 5. Explicit Operational Limitation

> [!WARNING]
> **LIVE MARKET STREAM VERIFICATION LIMITATION**:
> Because validation was executed outside Indian exchange operating hours (22:55+ IST), live WebSocket market streaming from the National Stock Exchange cannot be claimed as verified live.
> 
> **Status**: LIVE MARKET STREAM IMPLEMENTATION READY; REAL-MARKET VALIDATION PENDING NEXT NSE SESSION (09:15–15:30 IST).
