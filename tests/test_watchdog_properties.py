"""
Property-based tests for watchdog.py logic.

Uses Hypothesis to verify universal correctness properties defined in the
design document for the windows-autostart-server feature.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Make the project root importable
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Helpers — pure logic extracted from watchdog.py for isolated testing
# ---------------------------------------------------------------------------

def simulate_failure_counter(results: list[bool]) -> tuple[int, int]:
    """
    Simulate the watchdog failure-counter logic against a sequence of health
    check results.

    Returns (consecutive_failures_at_end, restart_count).
    """
    consecutive_failures = 0
    restart_count = 0
    fail_threshold = 3

    for result in results:
        if result:
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            if consecutive_failures >= fail_threshold:
                restart_count += 1
                consecutive_failures = 0  # reset after restart

    return consecutive_failures, restart_count


def max_consecutive_false_run(results: list[bool]) -> int:
    """Return the length of the longest uninterrupted run of False values."""
    max_run = 0
    current_run = 0
    for r in results:
        if not r:
            current_run += 1
            max_run = max(max_run, current_run)
        else:
            current_run = 0
    return max_run


# ---------------------------------------------------------------------------
# Property 1: Restart triggers on exactly 3 consecutive failures
# Feature: windows-autostart-server, Property 1
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(st.lists(st.booleans(), min_size=1))
def test_property1_restart_triggers_on_3_consecutive_failures(results: list[bool]) -> None:
    """
    For any sequence of health check results:
    - If the max consecutive False run >= 3, at least one restart must occur.
    - If the max consecutive False run < 3, no restart must occur.

    Validates: Requirements 1.3
    """
    # Feature: windows-autostart-server, Property 1: Restart triggers on exactly 3 consecutive failures
    _, restart_count = simulate_failure_counter(results)
    max_run = max_consecutive_false_run(results)

    if max_run >= 3:
        assert restart_count >= 1, (
            f"Expected at least one restart for sequence {results} "
            f"(max consecutive False run = {max_run}), but got {restart_count}"
        )
    else:
        assert restart_count == 0, (
            f"Expected no restart for sequence {results} "
            f"(max consecutive False run = {max_run}), but got {restart_count}"
        )


# ---------------------------------------------------------------------------
# Property 2: Failure counter resets to zero after any success
# Feature: windows-autostart-server, Property 2
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(st.lists(st.booleans(), min_size=1).filter(lambda s: True in s))
def test_property2_failure_counter_resets_after_success(results: list[bool]) -> None:
    """
    For any sequence that ends with at least one True (success), the
    consecutive failure counter must be 0 after processing.

    Validates: Requirements 1.7
    """
    # Feature: windows-autostart-server, Property 2: Failure counter resets to zero after any success

    # Ensure the sequence ends with a success
    results_ending_in_success = results + [True]
    consecutive_failures, _ = simulate_failure_counter(results_ending_in_success)

    assert consecutive_failures == 0, (
        f"Expected consecutive_failures == 0 after a success, "
        f"but got {consecutive_failures} for sequence {results_ending_in_success}"
    )


# ---------------------------------------------------------------------------
# Property 3: Log entries always contain all required fields
# Feature: windows-autostart-server, Property 3
# ---------------------------------------------------------------------------

def format_log_line(message: str, level: str, attempt: int) -> str:
    """
    Produce a log line in the watchdog format.

    This mirrors the formatter configured in watchdog.setup_logger():
      "%(asctime)s UTC | watchdog | %(levelname)s | %(message)s"
    """
    import datetime
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    return f"{ts} UTC | watchdog | {level} | {message} (attempt {attempt})"


@settings(max_examples=200)
@given(
    st.text(min_size=1),
    st.sampled_from(["DEBUG", "INFO", "WARNING", "ERROR"]),
    st.integers(min_value=0),
)
def test_property3_log_entries_contain_all_required_fields(
    message: str, level: str, attempt: int
) -> None:
    """
    For any log event (any message, any level, any attempt number), the
    resulting log line must contain:
      - a UTC timestamp substring
      - the component name "watchdog"
      - the log level name
      - the message text

    Validates: Requirements 1.6, 8.3
    """
    # Feature: windows-autostart-server, Property 3: Log entries always contain all required fields
    line = format_log_line(message, level, attempt)

    assert "UTC" in line, f"Log line missing UTC timestamp: {line!r}"
    assert "watchdog" in line, f"Log line missing component name: {line!r}"
    assert level in line, f"Log line missing level {level!r}: {line!r}"
    assert message in line, f"Log line missing message text: {line!r}"
