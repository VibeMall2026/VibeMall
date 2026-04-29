import os
import requests
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

BOT_API = os.environ.get('BOT_API_URL', 'http://127.0.0.1:8001')
HEADERS = {"X-API-Key": os.environ.get('BOT_API_KEY', 'Paladiya@2023')}
TIMEOUT = 5  # seconds


def _get(endpoint, default=None):
    """Safe GET from bot API. Returns default on any error."""
    if default is None:
        default = {}
    try:
        resp = requests.get(f"{BOT_API}{endpoint}", headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return default


def _post(endpoint, data=None, json=None):
    """Safe POST to bot API. Returns (ok, response_dict)."""
    try:
        resp = requests.post(
            f"{BOT_API}{endpoint}",
            headers=HEADERS,
            data=data,
            json=json,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return True, resp.json()
    except Exception as e:
        return False, {"error": str(e)}


def _put(endpoint, json=None):
    """Safe PUT to bot API. Returns (ok, response_dict)."""
    try:
        resp = requests.put(
            f"{BOT_API}{endpoint}",
            headers=HEADERS,
            json=json,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return True, resp.json()
    except Exception as e:
        return False, {"error": str(e)}


@staff_member_required
def dashboard(request):
    status = _get('/status', {})
    open_trades = _get('/open-trades', [])
    trades = _get('/trades', [])
    stats = _get('/stats', {})
    signals = _get('/signals', [])

    # Normalise open_trades to list
    if isinstance(open_trades, dict):
        open_trades = open_trades.get('trades', open_trades.get('data', []))
    if isinstance(trades, dict):
        trades = trades.get('trades', trades.get('data', []))
    if isinstance(signals, dict):
        signals = signals.get('signals', signals.get('data', []))

    # Flatten stats structure for template convenience
    bot_info = stats.get('bot', status.get('bot', {}))
    account = stats.get('account', status.get('account', {}))
    performance = stats.get('performance', {})
    daily = stats.get('daily', {})
    trades_summary = stats.get('trades', {})

    context = {
        'bot_running': bot_info.get('running', False),
        'mt5_connected': bot_info.get('mt5_connected', False),
        'telegram_connected': bot_info.get('telegram_connected', False),
        'balance': account.get('balance', 0),
        'equity': account.get('equity', 0),
        'free_margin': account.get('margin_free', 0),
        'currency': account.get('currency', 'USD'),
        'open_positions': trades_summary.get('open', len(open_trades)),
        'signals_processed': status.get('signals_processed', 0),
        'wins': daily.get('wins', 0),
        'losses': daily.get('losses', 0),
        'total_trades': daily.get('trades_count', 0),
        'today_net_pnl': daily.get('net_pnl', 0),
        'win_rate': performance.get('win_rate', 0),
        'total_pnl': performance.get('total_pnl', 0),
        'open_trades': open_trades,
        'recent_trades': trades[:20] if isinstance(trades, list) else [],
        'recent_signals': signals[:20] if isinstance(signals, list) else [],
    }
    return render(request, 'trading/dashboard.html', context)


@staff_member_required
def settings_page(request):
    settings_data = _get('/settings', {})
    status = _get('/status', {})

    bot_info = status.get('bot', {})
    channels = settings_data.get('channels', [])
    risk = settings_data.get('risk', settings_data)
    validation = settings_data.get('validation', settings_data)

    context = {
        'bot_running': bot_info.get('running', False),
        'mt5_connected': bot_info.get('mt5_connected', False),
        'telegram_connected': bot_info.get('telegram_connected', False),
        'channels': channels,
        'risk_percent': risk.get('risk_percent', ''),
        'reward_ratio': risk.get('reward_ratio', ''),
        'max_trades': risk.get('max_trades', ''),
        'max_positions': risk.get('max_positions', ''),
        'max_daily_loss': risk.get('max_daily_loss', ''),
        'max_consecutive_losses': risk.get('max_consecutive_losses', ''),
        'max_spread': validation.get('max_spread', ''),
        'duplicate_window': validation.get('duplicate_window', ''),
        'min_seconds': validation.get('min_seconds', ''),
        'allow_pending': validation.get('allow_pending', False),
    }
    return render(request, 'trading/settings.html', context)


@staff_member_required
@require_POST
def bot_control(request):
    action = request.POST.get('action', '')
    if action not in ('start', 'stop', 'restart', 'weekend_shutdown'):
        return JsonResponse({'success': False, 'error': 'Invalid action'}, status=400)
    ok, data = _post('/control', json={'action': action})
    return JsonResponse({'success': ok, **data})


@staff_member_required
@require_POST
def update_settings(request):
    payload = {
        'risk_percent': request.POST.get('risk_percent'),
        'reward_ratio': request.POST.get('reward_ratio'),
        'max_trades': request.POST.get('max_trades'),
        'max_positions': request.POST.get('max_positions'),
        'max_daily_loss': request.POST.get('max_daily_loss'),
        'max_consecutive_losses': request.POST.get('max_consecutive_losses'),
        'max_spread': request.POST.get('max_spread'),
        'duplicate_window': request.POST.get('duplicate_window'),
        'min_seconds': request.POST.get('min_seconds'),
        'allow_pending': request.POST.get('allow_pending') == 'on',
    }
    # Remove None values
    payload = {k: v for k, v in payload.items() if v is not None}
    ok, data = _put('/settings', json=payload)
    return JsonResponse({'success': ok, **data})


@staff_member_required
@require_POST
def update_channels(request):
    action = request.POST.get('action', '')
    channel = request.POST.get('channel', '').strip()
    if not channel:
        return JsonResponse({'success': False, 'error': 'Channel is required'}, status=400)
    if action == 'add':
        ok, data = _post('/channels', json={'channel': channel})
    elif action == 'remove':
        try:
            resp = requests.delete(
                f"{BOT_API}/channels",
                headers=HEADERS,
                json={'channel': channel},
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            ok, data = True, resp.json()
        except Exception as e:
            ok, data = False, {"error": str(e)}
    else:
        return JsonResponse({'success': False, 'error': 'Invalid action'}, status=400)
    return JsonResponse({'success': ok, **data})


@staff_member_required
@require_POST
def modify_position(request, position_id):
    sl = request.POST.get('sl')
    tp = request.POST.get('tp')
    payload = {}
    if sl:
        payload['sl'] = float(sl)
    if tp:
        payload['tp'] = float(tp)
    ok, data = _put(f'/positions/{position_id}', json=payload)
    return JsonResponse({'success': ok, **data})


@staff_member_required
@require_POST
def parse_signal(request):
    text = request.POST.get('text', '')
    ok, data = _post('/parse-signal', json={'text': text})
    return JsonResponse({'success': ok, **data})
