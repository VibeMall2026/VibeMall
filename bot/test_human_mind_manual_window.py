from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from bot.algo.human_mind import cfg, is_manual_management_window, should_early_exit, should_partial_close, should_time_exit


class HumanMindManualWindowTests(TestCase):
    def test_manual_window_uses_india_time(self):
        self.assertTrue(is_manual_management_window(datetime(2026, 7, 14, 4, 30, tzinfo=timezone.utc)))
        self.assertFalse(is_manual_management_window(datetime(2026, 7, 14, 16, 30, tzinfo=timezone.utc)))
        self.assertTrue(is_manual_management_window(datetime(2026, 7, 14, 16, 29, tzinfo=timezone.utc)))

    def test_management_helpers_pause_during_manual_window(self):
        candles = [SimpleNamespace(open=100.0, close=99.0), SimpleNamespace(open=99.0, close=98.0)]
        with patch.object(cfg, "partial_close_enabled", True), patch(
            "bot.algo.human_mind.is_manual_management_window", return_value=True
        ):
            self.assertFalse(
                should_partial_close(
                    entry=100.0,
                    current_price=102.0,
                    one_r=1.0,
                    side="buy",
                    partial_done=False,
                )
            )

        with patch("bot.algo.human_mind.is_manual_management_window", return_value=True):
            self.assertFalse(should_early_exit("buy", candles))
            self.assertFalse(
                should_time_exit(
                    opened_at=datetime(2026, 7, 14, 0, 0, tzinfo=timezone.utc),
                    entry=100.0,
                    current_price=99.0,
                    one_r=1.0,
                    side="buy",
                )
            )
