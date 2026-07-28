from unittest import TestCase
from unittest.mock import AsyncMock, patch

from bot import telegram_notifier


class TelegramNotifierAllowlistTests(TestCase):
    def test_signal_forge_and_the5ers_are_allowed(self):
        with patch.object(
            telegram_notifier.config,
            "TG_EXECUTION_ALERT_ACCOUNT_LABELS",
            ["Smart Money", "The5ers Funded"],
        ):
            self.assertTrue(telegram_notifier._is_allowed_execution_account("Smart Money"))
            self.assertTrue(telegram_notifier._is_allowed_execution_account("The5ers Funded"))
            self.assertFalse(telegram_notifier._is_allowed_execution_account("Demo Account"))

    def test_execution_alert_returns_false_for_blocked_account(self):
        with patch.object(
            telegram_notifier.config,
            "TG_EXECUTION_ALERT_ACCOUNT_LABELS",
            ["Smart Money", "The5ers Funded"],
        ), patch.object(
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
            ["Smart Money", "The5ers Funded"],
        ), patch.object(
            telegram_notifier, "_get_alert_destination", return_value="123456"
        ), patch.object(telegram_notifier, "_send_message", new=AsyncMock(return_value="bot_api")) as send_mock:
            sent = telegram_notifier.send_algo_execution_alert(
                symbol="XAUUSD",
                side="buy",
                account_label="The5ers Funded",
                login=123,
                ticket=456,
                lot=0.01,
                strategy_id="signal_forge",
                comment="ALGO:SFG",
            )

            self.assertTrue(sent)
            send_mock.assert_awaited_once()

    def test_execution_alert_sends_for_non_signal_forge_strategy(self):
        """
        Regression: a hardcoded gate used to allow only Signal Forge trades, so
        Smart Money (ALGO:SMR) executed with no Telegram alert at all. Account
        eligibility is the account allowlist's job, not the strategy's.
        """
        with patch.object(
            telegram_notifier.config,
            "TG_EXECUTION_ALERT_ACCOUNT_LABELS",
            ["Smart Money", "The5ers Funded"],
        ), patch.object(
            telegram_notifier, "_get_alert_destination", return_value="123456"
        ), patch.object(telegram_notifier, "_send_message", new=AsyncMock(return_value="bot_api")) as send_mock:
            sent = telegram_notifier.send_algo_execution_alert(
                symbol="XAUUSD",
                side="sell",
                account_label="Smart Money",
                login=109961694,
                ticket=9744738054,
                lot=0.02,
                strategy_id="smart_money",
                comment="ALGO:SMR",
            )

            self.assertTrue(sent)
            send_mock.assert_awaited_once()

    def test_error_alert_sends_for_non_signal_forge_strategy(self):
        """The same gate also silently suppressed Smart Money error alerts."""
        with patch.object(
            telegram_notifier.config, "TG_ALGO_ERROR_ALERTS_ENABLED", True
        ), patch.object(
            telegram_notifier.config,
            "TG_EXECUTION_ALERT_ACCOUNT_LABELS",
            ["Smart Money", "The5ers Funded"],
        ), patch.object(
            telegram_notifier.config, "TG_ALGO_ERROR_DEDUPE_SECONDS", 0
        ), patch.object(
            telegram_notifier, "_get_alert_destination", return_value="123456"
        ), patch.object(telegram_notifier, "_send_message", new=AsyncMock(return_value="bot_api")) as send_mock:
            sent = telegram_notifier.send_algo_error_alert(
                account_label="Smart Money",
                login=109961694,
                strategy_id="smart_money",
                symbol="XAUUSD",
                side="sell",
                order_type="market",
                reason="broker rejected order",
                comment="ALGO:SMR",
            )

            self.assertTrue(sent)
            send_mock.assert_awaited_once()
