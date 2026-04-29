import os
import requests
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

BOT_API = os.environ.get('BOT_API_URL', 'http://127.0.0.1:8001')
API_KEY = os.environ.get('BOT_API_KEY', 'Paladiya@2023')
HEADERS = {"X-API-Key": API_KEY}
TIMEOUT = 5


def _get(endpoint, default=None):
    if default is None:
        default = {}
    try:
        resp = requests.get(f"{BOT_API}{endpoint}", headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return default


def _post(endpoint, json=None):
    try:
        resp = requests.post(f"{BOT_API}{endpoint}", headers=HEADERS, json=json, timeout=TIMEOUT)
        resp.raise_for_status()
        return True, resp.json()
    except Exception as e:
        return False, {"error": str(e)}


def _put(endpoint, json=None):
    try:
        resp = requests.put(f"{BOT_API}{endpoint}", headers=HEADERS, json=json, timeout=TIMEOUT)
        resp.raise_for_status()
        return True, resp.json()
    except Exception as e:
        return False, {"error": str(e)}


@staff_member_required
def dashboard(request):
    health = _get('/health', {})
    status = _get('/status', {})
    open_trades_resp = _get('/open-trades', {'items': []})
    trades_resp = _get('/trades', {'items': []})
    stats = _get('/stats', {})
    signals_resp = _get('/signals', {'items': []})

    # TelegramCopier returns ListResponse with 'items' key
    open_trades = open_trades_resp.get('items', []) if isinstance(open_trades_resp, dict) else open_trades_resp
    trades = trades_resp.get('items', []) if isinstance(trades_resp, dict) else trades_resp
    signals = signals_resp.get('items', []) if isinstance(signals_resp, dict) else signals_resp

    # Account info from /status
    account = status.get('account', {})

    # Stats structure from TelegramCopier StatsResponse
    performance = stats.get('performance', {})
    daily = stats.get('daily', {})

    context = {
        'bot_running': health.get('running', False),
        'mt5_connected': health.get('mt5_connected', False),
        'telegram_connected': health.get('telegram_connected', False),
        'balance': account.get('balance', 0),
        'equity': account.get('equity', 0),
        'free_margin': account.get('margin_free', account.get('free_margin', 0)),
        'currency': account.get('currency', 'USD'),
        'open_positions': len(open_trades),
        'signals_processed': status.get('signals_processed', 0),
        'wins': daily.get('wins', 0),
        'losses': daily.get('losses', 0),
        'total_trades': daily.get('total_trades', daily.get('trades_count', 0)),
        'today_net_pnl': daily.get('net_pnl', daily.get('pnl', 0)),
        'win_rate': performance.get('win_rate', 0),
        'total_pnl': performance.get('total_pnl', performance.get('pnl', 0)),
        'open_trades': open_trades,
        'recent_trades': trades[:20],
        'recent_signals': signals[:20],
    }
    return render(request, 'trading/dashboard.html', context)


@staff_member_required
def settings_page(request):
    settings_data = _get('/settings', {})
    health = _get('/health', {})

    channels = settings_data.get('channels', [])
    risk = settings_data.get('risk', {})
    validation = settings_data.get('validation', {})

    context = {
        'bot_running': health.get('running', False),
        'mt5_connected': health.get('mt5_connected', False),
        'telegram_connected': health.get('telegram_connected', False),
        'channels': channels,
        'risk_percent': risk.get('risk_percent', ''),
        'reward_ratio': risk.get('reward_ratio', risk.get('fixed_reward_ratio', '')),
        'max_trades': risk.get('max_trades', risk.get('max_trades_per_day', '')),
        'max_positions': risk.get('max_positions', risk.get('max_open_positions', '')),
        'max_daily_loss': risk.get('max_daily_loss', risk.get('max_daily_loss_percent', '')),
        'max_consecutive_losses': risk.get('max_consecutive_losses', ''),
        'max_spread': validation.get('max_spread', validation.get('max_spread_points', '')),
        'duplicate_window': validation.get('duplicate_window', validation.get('duplicate_window_minutes', '')),
        'min_seconds': validation.get('min_seconds', validation.get('min_seconds_between_trades', '')),
        'allow_pending': validation.get('allow_pending', validation.get('allow_pending_orders', False)),
    }
    return render(request, 'trading/settings.html', context)


@staff_member_required
@require_POST
def bot_control(request):
    action = request.POST.get('action', '')
    # TelegramCopier has /start and /stop endpoints (not /control)
    if action == 'start':
        ok, data = _post('/start')
    elif action == 'stop':
        ok, data = _post('/stop')
    elif action == 'restart':
        _post('/stop')
        import time; time.sleep(1)
        ok, data = _post('/start')
    elif action == 'weekend_shutdown':
        ok, data = _post('/stop')
        if ok:
            data['message'] = 'Weekend shutdown initiated'
    else:
        return JsonResponse({'success': False, 'error': 'Invalid action'}, status=400)
    return JsonResponse({'success': ok, **data})


@staff_member_required
@require_POST
def update_settings(request):
    payload = {}
    fields = ['risk_percent', 'reward_ratio', 'max_trades', 'max_positions',
              'max_daily_loss', 'max_consecutive_losses', 'max_spread',
              'duplicate_window', 'min_seconds']
    for f in fields:
        v = request.POST.get(f)
        if v is not None and v != '':
            try:
                payload[f] = float(v) if '.' in v else int(v)
            except ValueError:
                payload[f] = v
    payload['allow_pending'] = request.POST.get('allow_pending') == 'on'
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
        ok, data = _post('/channels/add', json={'channel': channel})
        if not ok:
            # Try alternate endpoint
            ok, data = _put('/settings', json={'channels_add': [channel]})
    elif action == 'remove':
        ok, data = _post('/channels/remove', json={'channel': channel})
        if not ok:
            ok, data = _put('/settings', json={'channels_remove': [channel]})
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
        payload['stop_loss'] = float(sl)   # TelegramCopier uses stop_loss
    if tp:
        payload['take_profit'] = float(tp)  # TelegramCopier uses take_profit
    ok, data = _put(f'/positions/{position_id}', json=payload)
    return JsonResponse({'success': ok, **data})


@staff_member_required
@require_POST
def parse_signal(request):
    text = request.POST.get('text', '')
    # TelegramCopier uses 'message' field (not 'text')
    ok, data = _post('/parse-signal', json={'message': text})
    return JsonResponse({'success': ok, **data})
