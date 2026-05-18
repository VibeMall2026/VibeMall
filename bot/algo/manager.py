"""
Algo strategy manager.

Provides a stable API surface for the rest of the app while allowing the
underlying live algo module to be switched between different strategies.
"""
from __future__ import annotations

import importlib
from typing import Optional

from loguru import logger

from bot.strategies import get_strategy


_active_strategy_id = "order_block"


def get_active_strategy_id() -> str:
    return _active_strategy_id


def _get_strategy_module(strategy_id: Optional[str] = None):
    target_id = strategy_id or _active_strategy_id
    strategy = get_strategy(target_id)
    if not strategy or not strategy.get("module"):
        raise ValueError(f"Strategy '{target_id}' is not available as a live algo module")
    return importlib.import_module(strategy["module"])


def select_strategy(strategy_id: str) -> dict:
    """Select the live algo strategy module used by start/stop/status calls."""
    global _active_strategy_id

    strategy = get_strategy(strategy_id)
    if not strategy:
        raise ValueError(f"Unknown strategy '{strategy_id}'")
    if strategy.get("status") != "available" or not strategy.get("module"):
        raise ValueError(f"Strategy '{strategy_id}' is not available for live algo trading")

    if strategy_id == _active_strategy_id:
        return {"success": True, "active_strategy": _active_strategy_id, "changed": False}

    current_module = _get_strategy_module(_active_strategy_id)
    try:
        current_status = current_module.get_algo_status()
    except Exception:
        current_status = {"running": False}

    if current_status.get("running"):
        logger.info(f"[ALGO] Switching live strategy: {_active_strategy_id} -> {strategy_id}")
        current_module.stop_algo()

    _active_strategy_id = strategy_id
    logger.info(f"[ALGO] Active strategy set to: {_active_strategy_id}")
    return {"success": True, "active_strategy": _active_strategy_id, "changed": True}


def start_algo(strategy_id: Optional[str] = None) -> bool:
    if strategy_id:
        select_strategy(strategy_id)
    module = _get_strategy_module()
    return module.start_algo()


def stop_algo() -> bool:
    module = _get_strategy_module()
    return module.stop_algo()


def get_algo_status() -> dict:
    module = _get_strategy_module()
    status = module.get_algo_status()
    status["active_strategy"] = _active_strategy_id
    return status


def update_algo_config(**kwargs) -> dict:
    strategy_id = kwargs.pop("strategy_id", None)
    if strategy_id:
        select_strategy(strategy_id)
    module = _get_strategy_module()
    return module.update_algo_config(**kwargs)


def get_risk_status() -> dict:
    module = _get_strategy_module()
    if hasattr(module, "get_risk_status"):
        return module.get_risk_status()
    return {}


def reset_risk_halts(reset_peak_equity: bool = False) -> dict:
    module = _get_strategy_module()
    if hasattr(module, "reset_risk_halts"):
        return module.reset_risk_halts(reset_peak_equity=reset_peak_equity)
    raise ValueError(f"Strategy '{_active_strategy_id}' does not support risk reset")
