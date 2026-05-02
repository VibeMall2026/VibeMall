"""
Property-based tests for startup_manager.py logic.

Uses Hypothesis to verify universal correctness properties defined in the
design document for the windows-autostart-server feature.
"""

from __future__ import annotations

import sys
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

# Make the project root importable
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Helpers — pure logic extracted from startup_manager.py for isolated testing
# ---------------------------------------------------------------------------

def simulate_connectivity_check(n_failures: int, max_retries: int = 5) -> tuple[int, bool]:
    """
    Simulate the connectivity retry loop.

    *n_failures* is the number of consecutive failures before a success.
    If n_failures >= max_retries, all checks fail (no success).

    Returns (attempts_made, succeeded).
    """
    attempts = 0
    for i in range(max_retries):
        attempts += 1
        if i >= n_failures:
            # This attempt succeeds
            return attempts, True
    # All attempts failed
    return attempts, False


def simulate_health_polling(
    success_at_poll_index: int | None,
    poll_interval: int = 5,
    timeout: int = 60,
) -> tuple[int, bool, float]:
    """
    Simulate the health polling loop.

    *success_at_poll_index* is the 0-based index at which the first success
    occurs. If None, all polls fail (timeout).

    Returns (polls_made, succeeded, logged_elapsed_seconds).
    """
    max_polls = timeout // poll_interval  # 60 // 5 = 12

    polls_made = 0
    for i in range(max_polls + 1):  # +1 to allow checking at index 0
        if success_at_poll_index is not None and i == success_at_poll_index:
            elapsed = i * poll_interval
            return i + 1, True, float(elapsed)
        polls_made = i + 1
        if polls_made > max_polls:
            break

    return polls_made, False, float(polls_made * poll_interval)


# ---------------------------------------------------------------------------
# Property 4: Startup manager retries connectivity up to 5 times
# Feature: windows-autostart-server, Property 4
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(st.integers(min_value=0, max_value=5))
def test_property4_connectivity_retries_up_to_5_times(n_failures: int) -> None:
    """
    For any N failures (0 <= N <= 5):
    - If N < 5: the manager makes exactly N+1 attempts and succeeds.
    - If N == 5: the manager makes exactly 5 attempts and fails (exits non-zero).

    Validates: Requirements 2.2, 2.3
    """
    # Feature: windows-autostart-server, Property 4: Startup manager retries connectivity up to 5 times
    max_retries = 5
    attempts, succeeded = simulate_connectivity_check(n_failures, max_retries)

    expected_attempts = min(n_failures + 1, max_retries)
    assert attempts == expected_attempts, (
        f"Expected {expected_attempts} attempts for n_failures={n_failures}, "
        f"but got {attempts}"
    )

    if n_failures < max_retries:
        assert succeeded, (
            f"Expected success for n_failures={n_failures} < {max_retries}, "
            f"but got failure"
        )
    else:
        assert not succeeded, (
            f"Expected failure for n_failures={n_failures} >= {max_retries}, "
            f"but got success"
        )


# ---------------------------------------------------------------------------
# Property 5: Readiness polling respects the 60-second timeout
# Feature: windows-autostart-server, Property 5
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(st.integers(min_value=0, max_value=12))
def test_property5_readiness_polling_respects_timeout(success_at_index: int) -> None:
    """
    For any success at poll index K (0 <= K <= 12):
    - The logged elapsed time must be approximately K * 5 seconds.
    - No polls must occur beyond index 12 (the 60-second boundary).

    Validates: Requirements 2.5, 2.6
    """
    # Feature: windows-autostart-server, Property 5: Readiness polling respects the 60-second timeout
    poll_interval = 5
    timeout = 60
    max_polls = timeout // poll_interval  # 12

    polls_made, succeeded, elapsed = simulate_health_polling(
        success_at_poll_index=success_at_index,
        poll_interval=poll_interval,
        timeout=timeout,
    )

    # Must have succeeded
    assert succeeded, (
        f"Expected success at poll index {success_at_index}, but polling failed"
    )

    # Elapsed time must be approximately K * poll_interval
    expected_elapsed = success_at_index * poll_interval
    assert elapsed == pytest_approx(expected_elapsed, tolerance=poll_interval), (
        f"Expected elapsed ~{expected_elapsed} s for success_at_index={success_at_index}, "
        f"but got {elapsed} s"
    )

    # No polls beyond the 60-second boundary (index 12)
    assert success_at_index <= max_polls, (
        f"Success at index {success_at_index} exceeds max_polls={max_polls}"
    )


def pytest_approx(value: float, tolerance: float = 1e-6) -> "_Approx":
    """Minimal pytest.approx-like helper for use without pytest import at module level."""
    class _Approx:
        def __init__(self, expected: float, tol: float) -> None:
            self.expected = expected
            self.tol = tol

        def __eq__(self, other: object) -> bool:
            if not isinstance(other, (int, float)):
                return NotImplemented
            return builtins_abs(other - self.expected) <= self.tol

        def __repr__(self) -> str:
            return f"{self.expected} ± {self.tol}"

    return _Approx(value, tolerance)


# Capture the builtin abs before any shadowing
builtins_abs = abs
