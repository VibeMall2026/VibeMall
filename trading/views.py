import json
import logging
import os
from pathlib import Path

import requests
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


def _read_simple_env(env_path: Path) -> dict[str, str]:
    # Keep .env parsing dependency-free so CI and production share the same path.
    values: dict[str, str] = {}
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    except FileNotFoundError:
        return values
    except Exception as exc:
        logger.warning("Could not read bot env file at %s: %s", env_path, exc)
    return values


BOT_ENV = _read_simple_env(Path(__file__).resolve().parent.parent / "bot" / ".env")
DEFAULT_BOT_API_CANDIDATES = [
    "http://100.124.101.92:8001",   # Windows PC Tailscale IP (primary)
    "http://127.0.0.1:8001",        # localhost fallback
    "http://127.0.0.1:2222",        # SSH tunnel fallback
    "http://127.0.0.1:8000",        # Django port fallback
]
API_KEY = os.environ.get("BOT_API_KEY") or os.environ.get("API_KEY") or BOT_ENV.get("API_KEY", "")
HEADERS = {"X-API-Key": API_KEY} if API_KEY else {}
TIMEOUT = 3  # Reduced from 5s to 3s for faster failover


def _candidate_bot_api_urls():
    urls = []
    configured = os.environ.get("BOT_API_URL", "").strip()
    for url in [configured, *DEFAULT_BOT_API_CANDIDATES]:
        normalized = url.rstrip("/")
        if normalized and normalized not in urls:
            urls.append(normalized)
    return urls


def _check_api_health():
    errors = []
    candidates = _candidate_bot_api_urls()

    for base_url in candidates:
        try:
            health_resp = requests.get(f"{base_url}/health", timeout=TIMEOUT)
            health_resp.raise_for_status()

            status_resp = requests.get(f"{base_url}/status", headers=HEADERS, timeout=TIMEOUT)
            if status_resp.status_code == 403:
                errors.append(f"{base_url}: rejected API key or client IP")
                continue
            status_resp.raise_for_status()
            return True, base_url, None
        except requests.exceptions.ConnectionError:
            errors.append(f"{base_url}: connection refused")
        except requests.exceptions.Timeout:
            errors.append(f"{base_url}: timed out")
        except requests.exceptions.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else "HTTP error"
            errors.append(f"{base_url}: returned {status_code}")
        except Exception as exc:
            errors.append(f"{base_url}: {exc}")

    primary = candidates[0] if candidates else "unknown"
    if len(errors) > 1:
        detail = "; ".join(errors)
        return False, primary, f"Cannot connect to Bot API. Checked: {detail}"
    return False, primary, f"Cannot connect to Bot API at {primary}"


def _request(method, base_url, endpoint, default=None, json_body=None, params=None):
    if default is None:
        default = {}
    url = f"{base_url}{endpoint}"
    try:
        resp = requests.request(
            method,
            url,
            headers=HEADERS,
            json=json_body,
            params=params,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return True, resp.json()
    except requests.exceptions.ConnectionError as exc:
        logger.error("Bot API unreachable at %s - %s", url, exc)
    except requests.exceptions.Timeout:
        logger.error("Bot API timed out at %s", url)
    except Exception as exc:
        logger.error("Bot API error at %s - %s", url, exc)
    return False, default


def _get(base_url, endpoint, default=None, params=None):
    return _request("GET", base_url, endpoint, default=default, params=params)[1]


def _post(base_url, endpoint, json_body=None):
    return _request("POST", base_url, endpoint, json_body=json_body)


def _put(base_url, endpoint, json_body=None):
    return _request("PUT", base_url, endpoint, json_body=json_body)


def _delete(base_url, endpoint, json_body=None):
    return _request("DELETE", base_url, endpoint, json_body=json_body)


def _bot_flags(health: dict, status: dict) -> tuple[bool, bool, bool]:
    """Resolve bot flags with /status priority, then /health fallback."""
    status_bot = status.get("bot", {}) if isinstance(status, dict) else {}
    health = health if isinstance(health, dict) else {}

    bot_running = status_bot.get("running", health.get("running", False))
    mt5_connected = status_bot.get("mt5_connected", health.get("mt5_connected", False))
    telegram_connected = status_bot.get("telegram_connected", health.get("telegram_connected", False))
    return bool(bot_running), bool(mt5_connected), bool(telegram_connected)


@staff_member_required
def dashboard(request):
    api_reachable, bot_api_url, api_error_msg = _check_api_health()

    if api_reachable:
        health = _get(bot_api_url, "/health", {})
        status = _get(bot_api_url, "/status", {})
        open_trades_resp = _get(bot_api_url, "/open-trades", [])
        trades_resp = _get(bot_api_url, "/trades", [])
        stats = _get(bot_api_url, "/stats", {})
        signals_resp = _get(bot_api_url, "/signals", [])
        channel_msgs_resp = _get(bot_api_url, "/channel-messages", [])
        messages_resp = _get(bot_api_url, "/messages", [])
    else:
        health = status = stats = {}
        open_trades_resp = trades_resp = signals_resp = messages_resp = channel_msgs_resp = []

    open_trades = open_trades_resp if isinstance(open_trades_resp, list) else open_trades_resp.get("items", [])
    trades = trades_resp if isinstance(trades_resp, list) else trades_resp.get("items", [])
    signals = signals_resp if isinstance(signals_resp, list) else signals_resp.get("items", [])
    messages = messages_resp if isinstance(messages_resp, list) else []

    account = status.get("account", {})
    performance = stats.get("performance", {})
    daily = stats.get("daily", {})
    bot_running, mt5_connected, telegram_connected = _bot_flags(health, status)

    context = {
        "api_reachable": api_reachable,
        "api_error": api_error_msg,
        "bot_api_url": bot_api_url,
        "bot_running": bot_running,
        "mt5_connected": mt5_connected,
        "telegram_connected": telegram_connected,
        "balance": account.get("balance", 0),
        "equity": account.get("equity", 0),
        "free_margin": account.get("margin_free", account.get("free_margin", 0)),
        "currency": account.get("currency", "USD"),
        "open_positions": len(open_trades),
        "signals_processed": status.get("signals_processed", 0),
        "wins": daily.get("wins", 0),
        "losses": daily.get("losses", 0),
        "total_trades": daily.get("total_trades", daily.get("trades_count", 0)),
        "today_net_pnl": daily.get("net_pnl", daily.get("pnl", 0)),
        "win_rate": performance.get("win_rate", 0),
        "total_pnl": performance.get("total_pnl", performance.get("pnl", 0)),
        "open_trades": open_trades,
        "recent_trades": trades[:50],
        "recent_signals": signals[:20],
        "channel_messages": channel_msgs_resp[:50] if isinstance(channel_msgs_resp, list) else [],
        "channel_messages": messages[:50],
    }
    return render(request, "trading/dashboard.html", context)


@staff_member_required
def settings_page(request):
    api_reachable, bot_api_url, api_error_msg = _check_api_health()
    settings_data = _get(bot_api_url, "/settings", {}) if api_reachable else {}
    health = _get(bot_api_url, "/health", {}) if api_reachable else {}
    status = _get(bot_api_url, "/status", {}) if api_reachable else {}

    channels = settings_data.get("channels", [])
    risk = settings_data.get("risk", {})
    validation = settings_data.get("validation", {})
    bot_running, mt5_connected, telegram_connected = _bot_flags(health, status)

    context = {
        "api_reachable": api_reachable,
        "api_error": api_error_msg,
        "bot_api_url": bot_api_url,
        "bot_running": bot_running,
        "mt5_connected": mt5_connected,
        "telegram_connected": telegram_connected,
        "channels": channels,
        "risk_percent": risk.get("risk_percent", ""),
        "reward_ratio": risk.get("reward_ratio", risk.get("fixed_reward_ratio", "")),
        "max_trades": risk.get("max_trades", risk.get("max_trades_per_day", "")),
        "max_positions": risk.get("max_positions", risk.get("max_open_positions", "")),
        "max_daily_loss": risk.get("max_daily_loss", risk.get("max_daily_loss_percent", "")),
        "max_consecutive_losses": risk.get("max_consecutive_losses", ""),
        "max_spread": validation.get("max_spread", validation.get("max_spread_points", "")),
        "duplicate_window": validation.get("duplicate_window", validation.get("duplicate_window_minutes", "")),
        "min_seconds": validation.get("min_seconds", validation.get("min_seconds_between_trades", "")),
        "allow_pending": validation.get("allow_pending", validation.get("allow_pending_orders", False)),
    }
    return render(request, "trading/settings.html", context)


@staff_member_required
@require_POST
def bot_control(request):
    api_reachable, bot_api_url, api_error_msg = _check_api_health()
    if not api_reachable:
        return JsonResponse({"success": False, "error": api_error_msg}, status=503)

    action = request.POST.get("action", "")
    if action == "start":
        ok, data = _post(bot_api_url, "/start")
    elif action == "stop":
        ok, data = _post(bot_api_url, "/stop")
    elif action == "restart":
        _post(bot_api_url, "/stop")
        ok, data = _post(bot_api_url, "/start")
    elif action == "weekend_shutdown":
        ok, data = _post(bot_api_url, "/stop")
        if ok:
            data["message"] = "Weekend shutdown initiated"
    else:
        return JsonResponse({"success": False, "error": "Invalid action"}, status=400)
    return JsonResponse({"success": ok, **data})


@staff_member_required
@require_POST
def update_settings(request):
    api_reachable, bot_api_url, api_error_msg = _check_api_health()
    if not api_reachable:
        return JsonResponse({"success": False, "error": api_error_msg}, status=503)

    payload = {}
    fields = [
        "risk_percent",
        "reward_ratio",
        "max_trades",
        "max_positions",
        "max_daily_loss",
        "max_consecutive_losses",
        "max_spread",
        "duplicate_window",
        "min_seconds",
    ]
    for field in fields:
        value = request.POST.get(field)
        if value is not None and value != "":
            try:
                payload[field] = float(value) if "." in value else int(value)
            except ValueError:
                payload[field] = value
    payload["allow_pending"] = request.POST.get("allow_pending") == "on"
    ok, data = _put(bot_api_url, "/settings", json_body=payload)
    return JsonResponse({"success": ok, **data})


@staff_member_required
@require_POST
def update_channels(request):
    api_reachable, bot_api_url, api_error_msg = _check_api_health()
    if not api_reachable:
        return JsonResponse({"success": False, "error": api_error_msg}, status=503)

    action = request.POST.get("action", "")
    channel = request.POST.get("channel", "").strip()
    if not channel:
        return JsonResponse({"success": False, "error": "Channel is required"}, status=400)

    if action == "add":
        ok, data = _post(bot_api_url, "/channels", json_body={"channel": channel})
    elif action == "remove":
        ok, data = _delete(bot_api_url, "/channels", json_body={"channel": channel})
    else:
        return JsonResponse({"success": False, "error": "Invalid action"}, status=400)
    return JsonResponse({"success": ok, **data})


@staff_member_required
@require_POST
def modify_position(request, position_id):
    api_reachable, bot_api_url, api_error_msg = _check_api_health()
    if not api_reachable:
        return JsonResponse({"success": False, "error": api_error_msg}, status=503)

    sl = request.POST.get("sl")
    tp = request.POST.get("tp")
    payload = {}
    if sl:
        payload["sl"] = float(sl)
    if tp:
        payload["tp"] = float(tp)
    ok, data = _put(bot_api_url, f"/positions/{position_id}", json_body=payload)
    return JsonResponse({"success": ok, **data})


@staff_member_required
@require_POST
def parse_signal(request):
    api_reachable, bot_api_url, api_error_msg = _check_api_health()
    if not api_reachable:
        return JsonResponse({"success": False, "error": api_error_msg}, status=503)

    text = request.POST.get("text", "")
    ok, data = _post(bot_api_url, "/parse-signal", json_body={"text": text})
    return JsonResponse({"success": ok, **data})


@staff_member_required
def algo_dashboard(request):
    api_reachable, bot_api_url, api_error_msg = _check_api_health()
    return render(
        request,
        "trading/algo_dashboard.html",
        {
            "api_reachable": api_reachable,
            "api_error": api_error_msg,
            "bot_api_url": bot_api_url,
        },
    )


@staff_member_required
def algo_status(request):
    api_reachable, bot_api_url, api_error_msg = _check_api_health()
    if not api_reachable:
        return JsonResponse({"success": False, "error": api_error_msg}, status=503)
    return JsonResponse(_get(bot_api_url, "/algo/status", {}))


@staff_member_required
@require_POST
def algo_control(request, action):
    api_reachable, bot_api_url, api_error_msg = _check_api_health()
    if not api_reachable:
        return JsonResponse({"success": False, "error": api_error_msg}, status=503)
    if action not in ("start", "stop", "enable", "disable"):
        return JsonResponse({"success": False, "error": "Invalid action"}, status=400)
    ok, data = _post(bot_api_url, f"/algo/{action}")
    return JsonResponse({"success": ok, **data})


@staff_member_required
def algo_config(request):
    api_reachable, bot_api_url, api_error_msg = _check_api_health()
    if not api_reachable:
        return JsonResponse({"success": False, "error": api_error_msg}, status=503)
    if request.method == "PUT":
        try:
            payload = json.loads(request.body)
        except Exception:
            return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)
        ok, data = _put(bot_api_url, "/algo/config", json_body=payload)
        return JsonResponse({"success": ok, **data})
    return JsonResponse({"success": False, "error": "Method not allowed"}, status=405)


@staff_member_required
def algo_signals(request):
    api_reachable, bot_api_url, api_error_msg = _check_api_health()
    if not api_reachable:
        return JsonResponse({"success": False, "error": api_error_msg}, status=503)
    data = _get(bot_api_url, "/algo/trades", {})
    return JsonResponse(data, safe=False)


@staff_member_required
@staff_member_required
def bot_api_proxy(request, endpoint):
    api_reachable, bot_api_url, api_error_msg = _check_api_health()
    if not api_reachable:
        return JsonResponse({"error": api_error_msg or "Bot API unavailable"}, status=503)

    # Strip trailing slash to match FastAPI routes
    endpoint = endpoint.rstrip("/")
    url = f"{bot_api_url}/{endpoint}"
    try:
        kwargs = {"headers": HEADERS, "timeout": TIMEOUT}
        if request.method == "GET":
            kwargs["params"] = request.GET
        elif request.body:
            try:
                kwargs["json"] = json.loads(request.body)
            except Exception:
                pass

        if request.method == "GET":
            resp = requests.get(url, **kwargs)
        elif request.method == "POST":
            resp = requests.post(url, **kwargs)
        elif request.method == "PUT":
            resp = requests.put(url, **kwargs)
        elif request.method == "DELETE":
            resp = requests.delete(url, **kwargs)
        else:
            return JsonResponse({"error": "Method not allowed"}, status=405)

        return JsonResponse(resp.json(), safe=False, status=resp.status_code)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=503)
