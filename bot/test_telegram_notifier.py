from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from bot import telegram_notifier


class TelegramNotifierAllowlistTests(TestCase):
    def test_signal_forge_and_the5ers_are_allowed(self):
        with patch.object(
            telegram_notifier.config,
            "TG_EXECUTION_ALERT_ACCOUNT_LABELS",
            ["Signal Forge Gold", "The5ers Funded"],
        ):
            self.assertTrue(telegram_notifier._is_allowed_execution_account("Signal Forge Gold"))
            self.assertTrue(telegram_notifier._is_allowed_execution_account("The5ers Funded"))
            self.assertFalse(telegram_notifier._is_allowed_execution_account("Demo Account"))

    def test_execution_alert_returns_false_for_blocked_account(self):
        with patch.object(
            telegram_notifier.config,
            "TG_EXECUTION_ALERT_ACCOUNT_LABELS",
            ["Signal Forge Gold", "The5ers Funded"],
        ), patch.object(telegram_notifier, "_is_signal_forge_notice", return_value=True), patch.object(
            telegram_notifier, "_get_alert_destination", return_value="123456"
        ), patch.object(telegram_notifier, "_send_message", new=AsyncMock(return_value="bot_api")) as send_mock:
            sent = telegram_notifier.send_algo_execution_alert(
                symbol="XAUUSD",
                side="buy",
                account_label="Other Account",
                login=123,
                ticket=456,
                lot=0.01,
                strategy_id="signal_forge",
                comment="ALGO:SFG",
            )

            self.assertFalse(sent)
            send_mock.assert_not_awaited()

    def test_execution_alert_sends_for_allowed_account(self):
        with patch.object(
            telegram_notifier.config,
            "TG_EXECUTION_ALERT_ACCOUNT_LABELS",
            ["Signal Forge Gold", "The5ers Funded"],
        ), patch.object(telegram_notifier, "_is_signal_forge_notice", return_value=True), patch.object(
            telegram_notifier, "_get_alert_destination", return_value="123456"
        ), patch.object(telegram_notifier, "_send_message", new=AsyncMock(return_value="bot_api")) as send_mock:
            sent = telegram_notifier.send_algo_execution_alert(
                symbol="XAUUSD",
                side="buy",
                account_label="Signal Forge Gold",
                login=123,
                ticket=456,
                lot=0.01,
                strategy_id="signal_forge",
                comment="ALGO:SFG",
            )

            self.assertTrue(sent)
            send_mock.assert_awaited_once()
