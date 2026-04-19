"""Tests for workers — jitter engine (lexical, temporal, throttle)."""

import time
from unittest.mock import MagicMock, patch

import pytest

from backend.workers.jitter.lexical import LexicalJitter
from backend.workers.jitter.temporal import TemporalJitter
from backend.workers.jitter.throttle import ThrottleGuard


# ── Lexical Jitter ──


class TestLexicalJitter:
    def test_empty_text_unchanged(self):
        jitter = LexicalJitter(intensity=1.0)
        assert jitter.apply("") == ""

    def test_no_change_at_zero_intensity(self):
        jitter = LexicalJitter(intensity=0.0)
        text = "I hope this email finds you well. Best regards."
        result = jitter.apply(text)
        assert result == text

    def test_synonym_substitution_at_max_intensity(self):
        """With intensity=1.0, known phrases should always be substituted."""
        jitter = LexicalJitter(intensity=1.0)
        text = "I hope this email finds you well"
        # Run multiple times — at least one should differ
        results = {jitter.apply(text) for _ in range(10)}
        assert len(results) > 1 or text.lower() not in {r.lower() for r in results}

    def test_case_preservation(self):
        jitter = LexicalJitter(intensity=1.0)
        result = jitter._case_aware_replace(
            "Best regards, Alice",
            "best regards",
            "kind regards",
        )
        assert result.startswith("Kind") or result.startswith("kind")

    def test_intensity_clamped(self):
        assert LexicalJitter(intensity=-0.5).intensity == 0.0
        assert LexicalJitter(intensity=2.0).intensity == 1.0


# ── Temporal Jitter ──


class TestTemporalJitter:
    def test_delay_within_bounds(self):
        jitter = TemporalJitter(min_delay_seconds=30, max_delay_seconds=300)
        for _ in range(50):
            delay = jitter.get_send_delay()
            assert 30 <= delay <= 300

    def test_gaussian_distribution_center(self):
        """Most delays should cluster around the midpoint."""
        jitter = TemporalJitter(min_delay_seconds=100, max_delay_seconds=200)
        delays = [jitter.get_send_delay() for _ in range(100)]
        avg = sum(delays) / len(delays)
        assert 130 <= avg <= 170  # Should be near 150

    def test_batch_delays_sorted(self):
        jitter = TemporalJitter()
        delays = jitter.batch_delays(10)
        assert delays == sorted(delays)

    def test_batch_delays_minimum_spacing(self):
        jitter = TemporalJitter(min_delay_seconds=30, max_delay_seconds=60)
        delays = jitter.batch_delays(5)
        for i in range(1, len(delays)):
            assert delays[i] - delays[i - 1] >= 45

    def test_business_hours_weekend_skip(self):
        jitter = TemporalJitter(prefer_business_hours=True)
        send_time = jitter.get_send_time()
        assert send_time.weekday() < 5  # Not Saturday or Sunday


# ── Throttle Guard ──


class TestThrottleGuard:
    @pytest.fixture
    def mock_redis(self):
        """Create a ThrottleGuard with a mocked Redis client."""
        with patch("backend.workers.jitter.throttle.redis_lib") as mock_redis_mod:
            mock_client = MagicMock()
            mock_redis_mod.from_url.return_value = mock_client
            # Default: no sends recorded
            mock_client.zcard.return_value = 0
            mock_client.zremrangebyscore.return_value = 0
            mock_client.pipeline.return_value = mock_client
            mock_client.execute.return_value = []
            guard = ThrottleGuard()
            guard._redis = mock_client
            yield guard, mock_client

    def test_can_send_when_under_limit(self, mock_redis):
        guard, mock_client = mock_redis
        mock_client.zcard.return_value = 0
        assert guard.can_send("user-1") is True

    def test_cannot_send_hourly_limit(self, mock_redis):
        guard, mock_client = mock_redis
        mock_client.zcard.return_value = 3  # At hourly limit
        assert guard.can_send("user-1") is False

    def test_cannot_send_daily_limit(self, mock_redis):
        guard, mock_client = mock_redis

        def side_effect(key):
            if "hourly" in key:
                return 0
            return 30  # At daily limit
        mock_client.zcard.side_effect = side_effect
        assert guard.can_send("user-1") is False

    def test_record_send(self, mock_redis):
        guard, mock_client = mock_redis
        guard.record_send("user-1")
        assert mock_client.zadd.call_count >= 2  # hourly + daily

    def test_get_usage(self, mock_redis):
        guard, mock_client = mock_redis
        mock_client.zcard.return_value = 2
        usage = guard.get_usage("user-1")
        assert usage["hourly_sent"] == 2
        assert usage["hourly_remaining"] == 1
        assert usage["daily_limit"] == 30

    def test_reset(self, mock_redis):
        guard, mock_client = mock_redis
        guard.reset("user-1")
        assert mock_client.delete.call_count == 2
