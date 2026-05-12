"""
Fix multi-symbol support in order_block.py and breakout.py.
1. Add symbol field to OrderBlock/BreakoutSetup dataclasses
2. Set symbol when creating setups in _scan_and_trade
3. Use ob.symbol / setup.symbol in _execute_ob_trade / _execute_breakout_trade
"""
import re

# ── Fix order_block.py ────────────────────────────────────────────────────────
path = "bot/algo/order_block.py"
content = open(path, encoding="utf-8").read()

# 1. Add symbol field to OrderBlock dataclass
old_ob = """@dataclass
class OrderBlock:
    id: str
    direction: str"""
new_ob = """@dataclass
class OrderBlock:
    id: str
    direction: str
    symbol: str = "XAUUSD"  # symbol this OB was detected on"""

if old_ob in content:
    content = content.replace(old_ob, new_ob)
    print("OB dataclass: symbol field added")
else:
    print("WARNING: OB dataclass pattern not found")

# 2. In _detect_order_blocks, OBs are created without symbol — we set it in _scan_and_trade
# Find where new_obs are added and set ob.symbol = symbol
old_add = """        for ob in new_obs:
            if ob.id not in existing_ids:
                # Apply trend filter
                if not _is_trend_aligned(candles_analysis, ob.direction):
                    logger.debug(f"[ALGO] OB {ob.id} filtered out — against trend")
                    continue
                # Apply volatility filter
                if not _is_volatility_sufficient(candles_analysis):
                    logger.debug(f"[ALGO] OB {ob.id} filtered out — low volatility")
                    continue
                _active_obs.append(ob)"""
new_add = """        for ob in new_obs:
            if ob.id not in existing_ids:
                # Apply trend filter
                if not _is_trend_aligned(candles_analysis, ob.direction):
                    logger.debug(f"[ALGO] OB {ob.id} filtered out — against trend")
                    continue
                # Apply volatility filter
                if not _is_volatility_sufficient(candles_analysis):
                    logger.debug(f"[ALGO] OB {ob.id} filtered out — low volatility")
                    continue
                ob.symbol = symbol  # tag OB with its symbol
                _active_obs.append(ob)"""

if old_add in content:
    content = content.replace(old_add, new_add)
    print("_scan_and_trade: ob.symbol tagging added")
else:
    print("WARNING: ob tagging pattern not found")

# 3. Fix _execute_ob_trade to use ob.symbol instead of algo_config.symbol
# Replace all algo_config.symbol inside _execute_ob_trade with ob_symbol variable
old_exec_log = '        f"[ALGO] Order Block trade | {algo_config.symbol} {side.upper()} | "'
new_exec_log = '        f"[ALGO] Order Block trade | {ob.symbol} {side.upper()} | "'
content = content.replace(old_exec_log, new_exec_log)

# Replace symbol= algo_config.symbol in open_trade calls inside _execute_ob_trade
# We need to replace carefully - only inside _execute_ob_trade
# Find the function and replace algo_config.symbol with ob.symbol in trade calls
old_sym1 = """            symbol=algo_config.symbol,
            side=side,
            sl=sl,
            tp=tp,
            entry=entry_price,
            order_type="market",
            risk_percent=algo_config.risk_percent,
            comment=f"ALGO:OB:{ob.id[:8]}",
        )
        if not result.get("success"):
            logger.error(f"[ALGO] Trade failed: {result.get('message')}")
            return False
        ticket = result.get("ticket")
    else:
        from bot.accounts import _connect_account, _reconnect_primary"""
new_sym1 = """            symbol=ob.symbol,
            side=side,
            sl=sl,
            tp=tp,
            entry=entry_price,
            order_type="market",
            risk_percent=algo_config.risk_percent,
            comment=f"ALGO:OB:{ob.id[:8]}",
        )
        if not result.get("success"):
            logger.error(f"[ALGO] Trade failed: {result.get('message')}")
            return False
        ticket = result.get("ticket")
    else:
        from bot.accounts import _connect_account, _reconnect_primary"""
if old_sym1 in content:
    content = content.replace(old_sym1, new_sym1)
    print("_execute_ob_trade: fallback symbol fixed")
else:
    print("WARNING: fallback symbol pattern not found")

old_sym2 = """                    r = _execute_single(
                        symbol=algo_config.symbol,"""
new_sym2 = """                    r = _execute_single(
                        symbol=ob.symbol,"""
if old_sym2 in content:
    content = content.replace(old_sym2, new_sym2)
    print("_execute_ob_trade: _execute_single symbol fixed")
else:
    print("WARNING: _execute_single symbol pattern not found")

old_sym3 = '                f"Ticket: {r.get(\'ticket\')} | {algo_config.symbol} {side.upper()}"'
new_sym3 = '                f"Ticket: {r.get(\'ticket\')} | {ob.symbol} {side.upper()}"'
content = content.replace(old_sym3, new_sym3)

# Fix record_trade_open symbol
old_rto = """    record_trade_open(
        ticket=ticket,
        symbol=algo_config.symbol,"""
new_rto = """    record_trade_open(
        ticket=ticket,
        symbol=ob.symbol,"""
if old_rto in content:
    content = content.replace(old_rto, new_rto)
    print("record_trade_open: symbol fixed")

# Fix signal_log symbol
old_sl = '''        "symbol": algo_config.symbol,
        "side": side,
        "entry": entry_price,
        "sl": sl,
        "tp": tp,
        "one_r": one_r,
        "status": "executed",
        "source": "ALGO:OrderBlock",'''
new_sl = '''        "symbol": ob.symbol,
        "side": side,
        "entry": entry_price,
        "sl": sl,
        "tp": tp,
        "one_r": one_r,
        "status": "executed",
        "source": "ALGO:OrderBlock",'''
if old_sl in content:
    content = content.replace(old_sl, new_sl)
    print("signal_log: symbol fixed")

# Fix _manage_open_trade_risk to use ob.symbol
old_mgr = "current_price = _get_current_price(algo_config.symbol)"
new_mgr = "current_price = _get_current_price(getattr(ob, 'symbol', algo_config.symbol))"
content = content.replace(old_mgr, new_mgr)

old_mgr2 = "candles = _get_candles(algo_config.symbol, algo_config.execution_timeframe, 20)"
new_mgr2 = "candles = _get_candles(getattr(ob, 'symbol', algo_config.symbol), algo_config.execution_timeframe, 20)"
content = content.replace(old_mgr2, new_mgr2)

open(path, "w", encoding="utf-8").write(content)
print("order_block.py: DONE")

# ── Fix breakout.py ───────────────────────────────────────────────────────────
path2 = "bot/algo/breakout.py"
content2 = open(path2, encoding="utf-8").read()

# Add symbol field to BreakoutSetup
old_bs = """@dataclass
class BreakoutSetup:
    id: str
    direction: str"""
new_bs = """@dataclass
class BreakoutSetup:
    id: str
    direction: str
    symbol: str = "XAUUSD"  # symbol this setup was detected on"""

if old_bs in content2:
    content2 = content2.replace(old_bs, new_bs)
    print("BreakoutSetup: symbol field added")
else:
    print("WARNING: BreakoutSetup pattern not found")

# Tag setup with symbol in _scan_and_trade
old_bs_add = """            _active_breakouts.append(setup)
            logger.info(
                f"[BREAKOUT] New {setup.direction} breakout | "
                f"Level: {setup.breakout_level:.5f} | Range: {setup.range_low:.5f}-{setup.range_high:.5f} | "
                f"Time: {setup.time}"
            )"""
new_bs_add = """            setup.symbol = symbol  # tag setup with its symbol
            _active_breakouts.append(setup)
            logger.info(
                f"[BREAKOUT] New {setup.direction} breakout on {symbol} | "
                f"Level: {setup.breakout_level:.5f} | Range: {setup.range_low:.5f}-{setup.range_high:.5f} | "
                f"Time: {setup.time}"
            )"""
if old_bs_add in content2:
    content2 = content2.replace(old_bs_add, new_bs_add)
    print("_scan_and_trade breakout: setup.symbol tagging added")
else:
    print("WARNING: breakout setup tagging pattern not found")

# Fix _execute_breakout_trade to use setup.symbol
content2 = content2.replace(
    'f"[BREAKOUT] {algo_config.symbol} {side.upper()} | "',
    'f"[BREAKOUT] {setup.symbol} {side.upper()} | "'
)

# Fix symbol in open_trade fallback
old_bt1 = """        result = mt5_bridge.open_trade(
            symbol=algo_config.symbol,
            side=side,
            sl=sl,
            tp=tp,
            entry=entry_price,
            order_type="market",
            risk_percent=algo_config.risk_percent,
            comment=f"ALGO:BRK:{setup.id[:8]}",
        )"""
new_bt1 = """        result = mt5_bridge.open_trade(
            symbol=setup.symbol,
            side=side,
            sl=sl,
            tp=tp,
            entry=entry_price,
            order_type="market",
            risk_percent=algo_config.risk_percent,
            comment=f"ALGO:BRK:{setup.id[:8]}",
        )"""
if old_bt1 in content2:
    content2 = content2.replace(old_bt1, new_bt1)
    print("breakout fallback open_trade: symbol fixed")

# Fix execute_on_all_accounts symbol
old_bt2 = """        results = _exec_all(
            symbol=algo_config.symbol,"""
new_bt2 = """        results = _exec_all(
            symbol=setup.symbol,"""
if old_bt2 in content2:
    content2 = content2.replace(old_bt2, new_bt2)
    print("breakout _exec_all: symbol fixed")

# Fix log line
content2 = content2.replace(
    'f"Ticket: {r.get(\'ticket\')} | {algo_config.symbol} {side.upper()}"',
    'f"Ticket: {r.get(\'ticket\')} | {setup.symbol} {side.upper()}"'
)

# Fix signal_log symbol
old_sl2 = '''        "symbol": algo_config.symbol,
        "side": side,
        "entry": entry_price,
        "sl": sl,
        "tp": tp,
        "one_r": one_r,
        "status": "executed",
        "source": "ALGO:Breakout",'''
new_sl2 = '''        "symbol": setup.symbol,
        "side": side,
        "entry": entry_price,
        "sl": sl,
        "tp": tp,
        "one_r": one_r,
        "status": "executed",
        "source": "ALGO:Breakout",'''
if old_sl2 in content2:
    content2 = content2.replace(old_sl2, new_sl2)
    print("breakout signal_log: symbol fixed")

# Fix record_trade_open symbol
old_rto2 = """    record_trade_open(
        ticket=ticket,
        symbol=algo_config.symbol,"""
new_rto2 = """    record_trade_open(
        ticket=ticket,
        symbol=setup.symbol,"""
if old_rto2 in content2:
    content2 = content2.replace(old_rto2, new_rto2)
    print("breakout record_trade_open: symbol fixed")

# Fix entry_reason
old_er = """    entry_reason = (
        f"Range Breakout {setup.direction} | "
        f"Level: {setup.breakout_level:.5f} | "
        f"Range: {setup.range_low:.5f}-{setup.range_high:.5f}"
    )"""
new_er = """    entry_reason = (
        f"Range Breakout {setup.direction} on {setup.symbol} | "
        f"Level: {setup.breakout_level:.5f} | "
        f"Range: {setup.range_low:.5f}-{setup.range_high:.5f}"
    )"""
if old_er in content2:
    content2 = content2.replace(old_er, new_er)

# Fix _manage_open_trade_risk
content2 = content2.replace(
    "_get_current_price(algo_config.symbol)",
    "_get_current_price(getattr(setup, 'symbol', algo_config.symbol))"
)

open(path2, "w", encoding="utf-8").write(content2)
print("breakout.py: DONE")
print("\nAll fixes applied. Bot restart required.")
