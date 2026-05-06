# Bugfix Requirements Document

## Introduction

The trading bot dashboard displays "MT5 Offline" (red indicator) even when the bot status shows "Running". The bot is deployed on an Ubuntu VPS where the MetaTrader5 Python library is not available (`MT5_AVAILABLE = False`). The system is designed to use a Windows bridge architecture where MT5 operations are delegated to a separate Windows PC running `mt5_bridge_windows.py`. However, the current implementation in `bot/mt5_bridge.py` always returns `False` from `ensure_connected()` when `MT5_AVAILABLE = False`, preventing the dashboard from showing the correct MT5 connection status even when the Windows bridge is operational.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the bot runs on Ubuntu VPS where `MetaTrader5` library is not available THEN `MT5_AVAILABLE = False` is set in `bot/mt5_bridge.py`

1.2 WHEN `MT5_AVAILABLE = False` THEN `ensure_connected()` immediately returns `False` without checking if the Windows bridge is available

1.3 WHEN `ensure_connected()` returns `False` THEN the FastAPI `/health` endpoint returns `mt5_connected: False` to the Django dashboard

1.4 WHEN the Django dashboard receives `mt5_connected: False` THEN it displays "MT5 Offline" with a red indicator, even if the Windows bridge is running and connected to MT5

1.5 WHEN `get_account_info()`, `get_open_positions()`, and `get_trade_history()` are called with `MT5_AVAILABLE = False` THEN they return empty defaults (`{}` or `[]`) instead of delegating to the Windows bridge

1.6 WHEN the Windows bridge is running on port 8001 (as configured in `bot/.env`) but the VPS bot doesn't delegate to it THEN the dashboard shows USD 0.00 for Balance, Equity, and Free Margin

### Expected Behavior (Correct)

2.1 WHEN the bot runs on Ubuntu VPS where `MetaTrader5` library is not available THEN the system SHALL detect the Windows bridge configuration from environment variables (`BRIDGE_URL` or similar)

2.2 WHEN a Windows bridge URL is configured THEN `ensure_connected()` SHALL make an HTTP request to the bridge's `/health` endpoint to check MT5 connection status

2.3 WHEN the Windows bridge `/health` endpoint returns `{"mt5_connected": true}` THEN `ensure_connected()` SHALL return `True` to indicate MT5 is available via the bridge

2.4 WHEN `ensure_connected()` returns `True` via the bridge THEN the FastAPI `/health` endpoint SHALL return `mt5_connected: True` to the Django dashboard

2.5 WHEN the Django dashboard receives `mt5_connected: True` THEN it SHALL display "MT5 Connected" with a green indicator

2.6 WHEN `get_account_info()` is called and the Windows bridge is available THEN the system SHALL make an HTTP request to the bridge's `/account` endpoint and return the account data

2.7 WHEN `get_open_positions()` is called and the Windows bridge is available THEN the system SHALL make an HTTP request to the bridge's `/positions` endpoint and return the positions list

2.8 WHEN `get_trade_history()` is called and the Windows bridge is available THEN the system SHALL make an HTTP request to the bridge's `/history` endpoint and return the trade history

2.9 WHEN the Windows bridge is unreachable or returns an error THEN the system SHALL log the error and return `False` or empty defaults, maintaining the current "Offline" behavior

2.10 WHEN `open_trade()` is called and the Windows bridge is available THEN the system SHALL make an HTTP POST request to the bridge's `/trade` endpoint with the trade parameters

2.11 WHEN `modify_position()` is called and the Windows bridge is available THEN the system SHALL make an HTTP PUT request to the bridge's `/positions/{position_id}` endpoint

### Unchanged Behavior (Regression Prevention)

3.1 WHEN the bot runs on Windows with `MetaTrader5` library available (`MT5_AVAILABLE = True`) THEN the system SHALL CONTINUE TO use direct MT5 API calls without delegating to the bridge

3.2 WHEN `ensure_connected()` is called on Windows with direct MT5 connection THEN the system SHALL CONTINUE TO call `mt5.terminal_info()` to check connection status

3.3 WHEN the Windows bridge is not configured (no `BRIDGE_URL` environment variable) and `MT5_AVAILABLE = False` THEN the system SHALL CONTINUE TO return `False` from `ensure_connected()` and show "MT5 Offline"

3.4 WHEN any MT5 operation fails (either direct or via bridge) THEN the system SHALL CONTINUE TO log the error and return appropriate error responses

3.5 WHEN the FastAPI server authentication is required THEN the system SHALL CONTINUE TO use the `X-API-Key` header for bridge requests

3.6 WHEN the dashboard displays connection status THEN the system SHALL CONTINUE TO show the three status indicators: Bot Status, MT5, and Telegram

---

## Bug Condition (Pseudocode)

**Bug Condition Function** — identifies the inputs that trigger the bug:

```pascal
FUNCTION isBugCondition(X)
  INPUT: X of type BotEnvironment
  OUTPUT: boolean

  // The bug fires when:
  // 1. Bot runs on Ubuntu (MT5_AVAILABLE = False)
  // 2. Windows bridge is running and connected to MT5
  // 3. But ensure_connected() returns False without checking the bridge
  RETURN (X.MT5_AVAILABLE = False) 
     AND (X.BRIDGE_URL is configured)
     AND (Windows bridge is running and MT5 is connected)
END FUNCTION
```

**Property: Fix Checking** — correct behavior for buggy inputs:

```pascal
FOR ALL X WHERE isBugCondition(X) DO
  result ← ensure_connected'(X)
  bridge_health ← HTTP_GET(X.BRIDGE_URL + "/health")
  ASSERT result = bridge_health.mt5_connected
  ASSERT dashboard displays "MT5 Connected" with green indicator
  ASSERT account_info ← get_account_info'(X) contains balance > 0
END FOR
```

**Property: Preservation Checking** — non-buggy inputs must be unaffected:

```pascal
FOR ALL X WHERE NOT isBugCondition(X) DO
  // Case 1: Windows with direct MT5 (MT5_AVAILABLE = True)
  IF X.MT5_AVAILABLE = True THEN
    ASSERT ensure_connected(X) = ensure_connected'(X)
    ASSERT uses direct mt5.terminal_info() call
  END IF
  
  // Case 2: Ubuntu without bridge configured
  IF X.MT5_AVAILABLE = False AND X.BRIDGE_URL is not configured THEN
    ASSERT ensure_connected'(X) = False
    ASSERT dashboard displays "MT5 Offline"
  END IF
  
  // Case 3: Bridge configured but unreachable
  IF X.BRIDGE_URL is configured AND bridge is unreachable THEN
    ASSERT ensure_connected'(X) = False
    ASSERT error is logged
  END IF
END FOR
```

---

## Implementation Notes

**Environment Configuration:**
- Add `MT5_BRIDGE_URL` to `bot/.env` (e.g., `http://localhost:8001` or Windows PC IP)
- Add `MT5_BRIDGE_API_KEY` to `bot/.env` (should match `API_KEY` in Windows bridge)

**Bridge Detection Logic:**
```python
# In bot/mt5_bridge.py
BRIDGE_URL = os.getenv("MT5_BRIDGE_URL", "").strip()
BRIDGE_API_KEY = os.getenv("MT5_BRIDGE_API_KEY", "")
USE_BRIDGE = not MT5_AVAILABLE and bool(BRIDGE_URL)
```

**HTTP Client:**
- Use `requests` library for bridge communication
- Set timeout (e.g., 5 seconds) to avoid blocking
- Include `X-API-Key` header for authentication
- Handle connection errors gracefully

**Affected Functions:**
- `ensure_connected()` - Check bridge `/health` endpoint
- `get_account_info()` - Delegate to bridge `/account`
- `get_open_positions()` - Delegate to bridge `/positions`
- `get_trade_history()` - Delegate to bridge `/history`
- `open_trade()` - Delegate to bridge `/trade`
- `modify_position()` - Delegate to bridge `/positions/{id}`
- `calculate_lot_with_risk()` - Fetch account info via bridge for calculations
