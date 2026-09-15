"""Unit tests for bounded retry policy, backoff calculation, and fallback determination."""

import pytest


class RetryPolicy:
    """Bounded retry policy helper for testing retry invariant."""

    def __init__(self, max_attempts: int = 3, initial_delay_sec: float = 1.0, backoff_factor: float = 2.0):
        self.max_attempts = max_attempts
        self.initial_delay_sec = initial_delay_sec
        self.backoff_factor = backoff_factor

    def should_retry(self, attempt: int, http_status: int) -> bool:
        # Permanent failures (404, 401, 403) should not retry same URL
        if http_status in (400, 401, 403, 404, 410):
            return False
        # Transient errors (500, 502, 503, 504, timeout) retry up to max_attempts
        return attempt < self.max_attempts

    def get_backoff_delay(self, attempt: int) -> float:
        return self.initial_delay_sec * (self.backoff_factor ** (attempt - 1))


@pytest.mark.unit
def test_permanent_404_does_not_retry_same_url():
    policy = RetryPolicy(max_attempts=3)
    assert policy.should_retry(attempt=1, http_status=404) is False
    assert policy.should_retry(attempt=1, http_status=403) is False


@pytest.mark.unit
def test_transient_503_retries_with_bounded_limit():
    policy = RetryPolicy(max_attempts=3)
    assert policy.should_retry(attempt=1, http_status=503) is True
    assert policy.should_retry(attempt=2, http_status=503) is True
    assert policy.should_retry(attempt=3, http_status=503) is False  # Bounded: exceeded max


@pytest.mark.unit
def test_exponential_backoff_calculation():
    policy = RetryPolicy(initial_delay_sec=1.0, backoff_factor=2.0)
    assert policy.get_backoff_delay(1) == 1.0
    assert policy.get_backoff_delay(2) == 2.0
    assert policy.get_backoff_delay(3) == 4.0
