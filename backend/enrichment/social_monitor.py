"""Social Monitor — RSS feed + Google Alerts monitoring for leads."""

from datetime import datetime, timezone

import feedparser
import httpx
from supabase import create_client

from backend.core.config import settings
from backend.core.logger import get_logger

logger = get_logger("social_monitor")


class SocialMonitor:
    """Monitor RSS feeds and Google Alerts for lead intelligence."""

    def __init__(self):
        self._supabase = None

    @property
    def supabase(self):
        if self._supabase is None:
            self._supabase = create_client(
                settings.supabase_url, settings.supabase_service_key
            )
        return self._supabase

    async def setup_rss(self, user_id: str, feed_url: str, label: str = "") -> dict:
        """Register an RSS feed for monitoring.

        Args:
            user_id: Owner of this monitor.
            feed_url: The RSS/Atom feed URL.
            label: Optional label (e.g., company name).

        Returns:
            The created monitor record.
        """
        import uuid

        record = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "type": "rss",
            "source_url": feed_url,
            "label": label,
            "last_checked": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        self.supabase.table("social_monitors").insert(record).execute()
        logger.info("rss_monitor_created", user_id=user_id, url=feed_url)
        return record

    async def setup_google_alerts(
        self, user_id: str, query: str, label: str = ""
    ) -> dict:
        """Register a Google Alerts RSS feed for a search query.

        Google Alerts can output an RSS feed at a specific URL pattern.

        Args:
            user_id: Owner of this monitor.
            query: The search query to monitor.
            label: Optional label.

        Returns:
            The created monitor record.
        """
        # Google Alerts RSS feed URL pattern
        encoded_query = query.replace(" ", "+")
        feed_url = f"https://www.google.com/alerts/feeds/{encoded_query}"

        return await self.setup_rss(user_id, feed_url, label=label or query)

    async def check_feeds(self, user_id: str) -> list[dict]:
        """Check all registered RSS feeds for new items.

        Args:
            user_id: The user whose feeds to check.

        Returns:
            List of new feed items found.
        """
        monitors = (
            self.supabase.table("social_monitors")
            .select("*")
            .eq("user_id", user_id)
            .eq("type", "rss")
            .execute()
        )

        if not monitors.data:
            return []

        all_new_items = []

        for monitor in monitors.data:
            new_items = await self._fetch_feed(monitor)
            all_new_items.extend(new_items)

            # Update last_checked timestamp
            self.supabase.table("social_monitors").update(
                {"last_checked": datetime.now(timezone.utc).isoformat()}
            ).eq("id", monitor["id"]).execute()

        # Store new items
        if all_new_items:
            self.supabase.table("social_feed_items").insert(all_new_items).execute()

        logger.info(
            "feeds_checked",
            user_id=user_id,
            monitors=len(monitors.data),
            new_items=len(all_new_items),
        )
        return all_new_items

    async def _fetch_feed(self, monitor: dict) -> list[dict]:
        """Fetch and parse a single RSS feed, returning new items."""
        feed_url = monitor.get("source_url", "")
        last_checked = monitor.get("last_checked")

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(feed_url)
                if resp.status_code != 200:
                    logger.warning(
                        "feed_fetch_failed", url=feed_url, status=resp.status_code
                    )
                    return []
                content = resp.text
        except Exception as exc:
            logger.error("feed_fetch_error", url=feed_url, error=str(exc))
            return []

        feed = feedparser.parse(content)
        new_items = []

        for entry in feed.entries:
            # Parse published date
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

            # Skip if older than last check
            if last_checked and published:
                last_dt = datetime.fromisoformat(last_checked)
                if published <= last_dt:
                    continue

            import uuid

            new_items.append(
                {
                    "id": str(uuid.uuid4()),
                    "monitor_id": monitor["id"],
                    "user_id": monitor["user_id"],
                    "title": getattr(entry, "title", ""),
                    "link": getattr(entry, "link", ""),
                    "summary": getattr(entry, "summary", "")[:500],
                    "published_at": published.isoformat() if published else None,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        return new_items

    async def get_feed_items(
        self, user_id: str, limit: int = 20
    ) -> list[dict]:
        """Get recent feed items for a user."""
        result = (
            self.supabase.table("social_feed_items")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data

    async def delete_monitor(self, monitor_id: str) -> None:
        """Delete a monitor and its feed items."""
        self.supabase.table("social_feed_items").delete().eq(
            "monitor_id", monitor_id
        ).execute()
        self.supabase.table("social_monitors").delete().eq(
            "id", monitor_id
        ).execute()
        logger.info("monitor_deleted", monitor_id=monitor_id)
