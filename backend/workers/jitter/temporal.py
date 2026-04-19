"""Temporal Jitter — send-time randomization for anti-spam."""

import random
from datetime import datetime, time, timedelta, timezone

from backend.core.logger import get_logger

logger = get_logger("temporal_jitter")

# Default business hours window (UTC)
_BIZ_START = time(8, 0)   # 08:00
_BIZ_END = time(18, 0)    # 18:00


class TemporalJitter:
    """Randomize email send times to avoid detection as automated sending."""

    def __init__(
        self,
        min_delay_seconds: int = 30,
        max_delay_seconds: int = 300,
        prefer_business_hours: bool = True,
    ):
        """Initialize temporal jitter.

        Args:
            min_delay_seconds: Minimum delay before sending.
            max_delay_seconds: Maximum delay before sending.
            prefer_business_hours: If True, prefer business hours UTC.
        """
        self.min_delay = min_delay_seconds
        self.max_delay = max_delay_seconds
        self.prefer_business_hours = prefer_business_hours

    def get_send_delay(self) -> int:
        """Calculate a randomized delay in seconds.

        Uses a Gaussian distribution centered between min and max,
        so most sends cluster around the midpoint rather than being
        uniformly distributed (which looks robotic).

        Returns:
            Delay in seconds before the email should be sent.
        """
        mean = (self.min_delay + self.max_delay) / 2
        std_dev = (self.max_delay - self.min_delay) / 4

        delay = int(random.gauss(mean, std_dev))

        # Clamp to bounds
        delay = max(self.min_delay, min(self.max_delay, delay))

        logger.debug("temporal_delay_calculated", delay_seconds=delay)
        return delay

    def get_send_time(self) -> datetime:
        """Calculate the actual datetime to send an email.

        If prefer_business_hours is True and the calculated time
        falls outside business hours, it wraps to the next business
        window.

        Returns:
            UTC datetime when the email should be sent.
        """
        now = datetime.now(timezone.utc)
        delay = timedelta(seconds=self.get_send_delay())
        send_at = now + delay

        if self.prefer_business_hours:
            send_at = self._adjust_to_business_hours(send_at)

        logger.debug(
            "send_time_calculated",
            now=now.isoformat(),
            send_at=send_at.isoformat(),
        )
        return send_at

    def _adjust_to_business_hours(self, dt: datetime) -> datetime:
        """Shift a datetime into business hours if needed.

        Weekend sends get pushed to Monday.
        """
        send_time = dt.time()

        # If before business hours, shift to start + random minutes
        if send_time < _BIZ_START:
            random_minutes = random.randint(0, 45)
            dt = dt.replace(
                hour=_BIZ_START.hour,
                minute=_BIZ_START.minute + random_minutes,
                second=random.randint(0, 59),
            )
        # If after business hours, shift to next day start
        elif send_time > _BIZ_END:
            dt = dt + timedelta(days=1)
            random_minutes = random.randint(0, 45)
            dt = dt.replace(
                hour=_BIZ_START.hour,
                minute=_BIZ_START.minute + random_minutes,
                second=random.randint(0, 59),
            )

        # Skip weekends
        while dt.weekday() >= 5:  # Saturday=5, Sunday=6
            dt = dt + timedelta(days=1)

        return dt

    def batch_delays(self, count: int) -> list[int]:
        """Generate a list of increasing delays for a batch of emails.

        Ensures natural spacing between batch sends.

        Args:
            count: Number of delays to generate.

        Returns:
            Sorted list of delays in seconds.
        """
        delays = sorted(self.get_send_delay() for _ in range(count))

        # Ensure minimum spacing between consecutive sends
        min_spacing = 45
        for i in range(1, len(delays)):
            if delays[i] - delays[i - 1] < min_spacing:
                delays[i] = delays[i - 1] + min_spacing + random.randint(0, 30)

        return delays
