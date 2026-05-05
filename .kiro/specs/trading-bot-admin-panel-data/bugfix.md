# Bugfix Requirements Document

## Introduction

The Django admin dashboard for the trading bot system displays incorrect status information: all indicators show as "off" (`bot_running=False`, `mt5_connected=False`, `telegram_connected=False`) and no trade data appears, even though the bot is actively executing trades. The root cause is a port mismatch — Django's `BOT_API_URL` environment variable is configured to point to port `2222` instead of the correct port `8001` where the FastAPI bot server runs. Additionally, the `_get()` helper in `trading/views.py` silently swallows all connection errors and returns empty defaults, making the misconfiguration invisible to operators.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN `BOT_API_URL` is set to a port where the FastAPI server is not listening (e.g., `http://127.0.0.1:2222`) THEN the system raises a `ConnectionRefusedError` internally

1.2 WHEN a `ConnectionRefusedError` or any other exception occurs inside `_get()` THEN the system silently returns empty defaults (`{}` or `{'items': []}`) with no error surfaced to the user or logs

1.3 WHEN `_get('/health')` returns an empty dict due to a connection failure THEN the system displays `bot_running=False`, `mt5_connected=False`, and `telegram_connected=False` on the dashboard regardless of the actual bot state

1.4 WHEN `_get('/trades')` and `_get('/open-trades')` return empty defaults due to a connection failure THEN the system displays zero open positions and no trade history on the dashboard

1.5 WHEN `bot/config.py` reads `API_PORT` from `bot/.env` (correctly set to `8001`) but Django's `.env` has `BOT_API_URL=http://127.0.0.1:2222` THEN the system connects to the wrong port, causing all dashboard data to be stale/empty

### Expected Behavior (Correct)

2.1 WHEN `BOT_API_URL` is set to a port where the FastAPI server is not listening THEN the system SHALL surface a visible connection error in the dashboard (e.g., a banner or status indicator showing "Bot API unreachable") instead of silently showing all-off defaults

2.2 WHEN a connection error occurs inside `_get()` THEN the system SHALL log the error (including the target URL and exception message) so operators can diagnose the misconfiguration

2.3 WHEN `BOT_API_URL` is not explicitly set in Django's environment THEN the system SHALL default to `http://127.0.0.1:8001`, matching the `API_PORT=8001` value in `bot/.env`

2.4 WHEN the FastAPI server is running on port `8001` and `BOT_API_URL` is correctly set to `http://127.0.0.1:8001` THEN the system SHALL display accurate live values for `bot_running`, `mt5_connected`, `telegram_connected`, open positions, and trade history

2.5 WHEN a connection error occurs THEN the system SHALL pass an `api_error` flag (or equivalent) to the dashboard template so the UI can distinguish between "bot is off" and "bot API is unreachable"

### Unchanged Behavior (Regression Prevention)

3.1 WHEN the FastAPI server is reachable and returns valid data THEN the system SHALL CONTINUE TO render the dashboard with the correct bot status, account info, open trades, and recent signals

3.2 WHEN `_post()` or `_put()` is called for bot control actions (start, stop, restart) THEN the system SHALL CONTINUE TO return `(ok, data)` tuples and propagate errors to the caller as before

3.3 WHEN the bot API returns a non-2xx HTTP status THEN the system SHALL CONTINUE TO treat it as an error and return the appropriate default or error response

3.4 WHEN `BOT_API_URL` and `BOT_API_KEY` are correctly configured in Django's environment THEN the system SHALL CONTINUE TO authenticate requests to the FastAPI server using the `X-API-Key` header

3.5 WHEN the dashboard is loaded by a non-staff user THEN the system SHALL CONTINUE TO redirect to the login page via the `@staff_member_required` decorator

---

## Bug Condition (Pseudocode)

**Bug Condition Function** — identifies the inputs that trigger the bug:

```pascal
FUNCTION isBugCondition(X)
  INPUT: X of type DashboardRequest
  OUTPUT: boolean

  // The bug fires when Django cannot reach the bot API
  RETURN (BOT_API_URL port ≠ API_PORT where FastAPI is listening)
      OR (FastAPI server process is not running)
END FUNCTION
```

**Property: Fix Checking** — correct behavior for buggy inputs:

```pascal
FOR ALL X WHERE isBugCondition(X) DO
  result ← dashboard'(X)
  ASSERT result.context contains api_error = True
  ASSERT result.context contains error_message describing the connection failure
  ASSERT error is logged with target URL and exception details
END FOR
```

**Property: Preservation Checking** — non-buggy inputs must be unaffected:

```pascal
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT dashboard(X) = dashboard'(X)   // same data rendered when API is reachable
END FOR
```
