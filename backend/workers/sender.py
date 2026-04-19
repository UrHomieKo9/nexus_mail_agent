"""Send Engine — Celery tasks for email dispatch with jitter integration."""

import asyncio
from datetime import datetime, timezone

from supabase import create_client

from backend.api.schemas import EmailPlatform
from backend.celery_app import celery_app
from backend.connectors.gmail import GmailConnector
from backend.connectors.outlook import OutlookConnector
from backend.core.config import settings
from backend.core.logger import get_logger
from backend.workers.jitter.lexical import LexicalJitter
from backend.workers.jitter.temporal import TemporalJitter
from backend.workers.jitter.throttle import ThrottleGuard

logger = get_logger("sender")

_connectors = {
    EmailPlatform.GMAIL: GmailConnector(),
    EmailPlatform.OUTLOOK: OutlookConnector(),
}


def _get_access_token(user_id: str, provider: EmailPlatform) -> str | None:
    """Retrieve a valid access token for the user."""
    supabase = create_client(settings.supabase_url, settings.supabase_service_key)

    result = (
        supabase.table("oauth_tokens")
        .select("access_token")
        .eq("user_id", user_id)
        .eq("provider", provider.value)
        .execute()
    )

    if not result.data:
        return None
    return result.data[0].get("access_token")


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def send_email_task(
    self,
    draft_id: str,
    apply_jitter: bool = True,
) -> dict:
    """Celery task: send a single approved draft email.

    Args:
        draft_id: The draft to send.
        apply_jitter: Whether to apply lexical jitter.

    Returns:
        Dict with send status and message ID.
    """
    supabase = create_client(settings.supabase_url, settings.supabase_service_key)

    # Fetch draft
    draft_result = (
        supabase.table("drafts")
        .select("*")
        .eq("draft_id", draft_id)
        .execute()
    )

    if not draft_result.data:
        return {"status": "error", "message": f"Draft {draft_id} not found"}

    draft = draft_result.data[0]

    # Check throttle
    user_id = draft.get("user_id", "")
    throttle = ThrottleGuard()

    if not throttle.can_send(user_id):
        usage = throttle.get_usage(user_id)
        logger.warning("send_throttled", user_id=user_id, usage=usage)
        return {
            "status": "throttled",
            "message": "Sending limit reached",
            "usage": usage,
        }

    # Apply lexical jitter if enabled
    body = draft.get("body", "")
    if apply_jitter:
        jitter = LexicalJitter(intensity=0.5)
        body = jitter.apply(body)

    # Determine connector
    platform = EmailPlatform(draft.get("platform", "gmail"))
    connector = _connectors.get(platform)

    if not connector:
        return {"status": "error", "message": f"No connector for {platform.value}"}

    access_token = _get_access_token(user_id, platform)
    if not access_token:
        return {"status": "error", "message": "No access token"}

    # Send via connector
    try:
        message_id = asyncio.run(
            connector.send_email(
                access_token=access_token,
                to=draft.get("to", ""),
                subject=draft.get("subject", ""),
                body=body,
                thread_id=draft.get("thread_id"),
                reply_to_message_id=draft.get("original_message_id"),
            )
        )
    except Exception as exc:
        logger.error("send_failed", draft_id=draft_id, error=str(exc))
        raise self.retry(exc=exc)

    # Record send for throttling
    throttle.record_send(user_id)

    # Update draft status
    supabase.table("drafts").update({
        "status": "sent",
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "sent_message_id": message_id,
    }).eq("draft_id", draft_id).execute()

    logger.info("email_sent", draft_id=draft_id, message_id=message_id)
    return {"status": "sent", "draft_id": draft_id, "message_id": message_id}


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
def process_campaign(
    self,
    campaign_id: str,
    apply_jitter: bool = True,
) -> dict:
    """Celery task: process and send all pending emails in a campaign.

    Uses temporal jitter to space out sends naturally.

    Args:
        campaign_id: The campaign to process.
        apply_jitter: Whether to apply lexical + temporal jitter.

    Returns:
        Dict with campaign send summary.
    """
    supabase = create_client(settings.supabase_url, settings.supabase_service_key)

    # Fetch campaign
    campaign_result = (
        supabase.table("campaigns")
        .select("*")
        .eq("campaign_id", campaign_id)
        .execute()
    )

    if not campaign_result.data:
        return {"status": "error", "message": f"Campaign {campaign_id} not found"}

    campaign = campaign_result.data[0]

    if campaign.get("status") == "paused":
        return {"status": "paused", "campaign_id": campaign_id}

    recipients = campaign.get("recipients", [])
    pending = [r for r in recipients if r.get("status") == "pending"]

    if not pending:
        # Mark campaign as completed
        supabase.table("campaigns").update({
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("campaign_id", campaign_id).execute()
        return {"status": "completed", "campaign_id": campaign_id, "sent": 0}

    # Generate temporal delays for the batch
    temporal = TemporalJitter()
    delays = temporal.batch_delays(len(pending)) if apply_jitter else [0] * len(pending)

    sent_count = 0
    lexical = LexicalJitter(intensity=0.4)
    throttle = ThrottleGuard()

    for i, recipient in enumerate(pending):
        # Re-check campaign status (user may pause mid-send)
        if i > 0 and i % 5 == 0:
            refresh = (
                supabase.table("campaigns")
                .select("status")
                .eq("campaign_id", campaign_id)
                .execute()
            )
            if refresh.data and refresh.data[0].get("status") == "paused":
                logger.info("campaign_paused_mid_send", campaign_id=campaign_id)
                break

        # Check throttle
        user_id = campaign.get("user_id", "")
        if not throttle.can_send(user_id):
            logger.warning("campaign_throttled", campaign_id=campaign_id)
            break

        # Apply delay
        if apply_jitter and delays[i] > 0:
            import time
            time.sleep(min(delays[i], 60))  # Cap individual delay at 60s in task

        # Prepare email body with jitter
        body = campaign.get("body_template", "")
        subject = campaign.get("subject_template", "")

        if apply_jitter:
            body = lexical.apply(body)

        # Personalize
        body = body.replace("{{name}}", recipient.get("name", ""))
        body = body.replace("{{email}}", recipient.get("email", ""))
        body = body.replace("{{company}}", recipient.get("company", ""))
        subject = subject.replace("{{name}}", recipient.get("name", ""))
        subject = subject.replace("{{company}}", recipient.get("company", ""))

        # Dispatch individual send
        send_email_task.delay(
            draft_id=f"campaign-{campaign_id}-{i}",
            apply_jitter=False,  # Already applied
        )

        # Record per-recipient send
        throttle.record_send(user_id)
        sent_count += 1

    # Update campaign counters
    supabase.table("campaigns").update({
        "total_sent": campaign.get("total_sent", 0) + sent_count,
    }).eq("campaign_id", campaign_id).execute()

    logger.info(
        "campaign_processed",
        campaign_id=campaign_id,
        sent=sent_count,
        total_pending=len(pending),
    )

    return {
        "status": "processing",
        "campaign_id": campaign_id,
        "sent": sent_count,
        "remaining": len(pending) - sent_count,
    }
