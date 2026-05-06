# MT5 Offline Connection Fix - Implementation Tasks

## Overview

This task list implements the Windows bridge delegation fix for the MT5 offline connection bug. The implementation adds HTTP-based bridge communication to `bot/mt5_bridge.py`, allowing the Ubuntu VPS bot to delegate MT5 operations to a Windows PC running `mt5_bridge_windows.py`.

---

## Phase 1: Bridge Configuration and HTTP Client

### 1.1 Add Bridge Configuration Detection

**Objective**: Read bridge configuration from environment variables and determine delegation mode.

**Steps**:
1. Add `import requests` at the top of `bot/mt5_bridge.py` (after existing imports)
2. Add `import os` if not already present
3. After the `MT5_AVAILABLE` flag definition, add:
   ```python
   # Bridge configuration (for Ubuntu VPS → Windows PC delegation)
   BRIDGE_URL = os.getenv("MT5_BRIDGE_URL", "").strip()
   BRIDGE_API_KEY = os.getenv("MT5_BRIDGE_API_KEY", "")
   USE_BRIDGE = not MT5_AVAILABLE and bool(BRIDGE_URL)
   ```
4. Add logging statement:
   ```python
   if USE_BRIDGE:
       logger.info(f"Bridge mode enabled: {BRIDGE_URL}")
   elif not MT5_AVAILABLE:
       logger.warning("MT5 not available and no bridge configured")
   ```

**Acceptance Criteria**:
- `BRIDGE_URL` is read from environment variable `MT5_BRIDGE_URL`
- `BRIDGE_API_KEY` is read from environment variable `MT5_BRIDGE_API_KEY`
- `USE_BRIDGE` is `True` only when `MT5_AVAILABLE = False` and `BRIDGE_URL` is not empty
- Appropriate log messages are displayed based on configuration

---

### 1.2 Create Bridge HTTP Helper Function

**Objective**: Implement HTTP client function to communicate with Windows bridge.

**Steps**:
1. Add `_call_bridge()` function after the configuration section:
   ```python
   def _call_bridge(endpoint: str, method: str = "GET", json_data: dict = None, timeout: int = 5) -> Optional[dict]:
       """
       Call Windows bridge HTTP endpoint.
       Returns response JSON dict on success, None on failure.
       """
       if not BRIDGE_URL:
           return None
       
       url = f"{BRIDGE_URL}{endpoint}"
       headers = {"X-API-Key": BRIDGE_API_KEY} if BRIDGE_API_KEY else {}
       
       try:
           if method == "GET":
               response = requests.get(url, headers=headers, timeout=timeout)
           elif method == "POST":
               response = requests.post(url, headers=headers, json=json_data, timeout=timeout)
           elif method == "PUT":
               response = requests.put(url, headers=headers, json=json_data, timeout=timeout)
           else:
               logger.error(f"Unsupported HTTP method: {method}")
               return None
           
           response.raise_for_status()
           return response.json()
       
       except requests.exceptions.Timeout:
           logger.error(f"Bridge request timeout: {url}")
           return None
       except requests.exceptions.ConnectionError:
           logger.error(f"Bridge connection error: {url}")
           return None
       except requests.exceptions.HTTPError as e:
           logger.error(f"Bridge HTTP error: {e.response.status_code} - {url}")
           return None
       except Exception as e:
           logger.error(f"Bridge request failed: {e}")
           return None
   ```

**Acceptance Criteria**:
- Function accepts endpoint, method, json_data, and timeout parameters
- Function includes `X-API-Key` header when `BRIDGE_API_KEY` is configured
- Function handles GET, POST, and PUT methods
- Function returns parsed JSON response on success, `None` on failure
- Function logs appropriate error messages for timeout, connection error, HTTP error, and other exceptions
- Function has 5-second default timeout to avoid blocking

---

### 1.3 Create Bridge Health Check Helper

**Objective**: Implement helper function to check bridge MT5 connection status.

**Steps**:
1. Add `_check_bridge_health()` function after `_call_bridge()`:
   ```python
   def _check_bridge_health() -> bool:
       """
       Check if Windows bridge is connected to MT5.
       Returns True if bridge is reachable and MT5 is connected.
       """
       response = _call_bridge("/health")
       if response is None:
           return False
       return response.get("mt5_connected", False)
   ```

**Acceptance Criteria**:
- Function calls `_call_bridge("/health")`
- Function returns `False` if bridge is unreachable (response is `None`)
- Function extracts `mt5_connected` field from response and returns its boolean value
- Function defaults to `False` if `mt5_connected` field is missing

---

## Phase 2: Update Connection Functions

### 2.1 Update ensure_connected() Function

**Objective**: Add bridge delegation logic to connection status check.

**Steps**:
1. Locate the `ensure_connected()` function
2. Add bridge delegation at the beginning of the function (before the existing `if not MT5_AVAILABLE: return False` check):
   ```python
   def ensure_connected() -> bool:
       """Return an active MT5 connection, attempting a reconnect if needed."""
       # Bridge delegation mode
       if USE_BRIDGE:
           return _check_bridge_health()
       
       # Direct MT5 mode (existing code)
       if not MT5_AVAILABLE:
           return False
       if is_connected():
           return True
   
       logger.warning("MT5 connection inactive. Attempting reconnect...")
       return connect()
   ```

**Acceptance Criteria**:
- When `USE_BRIDGE = True`, function calls `_check_bridge_health()` and returns its result
- When `USE_BRIDGE = False`, function uses existing direct MT5 logic unchanged
- Function returns `True` when bridge reports MT5 is connected
- Function returns `False` when bridge is unreachable or MT5 is disconnected

---

## Phase 3: Update Data Retrieval Functions

### 3.1 Update get_account_info() Function

**Objective**: Add bridge delegation to account info retrieval.

**Steps**:
1. Locate the `get_account_info()` function
2. Add bridge delegation at the beginning:
   ```python
   def get_account_info() -> dict:
       # Bridge delegation mode
       if USE_BRIDGE:
           response = _call_bridge("/account")
           return response if response is not None else {}
       
       # Direct MT5 mode (existing code)
       if not MT5_AVAILABLE or not ensure_connected():
           return {}
       info = mt5.account_info()
       if not info:
           return {}
       return {
           "balance": info.balance,
           "equity": info.equity,
           "margin_free": info.margin_free,
           "currency": info.currency,
           "leverage": info.leverage,
           "login": info.login,
           "server": info.server,
       }
   ```

**Acceptance Criteria**:
- When `USE_BRIDGE = True`, function calls `_call_bridge("/account")`
- Function returns bridge response dict on success
- Function returns empty dict `{}` when bridge is unreachable
- When `USE_BRIDGE = False`, function uses existing direct MT5 logic unchanged

---

### 3.2 Update get_open_positions() Function

**Objective**: Add bridge delegation to open positions retrieval.

**Steps**:
1. Locate the `get_open_positions()` function
2. Add bridge delegation at the beginning:
   ```python
   def get_open_positions() -> list[dict]:
       # Bridge delegation mode
       if USE_BRIDGE:
           response = _call_bridge("/positions")
           return response if response is not None else []
       
       # Direct MT5 mode (existing code)
       if not MT5_AVAILABLE or not ensure_connected():
           return []
       positions = mt5.positions_get()
       if not positions:
           return []
       result = []
       for p in positions:
           result.append({
               "id": p.ticket,
               "position_id": p.ticket,
               "symbol": p.symbol,
               "side": "buy" if p.type == mt5.ORDER_TYPE_BUY else "sell",
               "volume": p.volume,
               "entry": p.price_open,
               "sl": p.sl,
               "tp": p.tp,
               "pnl": p.profit,
               "opened": str(p.time),
               "magic": p.magic,
               "comment": p.comment,
           })
       return result
   ```

**Acceptance Criteria**:
- When `USE_BRIDGE = True`, function calls `_call_bridge("/positions")`
- Function returns bridge response list on success
- Function returns empty list `[]` when bridge is unreachable
- When `USE_BRIDGE = False`, function uses existing direct MT5 logic unchanged

---

### 3.3 Update get_trade_history() Function

**Objective**: Add bridge delegation to trade history retrieval.

**Steps**:
1. Locate the `get_trade_history()` function
2. Add bridge delegation at the beginning:
   ```python
   def get_trade_history(limit: int = 50) -> list[dict]:
       # Bridge delegation mode
       if USE_BRIDGE:
           response = _call_bridge(f"/history?limit={limit}")
           return response if response is not None else []
       
       # Direct MT5 mode (existing code continues unchanged)
       if not MT5_AVAILABLE or not ensure_connected():
           return []
       # ... rest of existing code ...
   ```

**Acceptance Criteria**:
- When `USE_BRIDGE = True`, function calls `_call_bridge(f"/history?limit={limit}")`
- Function passes `limit` parameter as query string
- Function returns bridge response list on success
- Function returns empty list `[]` when bridge is unreachable
- When `USE_BRIDGE = False`, function uses existing direct MT5 logic unchanged

---

## Phase 4: Update Trade Execution Functions

### 4.1 Update open_trade() Function

**Objective**: Add bridge delegation to trade opening.

**Steps**:
1. Locate the `open_trade()` function
2. Add bridge delegation at the beginning (after parameter validation if any):
   ```python
   def open_trade(
       symbol: str,
       side: str,
       sl: float,
       tp: float,
       entry: Optional[float] = None,
       order_type: str = "market",
       risk_percent: Optional[float] = None,
       comment: str = "TG Signal",
   ) -> dict:
       """
       Open a market or pending order.
       Returns dict with success, ticket, message.
       """
       # Bridge delegation mode
       if USE_BRIDGE:
           json_data = {
               "symbol": symbol,
               "side": side,
               "order_type": order_type,
               "sl": sl,
               "tp": tp,
               "entry": entry,
               "risk_percent": risk_percent,
               "comment": comment,
           }
           response = _call_bridge("/trade", method="POST", json_data=json_data)
           if response is None:
               return {"success": False, "message": "Bridge request failed"}
           return response
       
       # Direct MT5 mode (existing code continues unchanged)
       if not MT5_AVAILABLE or not ensure_connected():
           return {"success": False, "message": "MT5 not connected"}
       # ... rest of existing code ...
   ```

**Acceptance Criteria**:
- When `USE_BRIDGE = True`, function calls `_call_bridge("/trade", method="POST", json_data={...})`
- Function includes all trade parameters in JSON payload (symbol, side, order_type, sl, tp, entry, risk_percent, comment)
- Function returns bridge response dict on success
- Function returns error dict with `success: False` when bridge is unreachable
- When `USE_BRIDGE = False`, function uses existing direct MT5 logic unchanged

---

### 4.2 Update modify_position() Function

**Objective**: Add bridge delegation to position modification.

**Steps**:
1. Locate the `modify_position()` function
2. Add bridge delegation at the beginning:
   ```python
   def modify_position(position_id: int, sl: Optional[float] = None, tp: Optional[float] = None) -> dict:
       # Bridge delegation mode
       if USE_BRIDGE:
           json_data = {}
           if sl is not None:
               json_data["sl"] = sl
           if tp is not None:
               json_data["tp"] = tp
           response = _call_bridge(f"/positions/{position_id}", method="PUT", json_data=json_data)
           if response is None:
               return {"success": False, "message": "Bridge request failed"}
           return response
       
       # Direct MT5 mode (existing code continues unchanged)
       if not MT5_AVAILABLE or not ensure_connected():
           return {"success": False, "message": "MT5 not connected"}
       # ... rest of existing code ...
   ```

**Acceptance Criteria**:
- When `USE_BRIDGE = True`, function calls `_call_bridge(f"/positions/{position_id}", method="PUT", json_data={...})`
- Function includes sl and tp parameters in JSON payload (only if not None)
- Function returns bridge response dict on success
- Function returns error dict with `success: False` when bridge is unreachable
- When `USE_BRIDGE = False`, function uses existing direct MT5 logic unchanged

---

## Phase 5: Update Lot Calculation Function

### 5.1 Update calculate_lot_with_risk() Function

**Objective**: Add bridge delegation to fetch account info for lot calculation.

**Steps**:
1. Locate the `calculate_lot_with_risk()` function
2. Add bridge delegation for account info retrieval:
   ```python
   def calculate_lot_with_risk(symbol: str, sl_points: float, risk_percent: Optional[float] = None) -> float:
       """Calculate lot size based on risk % of account balance."""
       # Bridge delegation mode - fetch account info from bridge
       if USE_BRIDGE:
           account_response = _call_bridge("/account")
           if account_response is None:
               logger.warning("Bridge account info unavailable, using minimum lot")
               return 0.01
           
           balance = account_response.get("balance", 0)
           if balance == 0:
               return 0.01
           
           # Note: Symbol info is not available via bridge yet
           # For now, use conservative defaults
           # TODO: Add /symbol_info endpoint to bridge or fetch locally
           effective_risk_percent = config.RISK_PERCENT if risk_percent is None else risk_percent
           risk_amount = balance * (effective_risk_percent / 100.0)
           
           # Conservative lot calculation without symbol info
           # Assume standard forex pair with $10 per pip per lot
           lot = risk_amount / (sl_points * 10)
           lot = max(0.01, min(100.0, lot))  # Clamp to reasonable range
           lot = round(lot, 2)  # Round to 2 decimals
           return lot
       
       # Direct MT5 mode (existing code continues unchanged)
       if not MT5_AVAILABLE or not ensure_connected():
           return 0.01
       # ... rest of existing code ...
   ```

**Acceptance Criteria**:
- When `USE_BRIDGE = True`, function calls `_call_bridge("/account")` to get balance
- Function uses conservative lot calculation when symbol info is unavailable
- Function returns minimum lot (0.01) when bridge is unreachable or balance is 0
- Function clamps lot size to reasonable range (0.01 to 100.0)
- Function rounds lot to 2 decimal places
- When `USE_BRIDGE = False`, function uses existing direct MT5 logic unchanged
- Function logs warning when bridge account info is unavailable

**Note**: This is a temporary solution. A future enhancement should add a `/symbol_info` endpoint to the Windows bridge for accurate lot calculation.

---

## Phase 6: Environment Configuration

### 6.1 Add Bridge Configuration to bot/.env

**Objective**: Add bridge URL and API key to environment configuration.

**Steps**:
1. Open `bot/.env` file
2. Add new section after MT5 configuration:
   ```
   # ============================================================
   # MT5 BRIDGE (Ubuntu VPS → Windows PC)
   # ============================================================
   MT5_BRIDGE_URL=
   MT5_BRIDGE_API_KEY=Paladiya@2023
   ```
3. Add comment explaining configuration:
   ```
   # MT5_BRIDGE_URL: Windows PC IP and port (e.g., http://192.168.1.100:8001)
   # MT5_BRIDGE_API_KEY: Must match API_KEY in Windows bridge .env
   # Leave MT5_BRIDGE_URL empty to disable bridge mode
   ```

**Acceptance Criteria**:
- `MT5_BRIDGE_URL` variable is added (empty by default)
- `MT5_BRIDGE_API_KEY` variable is added (matches existing `API_KEY`)
- Comments explain how to configure the bridge
- Configuration is placed in a clearly labeled section

---

## Phase 7: Testing

### 7.1 Manual Testing - Bridge Mode

**Objective**: Verify bridge delegation works correctly on Ubuntu VPS.

**Test Steps**:
1. On Windows PC, ensure `mt5_bridge_windows.py` is running on port 8001
2. On Ubuntu VPS, configure `bot/.env`:
   - Set `MT5_BRIDGE_URL=http://<WINDOWS_PC_IP>:8001`
   - Set `MT5_BRIDGE_API_KEY=Paladiya@2023`
3. Restart the bot on Ubuntu VPS
4. Check logs for "Bridge mode enabled" message
5. Open dashboard and verify:
   - MT5 status shows "Connected" (green indicator)
   - Account balance, equity, and margin are displayed correctly
   - Open positions are displayed (if any)
   - Trade history is displayed
6. Test trade execution:
   - Send a test signal via Telegram
   - Verify trade is executed on MT5 via bridge
   - Verify trade appears in dashboard

**Acceptance Criteria**:
- Dashboard displays "MT5 Connected" with green indicator
- Account information is displayed correctly (balance, equity, margin)
- Open positions are displayed correctly
- Trade history is displayed correctly
- Trade execution works via bridge
- No errors in bot logs related to bridge communication

---

### 7.2 Manual Testing - Direct MT5 Mode (Preservation)

**Objective**: Verify direct MT5 connection still works on Windows.

**Test Steps**:
1. On Windows PC with MT5 installed, configure `bot/.env`:
   - Leave `MT5_BRIDGE_URL` empty
   - Ensure MT5 credentials are correct
2. Run the bot on Windows
3. Check logs for direct MT5 connection (no "Bridge mode enabled" message)
4. Open dashboard and verify:
   - MT5 status shows "Connected" (green indicator)
   - Account information is displayed correctly
   - Open positions are displayed (if any)
   - Trade history is displayed
5. Test trade execution:
   - Send a test signal via Telegram
   - Verify trade is executed directly on MT5
   - Verify trade appears in dashboard

**Acceptance Criteria**:
- Dashboard displays "MT5 Connected" with green indicator
- Account information is displayed correctly
- Open positions are displayed correctly
- Trade history is displayed correctly
- Trade execution works directly (no bridge)
- No errors in bot logs
- Behavior is identical to pre-fix behavior

---

### 7.3 Manual Testing - No Bridge Mode (Preservation)

**Objective**: Verify "MT5 Offline" behavior when bridge is not configured.

**Test Steps**:
1. On Ubuntu VPS, configure `bot/.env`:
   - Leave `MT5_BRIDGE_URL` empty
2. Restart the bot
3. Check logs for "MT5 not available and no bridge configured" warning
4. Open dashboard and verify:
   - MT5 status shows "Offline" (red indicator)
   - Account information shows USD 0.00
   - No positions or trade history displayed

**Acceptance Criteria**:
- Dashboard displays "MT5 Offline" with red indicator
- Account information shows zeros
- No positions or trade history displayed
- Warning logged about missing MT5 and bridge
- Behavior is identical to pre-fix behavior

---

### 7.4 Manual Testing - Bridge Unreachable

**Objective**: Verify error handling when bridge is configured but unreachable.

**Test Steps**:
1. On Ubuntu VPS, configure `bot/.env`:
   - Set `MT5_BRIDGE_URL=http://192.168.1.100:8001` (ensure Windows PC is offline or bridge is stopped)
2. Restart the bot
3. Check logs for bridge connection errors
4. Open dashboard and verify:
   - MT5 status shows "Offline" (red indicator)
   - Account information shows USD 0.00

**Acceptance Criteria**:
- Dashboard displays "MT5 Offline" with red indicator
- Connection errors are logged (timeout or connection error)
- No crashes or unhandled exceptions
- System gracefully degrades to offline mode

---

## Phase 8: Documentation

### 8.1 Update README or Deployment Guide

**Objective**: Document bridge configuration for deployment.

**Steps**:
1. Add section to README or deployment documentation explaining bridge setup
2. Include:
   - When to use bridge mode (Ubuntu VPS deployment)
   - How to configure `MT5_BRIDGE_URL` and `MT5_BRIDGE_API_KEY`
   - How to run `mt5_bridge_windows.py` on Windows PC
   - Network requirements (Windows PC must be reachable from VPS)
   - Security considerations (API key, firewall rules)

**Acceptance Criteria**:
- Documentation clearly explains bridge mode purpose
- Configuration steps are documented
- Network and security considerations are mentioned

---

## Summary

**Total Tasks**: 17 tasks across 8 phases

**Estimated Effort**:
- Phase 1-2: Bridge infrastructure (3 tasks) - 1-2 hours
- Phase 3: Data retrieval (3 tasks) - 1 hour
- Phase 4: Trade execution (2 tasks) - 1 hour
- Phase 5: Lot calculation (1 task) - 30 minutes
- Phase 6: Configuration (1 task) - 15 minutes
- Phase 7: Testing (4 tasks) - 2-3 hours
- Phase 8: Documentation (1 task) - 30 minutes

**Total Estimated Time**: 6-8 hours

**Risk Areas**:
- Network connectivity between VPS and Windows PC
- Lot calculation without symbol info (temporary limitation)
- Timeout handling for slow bridge responses

**Future Enhancements**:
- Add `/symbol_info` endpoint to bridge for accurate lot calculation
- Add connection pooling for better performance
- Add retry logic for transient network failures
- Add bridge health monitoring and alerting
