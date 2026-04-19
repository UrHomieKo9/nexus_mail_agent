"""Celery worker for periodic email ingestion."""

from supabase import create_client

from backend.api.schemas import EmailPlatform
from backend.celery_app import celery_app
from backend.connectors.gmail import GmailConnector
from backend.connectors.outlook import OutlookConnector
from backend.core.config import settings
from backend.core.logger import get_logger
from backend.pipeline_runner import process_emails_with_pipeline_sync

logger = get_logger("fetcher")

_connectors = {
    EmailPlatform.GMAIL: GmailConnector(),
    EmailPlatform.OUTLOOK: OutlookConnector(),
}


def _get_access_token(user_id: str, provider: EmailPlatform) -> str | None:
    """Retrieve a valid access token for the user from Supabase."""
    supabase = create_client(settings.supabase_url, settings.supabase_service_key)

    result = (
        supabase.table("oauth_tokens")
        .select("access_token, expires_at")
        .eq("user_id", user_id)
        .eq("provider", provider.value)
        .execute()
    )

    if not result.data:
        logger.error("no_token_found", user_id=user_id, provider=provider.value)
        return None

    return result.data[0].get("access_token")


def _store_emails(user_id: str, emails: list[dict]) -> None:
    """Store fetched emails in Supabase."""
    if not emails:
        return

    supabase = create_client(settings.supabase_url, settings.supabase_service_key)

    records = []
    for email in emails:
        records.append({
            "user_id": user_id,
            "platform": email.get("platform"),
            "thread_id": email.get("thread_id"),
            "message_id": email.get("message_id"),
            "sender": email.get("sender"),
            "subject": email.get("subject"),
            "body_clean": email.get("body_clean"),
            "timestamp": email.get("timestamp"),
            "labels": email.get("labels", []),
        })

    supabase.table("emails").upsert(records, on_conflict="message_id").execute()
    logger.info("emails_stored", user_id=user_id, count=len(records))


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def fetch_user_emails(self, user_id: str, provider: str, max_results: int = 50) -> dict:
    """Celery task: fetch emails for a specific user and provider.

    Args:
        user_id: The user's unique identifier.
        provider: "gmail" or "outlook".
        max_results: Maximum number of emails to fetch.

    Returns:
        Dict with count of fetched emails and status.
    """
    try:
        platform = EmailPlatform(provider)
    except ValueError:
        logger.error("invalid_provider", provider=provider)
        return {"status": "error", "message": f"Invalid provider: {provider}"}

    connector = _connectors.get(platform)
    if not connector:
        logger.error("no_connector", provider=provider)
        return {"status": "error", "message": f"No connector for: {provider}"}

    import asyncio

    access_token = _get_access_token(user_id, platform)
    if not access_token:
        return {"status": "error", "message": "No access token found"}

    try:
        emails, next_token = asyncio.run(
            connector.fetch_emails(access_token, max_results=max_results)
        )
    except Exception as exc:
        logger.error("fetch_failed", user_id=user_id, provider=provider, error=str(exc))
        raise self.retry(exc=exc)

    # Convert to dict for storage
    email_dicts = [email.model_dump(mode="json") for email in emails]
    _store_emails(user_id, email_dicts)

    if settings.pipeline_after_fetch:
        pipeline_stats = process_emails_with_pipeline_sync(user_id, emails)
    else:
        pipeline_stats = {
            "drafts_created": 0,
            "skipped": len(emails),
            "pipeline_errors": 0,
        }

    logger.info("fetch_complete", user_id=user_id, provider=provider, count=len(emails))
    return {
        "status": "ok",
        "user_id": user_id,
        "provider": provider,
        "fetched": len(emails),
        "has_more": next_token is not None,
        **pipeline_stats,
    }


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def fetch_all_users_emails(self, provider: str = "gmail", max_results: int = 50) -> dict:
    """Celery task: fetch emails for all users with a given provider connected.

    Returns summary of all fetches.
    """
    supabase = create_client(settings.supabase_url, settings.supabase_service_key)

    result = (
        supabase.table("oauth_tokens")
        .select("user_id")
        .eq("provider", provider)
        .execute()
    )

    if not result.data:
        logger.info("no_users_for_provider", provider=provider)
        return {"status": "ok", "fetched": 0, "users": 0}

    user_ids = list({row["user_id"] for row in result.data})
    total_fetched = 0

    for uid in user_ids:
        task_result = fetch_user_emails.delay(uid, provider, max_results)
        logger.info("dispatched_fetch", user_id=uid, task_id=task_result.id)
        total_fetched += 1

    return {"status": "ok", "users": total_fetched, "provider": provider}