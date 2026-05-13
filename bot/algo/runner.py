"""
Multi-Strategy Parallel Runner
================================
Runs multiple algo strategies simultaneously, each in its own thread.
Each strategy only trades on accounts that have it assigned.

Usage (from main.py):
    from bot.algo.runner import start_all_strategies, stop_all_strategies
"""
from __future__ import annotations

import threading
from typing import Optional
from loguru import logger

from bot.accounts import get_all_accounts


# ── Registry of running strategy threads ─────────────────────────────────────

_running_strategies: dict[str, bool] = {}   # strategy_id -> running flag
_strategy_threads: dict[str, list[threading.Thread]] = {}
_lock = threading.Lock()


def _get_strategies_to_run() -> list[str]:
    """
    Collect unique strategy IDs assigned to at least one enabled account.
    Only strategies with an actual algo module are included.
    """
    from bot.strategies import get_strategy
    needed: set[str] = set()
    accounts = get_all_accounts()
    logger.info(f"[RUNNER] Checking {len(accounts)} accounts for strategy assignments")
    for acc in accounts:
        if not acc.enabled:
            logger.debug(f"[RUNNER] Account {acc.label} disabled — skip")
            continue
        for sid in (acc.strategy or []):
            strat = get_strategy(sid)
            if strat and strat.get("status") == "available" and strat.get("module"):
                needed.add(sid)
                logger.info(f"[RUNNER] Account '{acc.label}' → strategy '{sid}'")
            else:
                logger.debug(f"[RUNNER] Strategy '{sid}' not available as algo module")
    logger.info(f"[RUNNER] Strategies to start: {list(needed)}")
    return list(needed)


def start_all_strategies() -> list[str]:
    """
    Start a thread for every strategy that has at least one assigned account.
    Returns list of started strategy IDs.
    """
    import importlib
    started = []
    strategies = _get_strategies_to_run()

    for sid in strategies:
        with _lock:
            if _running_strategies.get(sid):
                logger.info(f"[RUNNER] Strategy '{sid}' already running — skip")
                continue

        try:
            from bot.strategies import get_strategy
            strat = get_strategy(sid)
            module = importlib.import_module(strat["module"])
            ok = module.start_algo()
            if ok:
                with _lock:
                    _running_strategies[sid] = True
                logger.success(f"[RUNNER] Started strategy: {sid}")
                started.append(sid)
            else:
                logger.warning(f"[RUNNER] Strategy '{sid}' start_algo() returned False")
        except Exception as exc:
            logger.error(f"[RUNNER] Failed to start strategy '{sid}': {exc}")

    return started


def stop_all_strategies() -> None:
    """Stop all running strategies."""
    import importlib
    from bot.strategies import get_strategy

    with _lock:
        sids = list(_running_strategies.keys())

    for sid in sids:
        try:
            strat = get_strategy(sid)
            if strat and strat.get("module"):
                module = importlib.import_module(strat["module"])
                module.stop_algo()
                with _lock:
                    _running_strategies.pop(sid, None)
                logger.info(f"[RUNNER] Stopped strategy: {sid}")
        except Exception as exc:
            logger.error(f"[RUNNER] Failed to stop strategy '{sid}': {exc}")


def get_runner_status() -> dict:
    """Return status of all running strategies."""
    import importlib
    from bot.strategies import get_strategy

    statuses = {}
    with _lock:
        sids = [sid for sid, running in _running_strategies.items() if running]

    for sid in sids:
        try:
            strat = get_strategy(sid)
            if strat and strat.get("module"):
                module = importlib.import_module(strat["module"])
                statuses[sid] = module.get_algo_status()
        except Exception as exc:
            statuses[sid] = {"error": str(exc)}

    return {
        "running_strategies": sids,
        "statuses": statuses,
    }
