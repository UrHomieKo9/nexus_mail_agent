"""Throttle Guard — volume hard caps to prevent spam flags."""

from datetime import datetime, timezone

import redis as redis_lib

from backend.core.config import settings
from backend.core.logger import get_logger

logger = get_logger("throttle")


class ThrottleGuard:
    """Enforce per-user email sending limits using Redis sliding windows.

    Hard caps (configurable via settings):
    - 3 emails per hour  (MAX_EMAILS_PER_HOUR)
    - 30 emails per day  (MAX_EMAILS_PER_DAY)
    """

    HOUR_WINDOW = 3600       # 1 hour in seconds
    DAY_WINDOW = 86400       # 24 hours in seconds

    def __init__(self):
        self._redis = redis_lib.from_url(settings.redis_url, decode_responses=True)
        self.max_per_hour = settings.max_emails_per_hour
        self.max_per_day = settings.max_emails_per_day

    def _hourly_key(self, user_id: str) -> str:
        return f"throttle:hourly:{user_id}"

    def _daily_key(self, user_id: str) -> str:
        return f"throttle:daily:{user_id}"

    def can_send(self, user_id: str) -> bool:
        """Check if a user is allowed to send another email.

        Returns:
            True if within both hourly and daily limits.
        """
        now = datetime.now(timezone.utc).timestamp()

        hourly_count = self._count_in_window(
            self._hourly_key(user_id), now, self.HOUR_WINDOW
        )
        if hourly_count >= self.max_per_hour:
            logger.warning(
                "throttle_hourly_limit",
                user_id=user_id,
                count=hourly_count,
                limit=self.max_per_hour,
            )
            return False

        daily_count = self._count_in_window(
            self._daily_key(user_id), now, self.DAY_WINDOW
        )
        if daily_count >= self.max_per_day:
            logger.warning(
                "throttle_daily_limit",
                user_id=user_id,
                count=daily_count,
                limit=self.max_per_day,
            )
            return False

        return True

    def record_send(self, user_id: str) -> None:
        """Record that a user sent an email.

        Adds the current timestamp to both hourly and daily sorted sets.
        """
        now = datetime.now(timezone.utc).timestamp()

        pipe = self._redis.pipeline()

        # Add to hourly window
        hourly_key = self._hourly_key(user_id)
        pipe.zadd(hourly_key, {str(now): now})
        pipe.expire(hourly_key, self.HOUR_WINDOW + 60)

        # Add to daily window
        daily_key = self._daily_key(user_id)
        pipe.zadd(daily_key, {str(now): now})
        pipe.expire(daily_key, self.DAY_WINDOW + 60)

        pipe.execute()

        logger.info("send_recorded", user_id=user_id)

    def get_usage(self, user_id: str) -> dict:
        """Get current usage stats for a user.

        Returns:
            Dict with hourly/daily counts and limits.
        """
        now = datetime.now(timezone.utc).timestamp()

        hourly = self._count_in_window(
            self._hourly_key(user_id), now, self.HOUR_WINDOW
        )
        daily = self._count_in_window(
            self._daily_key(user_id), now, self.DAY_WINDOW
        )

        return {
            "hourly_sent": hourly,
            "hourly_limit": self.max_per_hour,
            "hourly_remaining": max(0, self.max_per_hour - hourly),
            "daily_sent": daily,
            "daily_limit": self.max_per_day,
            "daily_remaining": max(0, self.max_per_day - daily),
        }

    def reset(self, user_id: str) -> None:
        """Reset all throttle counters for a user (admin use)."""
        self._redis.delete(self._hourly_key(user_id))
        self._redis.delete(self._daily_key(user_id))
        logger.info("throttle_reset", user_id=user_id)

    def _count_in_window(self, key: str, now: float, window: int) -> int:
        """Count entries in a Redis sorted set within a sliding window."""
        cutoff = now - window

        # Clean old entries
        self._redis.zremrangebyscore(key, "-inf", cutoff)

        # Count remaining
        return self._redis.zcard(key)
