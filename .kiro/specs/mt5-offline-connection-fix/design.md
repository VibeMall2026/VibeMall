# MT5 Offline Connection Fix - Bugfix Design

## Overview

The trading bot dashboard incorrectly displays "MT5 Offline" (red indicator) when running on Ubuntu VPS, even though the Windows bridge is operational and connected to MT5. The root cause is that `bot/mt5_bridge.py` immediately returns `False` from `ensure_connected()` when `MT5_AVAILABLE = False`, without checking if a Windows bridge is configured and available.

The fix implements bridge delegation logic: when the MetaTrader5 Python library is unavailable (Ubuntu VPS), the system will detect the Windows bridge configuration from environment variables and delegate all MT5 operations to the bridge via HTTP requests. This allows the dashboard to correctly display MT5 connection status and account information by querying the bridge instead of attempting direct MT5 API calls.

## Glossary

- **Bug_Condition (C)**: The condition that triggers the bug - when the bot runs on Ubuntu (`MT5_AVAILABLE = False`), a Windows bridge is configured and operational, but `ensure_connected()` returns `False` without checking the bridge
- **Property (P)**: The desired behavior - `ensure_connected()` should query the bridge's `/health` endpoint and return the actual MT5 connection status from the bridge
- **Preservation**: Existing direct MT5 connection behavior on Windows that must remain unchanged by the fix
- **MT5_AVAILABLE**: Boolean flag set to `False` when the MetaTrader5 Python library cannot be imported (Ubuntu/Linux), `True` on Windows
- **Windows Bridge**: A separate FastAPI server (`mt5_bridge_windows.py`) running on a Windows PC that has direct access to MT5 via the MetaTrader5 Python library
- **Bridge Delegation**: The pattern of forwarding MT5 operations from the VPS bot to the Windows bridge via HTTP requests
- **ensure_connected()**: Function in `bot/mt5_bridge.py` that checks MT5 connection status and is called by the `/health` endpoint
- **BRIDGE_URL**: Environment variable (e.g., `http://192.168.1.100:8001`) that specifies the Windows bridge server address
- **USE_BRIDGE**: Boolean flag that determines whether to use bridge delegation (`True` when `MT5_AVAILABLE = False` and `BRIDGE_URL` is configured)

## Bug Details

### Bug Condition

The bug manifests when the bot runs on Ubuntu VPS where the MetaTrader5 Python library is not available. The `ensure_connected()` function immediately returns `False` without checking if a Windows bridge is configured and operational, causing the dashboard to display "MT5 Offline" even when the bridge is running and connected to MT5.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type BotEnvironment
  OUTPUT: boolean
  
  RETURN input.MT5_AVAILABLE = False
         AND input.BRIDGE_URL is configured (not empty)
         AND Windows bridge is running and MT5 is connected
         AND ensure_connected() returns False (without checking bridge)
END FUNCTION
```

### Examples

- **Ubuntu VPS with bridge configured**: Bot runs on Ubuntu, `MT5_AVAILABLE = False`, `BRIDGE_URL = "http://192.168.1.100:8001"`, Windows bridge is running and connected to MT5, but dashboard shows "MT5 Offline" (red) instead of "MT5 Connected" (green)
- **Ubuntu VPS with bridge showing account data**: Windows bridge returns `{"balance": 10000, "equity": 10050, "margin_free": 9500}`, but dashboard displays "Balance: USD 0.00, Equity: USD 0.00, Free Margin: USD 0.00" because `get_account_info()` returns `{}`
- **Ubuntu VPS with open positions**: Windows bridge has 3 open positions, but dashboard shows "Open Trades: 0" because `get_open_positions()` returns `[]`
- **Edge case - Bridge unreachable**: Windows bridge is configured but offline/unreachable, system should return `False` and log error (expected behavior - should show "MT5 Offline")

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Direct MT5 connection on Windows must continue to work exactly as before (when `MT5_AVAILABLE = True`)
- When no bridge is configured (`BRIDGE_URL` is empty) and `MT5_AVAILABLE = False`, system must continue to return `False` and show "MT5 Offline"
- Error handling and logging for failed MT5 operations must remain unchanged
- FastAPI authentication using `X-API-Key` header must continue to work for all endpoints
- Dashboard display of three status indicators (Bot Status, MT5, Telegram) must remain unchanged

**Scope:**
All inputs that do NOT involve Ubuntu VPS with a configured Windows bridge should be completely unaffected by this fix. This includes:
- Windows environments with direct MT5 connection (`MT5_AVAILABLE = True`)
- Ubuntu environments without bridge configuration (`BRIDGE_URL` not set)
- Any environment where the bridge is unreachable or returns errors

## Hypothesized Root Cause

Based on the bug description, the most likely issues are:

1. **Missing Bridge Detection Logic**: The code does not check for `BRIDGE_URL` environment variable or determine whether to use bridge delegation
   - No `BRIDGE_URL` or `BRIDGE_API_KEY` environment variables are read from `bot/.env`
   - No `USE_BRIDGE` flag is set based on `MT5_AVAILABLE` and `BRIDGE_URL` configuration

2. **Early Return in ensure_connected()**: The function returns `False` immediately when `MT5_AVAILABLE = False` without attempting bridge communication
   - Line in `ensure_connected()`: `if not MT5_AVAILABLE: return False`
   - No HTTP request is made to check bridge status

3. **No HTTP Client Implementation**: The code lacks HTTP client logic to communicate with the Windows bridge
   - No `requests` library imports or HTTP request functions
   - No error handling for network timeouts or connection failures

4. **Missing Bridge Delegation in Data Functions**: Functions like `get_account_info()`, `get_open_positions()`, and `get_trade_history()` return empty defaults instead of delegating to the bridge
   - These functions check `MT5_AVAILABLE` and return `{}` or `[]` without checking `USE_BRIDGE`

## Correctness Properties

Property 1: Bug Condition - Bridge Connection Status Check

_For any_ environment where `MT5_AVAILABLE = False` and `BRIDGE_URL` is configured, the fixed `ensure_connected()` function SHALL make an HTTP GET request to `{BRIDGE_URL}/health` and return `True` if the bridge responds with `{"mt5_connected": true}`, enabling the dashboard to display "MT5 Connected" with a green indicator.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**

Property 2: Preservation - Direct MT5 Connection Behavior

_For any_ environment where `MT5_AVAILABLE = True` (Windows with direct MT5), the fixed code SHALL produce exactly the same behavior as the original code, continuing to use direct `mt5.terminal_info()` calls without attempting bridge communication, preserving all existing Windows MT5 connection logic.

**Validates: Requirements 3.1, 3.2, 3.4**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `bot/mt5_bridge.py`

**Function**: Module-level configuration and multiple functions

**Specific Changes**:

1. **Add Bridge Configuration Detection** (after imports, before `connect()` function):
   - Import `requests` library for HTTP communication
   - Read `MT5_BRIDGE_URL` from environment variables using `os.getenv()`
   - Read `MT5_BRIDGE_API_KEY` from environment variables
   - Set `USE_BRIDGE = not MT5_AVAILABLE and bool(BRIDGE_URL)` to determine delegation mode
   - Log bridge configuration status for debugging

2. **Create Bridge HTTP Helper Function**:
   - Add `_call_bridge(endpoint: str, method: str = "GET", json_data: dict = None) -> dict` function
   - Include `X-API-Key` header with `BRIDGE_API_KEY` value
   - Set timeout to 5 seconds to avoid blocking
   - Handle `requests.exceptions.RequestException` and log errors
   - Return `None` on failure for graceful degradation

3. **Update ensure_connected() Function**:
   - Add bridge delegation logic: `if USE_BRIDGE: return _check_bridge_health()`
   - Create `_check_bridge_health()` helper that calls `_call_bridge("/health")`
   - Parse response and return `response.get("mt5_connected", False)`
   - Keep existing direct MT5 logic unchanged for Windows

4. **Update get_account_info() Function**:
   - Add bridge delegation: `if USE_BRIDGE: return _call_bridge("/account") or {}`
   - Keep existing direct MT5 logic unchanged

5. **Update get_open_positions() Function**:
   - Add bridge delegation: `if USE_BRIDGE: return _call_bridge("/positions") or []`
   - Keep existing direct MT5 logic unchanged

6. **Update get_trade_history() Function**:
   - Add bridge delegation: `if USE_BRIDGE: return _call_bridge(f"/history?limit={limit}") or []`
   - Keep existing direct MT5 logic unchanged

7. **Update open_trade() Function**:
   - Add bridge delegation: `if USE_BRIDGE: return _call_bridge("/trade", method="POST", json_data={...})`
   - Build JSON payload with all trade parameters (symbol, side, order_type, sl, tp, entry, risk_percent, comment)
   - Keep existing direct MT5 logic unchanged

8. **Update modify_position() Function**:
   - Add bridge delegation: `if USE_BRIDGE: return _call_bridge(f"/positions/{position_id}", method="PUT", json_data={...})`
   - Build JSON payload with sl and tp parameters
   - Keep existing direct MT5 logic unchanged

9. **Update calculate_lot_with_risk() Function**:
   - Add bridge delegation to fetch account info: `if USE_BRIDGE: account = _call_bridge("/account")`
   - Extract balance from bridge response for lot calculation
   - Note: Symbol info still needs to be available locally or fetched from bridge (may require additional bridge endpoint)

10. **Add Environment Variables to bot/.env**:
    - Add `MT5_BRIDGE_URL=http://192.168.1.100:8001` (example, user will configure actual IP)
    - Add `MT5_BRIDGE_API_KEY=Paladiya@2023` (should match `API_KEY` in Windows bridge)

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write tests that simulate Ubuntu VPS environment with Windows bridge configured. Mock the environment variables and HTTP responses. Run these tests on the UNFIXED code to observe failures and understand the root cause.

**Test Cases**:
1. **Ubuntu with Bridge - Connection Status Test**: Set `MT5_AVAILABLE = False`, configure `BRIDGE_URL`, mock bridge `/health` returning `{"mt5_connected": true}`, call `ensure_connected()` (will fail on unfixed code - returns `False` without checking bridge)
2. **Ubuntu with Bridge - Account Info Test**: Set `MT5_AVAILABLE = False`, configure `BRIDGE_URL`, mock bridge `/account` returning account data, call `get_account_info()` (will fail on unfixed code - returns `{}`)
3. **Ubuntu with Bridge - Open Positions Test**: Set `MT5_AVAILABLE = False`, configure `BRIDGE_URL`, mock bridge `/positions` returning positions list, call `get_open_positions()` (will fail on unfixed code - returns `[]`)
4. **Ubuntu without Bridge Test**: Set `MT5_AVAILABLE = False`, no `BRIDGE_URL` configured, call `ensure_connected()` (may pass on unfixed code - should return `False`)

**Expected Counterexamples**:
- `ensure_connected()` returns `False` even when bridge is available and connected
- `get_account_info()` returns `{}` even when bridge returns valid account data
- Possible causes: missing bridge detection logic, early return in functions, no HTTP client implementation

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := ensure_connected_fixed(input)
  bridge_response := HTTP_GET(input.BRIDGE_URL + "/health")
  ASSERT result = bridge_response.mt5_connected
  ASSERT dashboard displays correct MT5 status
  ASSERT get_account_info_fixed(input) returns bridge account data
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT ensure_connected_original(input) = ensure_connected_fixed(input)
  ASSERT get_account_info_original(input) = get_account_info_fixed(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan**: Observe behavior on UNFIXED code first for Windows direct MT5 connection and Ubuntu without bridge, then write property-based tests capturing that behavior.

**Test Cases**:
1. **Windows Direct MT5 Preservation**: Observe that `ensure_connected()` calls `mt5.terminal_info()` on Windows, then write test to verify this continues after fix
2. **Ubuntu No Bridge Preservation**: Observe that `ensure_connected()` returns `False` when no bridge is configured, then write test to verify this continues after fix
3. **Error Handling Preservation**: Observe that failed MT5 operations log errors and return appropriate responses, then write test to verify this continues after fix
4. **Authentication Preservation**: Observe that FastAPI endpoints require `X-API-Key` header, then write test to verify this continues after fix

### Unit Tests

- Test bridge configuration detection (reads environment variables correctly)
- Test `_call_bridge()` helper function with various endpoints and methods
- Test `_check_bridge_health()` with different bridge responses
- Test each delegated function (account info, positions, history, trade, modify) with mocked bridge responses
- Test error handling when bridge is unreachable (timeout, connection error)
- Test that direct MT5 logic is unchanged on Windows

### Property-Based Tests

- Generate random environment configurations (Windows/Ubuntu, bridge configured/not configured) and verify correct delegation mode is selected
- Generate random bridge responses and verify functions parse them correctly
- Generate random MT5 operations and verify they are delegated correctly when `USE_BRIDGE = True`
- Test that all non-bridge environments continue to work across many scenarios

### Integration Tests

- Test full dashboard flow: VPS bot → bridge → MT5 → bridge → VPS bot → dashboard
- Test switching between direct MT5 (Windows) and bridge delegation (Ubuntu) modes
- Test that dashboard displays correct status indicators after fix
- Test that account data, positions, and trade history are displayed correctly via bridge
- Test that trade execution works correctly via bridge (open trade, modify position)
