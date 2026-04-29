# Requirements Document

## Introduction

This feature adds a `trading/` Django app to the VibeMall project that serves as an admin dashboard for controlling and monitoring a trading bot. The bot runs as a separate service at `http://127.0.0.1:8001` (accessed via SSH tunnel from a Windows PC) and exposes a REST API. The dashboard provides real-time status visibility, trade management, risk configuration, and Telegram channel management — all protected behind Django's staff-member authentication.

## Glossary

- **Trading_App**: The new `trading` Django application added to the VibeMall project.
- **Bot_API**: The external trading bot REST service running at the URL configured by `BOT_API_URL` (default: `http://127.0.0.1:8001`).
- **Dashboard**: The main admin page at `/trading/` that displays bot status, account info, open trades, recent trades, and recent signals.
- **Settings_Page**: The admin page at `/trading/settings/` for configuring bot risk parameters, Telegram channels, and testing signal parsing.
- **Staff_Member**: A Django user with `is_staff=True`, the minimum privilege level required to access any Trading_App view.
- **Bot_API_Key**: The secret key sent in the `X-API-Key` HTTP header for all Bot_API requests, read from the `BOT_API_KEY` environment variable.
- **Open_Trade**: A currently active position managed by the trading bot on MT5.
- **Signal**: A parsed Telegram message that the bot has evaluated as a potential trade entry.
- **Position_ID**: The integer identifier of an Open_Trade used to reference it in Bot_API calls.
- **Risk_Settings**: Bot configuration fields: `risk_percent`, `reward_ratio`, `max_trades`, `max_positions`, `max_daily_loss`, `max_consecutive_losses`.
- **Validation_Settings**: Bot configuration fields: `max_spread`, `duplicate_window`, `min_seconds`, `allow_pending`.
- **Telegram_Channel**: A channel identifier registered with the bot for signal sourcing.
- **Sneat_Theme**: The Sneat Bootstrap 5 admin theme already used by the VibeMall admin panel (`admin_panel/base_admin.html`).

---

## Requirements

### Requirement 1: Django App Registration

**User Story:** As a developer, I want the `trading` app registered in the Django project, so that its views, URLs, and templates are discoverable by the framework.

#### Acceptance Criteria

1. THE `Trading_App` SHALL be listed in `INSTALLED_APPS` in `VibeMall/settings.py`.
2. THE `Trading_App` SHALL define an `AppConfig` with `name = 'trading'` in `trading/apps.py`.
3. THE `Trading_App` SHALL include a `trading/urls.py` module that defines all URL patterns for the app.
4. THE VibeMall URL router SHALL include `trading.urls` under the prefix `trading/` in `VibeMall/urls.py`.

---

### Requirement 2: Access Control

**User Story:** As a site owner, I want all trading dashboard views restricted to staff members, so that regular customers cannot access or control the trading bot.

#### Acceptance Criteria

1. WHEN an unauthenticated user requests any URL under `/trading/`, THE `Trading_App` SHALL redirect the user to the Django login page.
2. WHEN an authenticated non-staff user requests any URL under `/trading/`, THE `Trading_App` SHALL redirect the user to the Django login page.
3. THE `dashboard` view SHALL be decorated with `@staff_member_required`.
4. THE `settings_page` view SHALL be decorated with `@staff_member_required`.
5. THE `bot_control` view SHALL be decorated with `@staff_member_required`.
6. THE `update_settings` view SHALL be decorated with `@staff_member_required`.
7. THE `update_channels` view SHALL be decorated with `@staff_member_required`.
8. THE `modify_position` view SHALL be decorated with `@staff_member_required`.
9. THE `parse_signal` view SHALL be decorated with `@staff_member_required`.

---

### Requirement 3: Bot API Configuration

**User Story:** As a developer, I want the bot API URL and key read from environment variables, so that credentials are not hard-coded in source control.

#### Acceptance Criteria

1. THE `Trading_App` SHALL read the Bot_API base URL from the `BOT_API_URL` environment variable, defaulting to `http://127.0.0.1:8001`.
2. THE `Trading_App` SHALL read the Bot_API_Key from the `BOT_API_KEY` environment variable, defaulting to `Paladiya@2023`.
3. THE `Trading_App` SHALL send the Bot_API_Key in the `X-API-Key` HTTP header on every outbound Bot_API request.

---

### Requirement 4: Bot API Resilience

**User Story:** As an admin user, I want the dashboard to remain usable when the trading bot is offline, so that a bot outage does not crash the admin panel.

#### Acceptance Criteria

1. WHEN a Bot_API request raises a connection error or timeout, THE `Trading_App` SHALL catch the exception and substitute empty/default data for the failed response.
2. WHEN the Bot_API returns an HTTP error status, THE `Trading_App` SHALL treat the response as empty/default data rather than raising an unhandled exception.
3. WHILE the Bot_API is offline, THE `Dashboard` SHALL render successfully with empty tables and zeroed status cards.
4. WHILE the Bot_API is offline, THE `Settings_Page` SHALL render successfully with empty forms.

---

### Requirement 5: Dashboard View

**User Story:** As a staff member, I want a single-page dashboard showing the bot's live status and trade history, so that I can monitor performance at a glance.

#### Acceptance Criteria

1. WHEN a staff member visits `/trading/`, THE `dashboard` view SHALL issue GET requests to the Bot_API endpoints `/status`, `/open-trades`, `/trades`, `/stats`, and `/signals`.
2. THE `Dashboard` SHALL display status cards for: bot running state, MT5 connection, Telegram connection, account balance, equity, free margin, open position count, and signals processed count.
3. THE `Dashboard` SHALL display today's statistics: wins, losses, total trades, today's net PnL, win rate, and total PnL.
4. THE `Dashboard` SHALL display a table of Open_Trades with columns: Symbol, Side, Volume, Entry price, Stop Loss, Take Profit, Risk, Risk:Reward ratio, Opened time, and an Edit SL/TP action button.
5. THE `Dashboard` SHALL display a table of recent closed trades with columns: Symbol, Side, Volume, Entry price, Stop Loss, Take Profit, Risk:Reward ratio, PnL, Status, Channel, and Opened time.
6. THE `Dashboard` SHALL display a table of recent Signals with columns: Symbol, Side, Stop Loss, Take Profit, Status, Channel, Reason, and Time.
7. THE `Dashboard` SHALL provide bot control buttons: Start Bot, Stop Bot, Restart, and Weekend Shutdown.
8. THE `Dashboard` SHALL provide a link to the Settings_Page in the top-right area of the page.
9. THE `Dashboard` SHALL render using the `trading/dashboard.html` template that extends `admin_panel/base_admin.html`.

---

### Requirement 6: Edit SL/TP Modal

**User Story:** As a staff member, I want to modify the Stop Loss and Take Profit of an open trade from the dashboard, so that I can manage risk without leaving the page.

#### Acceptance Criteria

1. WHEN a staff member clicks the Edit SL/TP button for an Open_Trade, THE `Dashboard` SHALL display a modal form pre-populated with the trade's current Stop Loss and Take Profit values.
2. WHEN a staff member submits the modal form, THE `Dashboard` SHALL POST to `/trading/modify-position/<position_id>/` with the updated Stop Loss and Take Profit values.
3. WHEN the `modify_position` view receives a POST request, THE `Trading_App` SHALL send a PUT request to the Bot_API endpoint `/positions/{position_id}` with the submitted data.
4. WHEN the Bot_API returns a success response, THE `modify_position` view SHALL return a JSON response indicating success.
5. IF the Bot_API is unreachable, THEN THE `modify_position` view SHALL return a JSON response indicating failure without raising an unhandled exception.

---

### Requirement 7: Bot Control

**User Story:** As a staff member, I want to start, stop, restart, or trigger a weekend shutdown of the trading bot from the dashboard, so that I can manage bot lifecycle remotely.

#### Acceptance Criteria

1. WHEN a staff member POSTs to `/trading/bot-control/` with `action=start`, THE `bot_control` view SHALL send a POST request to the Bot_API `/control` endpoint with `action=start`.
2. WHEN a staff member POSTs to `/trading/bot-control/` with `action=stop`, THE `bot_control` view SHALL send a POST request to the Bot_API `/control` endpoint with `action=stop`.
3. WHEN a staff member POSTs to `/trading/bot-control/` with `action=restart`, THE `bot_control` view SHALL send a POST request to the Bot_API `/control` endpoint with `action=restart`.
4. WHEN a staff member POSTs to `/trading/bot-control/` with `action=weekend_shutdown`, THE `bot_control` view SHALL send a POST request to the Bot_API `/control` endpoint with `action=weekend_shutdown`.
5. THE `bot_control` view SHALL return a JSON response indicating the outcome of the Bot_API call.
6. IF the Bot_API is unreachable, THEN THE `bot_control` view SHALL return a JSON error response without raising an unhandled exception.

---

### Requirement 8: Settings Page View

**User Story:** As a staff member, I want a dedicated settings page to configure the bot's risk and validation parameters, so that I can tune bot behaviour without editing config files.

#### Acceptance Criteria

1. WHEN a staff member visits `/trading/settings/`, THE `settings_page` view SHALL issue GET requests to the Bot_API endpoints `/settings` and `/status`.
2. THE `Settings_Page` SHALL display a Risk_Settings form with fields: `risk_percent`, `reward_ratio`, `max_trades`, `max_positions`, `max_daily_loss`, and `max_consecutive_losses`.
3. THE `Settings_Page` SHALL display a Validation_Settings form with fields: `max_spread`, `duplicate_window`, `min_seconds`, and `allow_pending`.
4. THE `Settings_Page` SHALL display the current list of Telegram_Channels with the ability to add a new channel and remove existing channels.
5. THE `Settings_Page` SHALL display bot control buttons: Start Bot, Stop Bot, Restart, and Weekend Shutdown.
6. THE `Settings_Page` SHALL display a Signal Format Tester with a textarea for raw signal text, a parse button, and a result display area.
7. THE `Settings_Page` SHALL render using the `trading/settings.html` template that extends `admin_panel/base_admin.html`.

---

### Requirement 9: Update Risk and Validation Settings

**User Story:** As a staff member, I want to save updated risk and validation settings to the bot, so that configuration changes take effect immediately.

#### Acceptance Criteria

1. WHEN a staff member POSTs to `/trading/update-settings/`, THE `update_settings` view SHALL send a PUT request to the Bot_API `/settings` endpoint with the submitted form data.
2. THE `update_settings` view SHALL return a JSON response indicating the outcome of the Bot_API call.
3. IF the Bot_API is unreachable, THEN THE `update_settings` view SHALL return a JSON error response without raising an unhandled exception.

---

### Requirement 10: Telegram Channel Management

**User Story:** As a staff member, I want to add and remove Telegram channels from the bot's watch list, so that I can control which signal sources the bot monitors.

#### Acceptance Criteria

1. WHEN a staff member POSTs to `/trading/update-channels/` with `action=add` and a channel identifier, THE `update_channels` view SHALL send the appropriate request to the Bot_API `/channels` endpoint to add the channel.
2. WHEN a staff member POSTs to `/trading/update-channels/` with `action=remove` and a channel identifier, THE `update_channels` view SHALL send the appropriate request to the Bot_API `/channels` endpoint to remove the channel.
3. THE `update_channels` view SHALL return a JSON response indicating the outcome of the Bot_API call.
4. IF the Bot_API is unreachable, THEN THE `update_channels` view SHALL return a JSON error response without raising an unhandled exception.

---

### Requirement 11: Signal Format Tester

**User Story:** As a staff member, I want to test raw Telegram signal text against the bot's parser, so that I can verify signal formats before adding a new channel.

#### Acceptance Criteria

1. WHEN a staff member POSTs to `/trading/parse-signal/` with raw signal text, THE `parse_signal` view SHALL send a POST request to the Bot_API `/parse-signal` endpoint with the submitted text.
2. THE `parse_signal` view SHALL return the Bot_API's parsed result as a JSON response.
3. IF the Bot_API is unreachable, THEN THE `parse_signal` view SHALL return a JSON error response without raising an unhandled exception.

---

### Requirement 12: Sidebar Navigation

**User Story:** As a staff member, I want Trading Bot links in the admin sidebar, so that I can navigate to the dashboard and settings from any admin page.

#### Acceptance Criteria

1. THE `admin_panel/base_admin.html` template SHALL include a sidebar menu item labelled "Trading Bot" linking to `/trading/` with the `bx-line-chart` icon, placed before the "Go To Website" link.
2. THE `admin_panel/base_admin.html` template SHALL include a sidebar menu item labelled "Bot Settings" linking to `/trading/settings/` with the `bx-cog` icon, placed before the "Go To Website" link.

---

### Requirement 13: Template Structure and Theming

**User Story:** As a staff member, I want the trading dashboard pages to match the existing admin panel visual style, so that the experience is consistent with the rest of the admin interface.

#### Acceptance Criteria

1. THE `trading/dashboard.html` template SHALL extend `admin_panel/base_admin.html`.
2. THE `trading/settings.html` template SHALL extend `admin_panel/base_admin.html`.
3. THE `Trading_App` templates SHALL be placed in `Hub/templates/trading/` to match the existing template directory convention.
4. THE `Dashboard` and `Settings_Page` SHALL use the Sneat_Theme dark-compatible styling consistent with the existing admin panel.

---

### Requirement 14: JavaScript Interactions

**User Story:** As a staff member, I want dashboard actions (bot control, position editing) to work without full page reloads, so that the experience is responsive.

#### Acceptance Criteria

1. THE `Dashboard` SHALL include a `botAction(action)` JavaScript function that POSTs to `/trading/bot-control/` and displays the result without a full page reload.
2. THE `Dashboard` SHALL include a `weekendShutdown()` JavaScript function that calls `botAction('weekend_shutdown')`.
3. THE `Dashboard` SHALL include an `openModify(positionId, sl, tp)` JavaScript function that opens the Edit SL/TP modal pre-populated with the given values.
4. THE `Dashboard` SHALL include a `submitModify()` JavaScript function that POSTs to `/trading/modify-position/<position_id>/` and closes the modal on success.
5. THE `Dashboard` SHALL include a `getCookie(name)` JavaScript function that retrieves a named cookie value (used for CSRF token handling).
