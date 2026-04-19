"""Run the LangGraph pipeline on fetched emails and persist drafts."""

from __future__ import annotations

import asyncio
from datetime import datetime

from supabase import create_client

from backend.agents.graph import run_pipeline
from backend.api.schemas import EmailMessage, EmailPlatform
from backend.core.config import settings
from backend.core.logger import get_logger
from backend.memory.profiler import Profiler
from backend.memory.vector_store import VectorStore

logger = get_logger("pipeline_runner")


def _supabase():
    return create_client(settings.supabase_url, settings.supabase_service_key)


def _draft_exists(user_id: str, message_id: str) -> bool:
    result = (
        _supabase()
        .table("drafts")
        .select("draft_id")
        .eq("user_id", user_id)
        .eq("original_message_id", message_id)
        .limit(1)
        .execute()
    )
    return bool(result.data)


def _persist_draft(user_id: str, email: EmailMessage, result) -> None:
    if not result.copywriter:
        return
    row = {
        "draft_id": result.draft_id,
        "user_id": user_id,
        "thread_id": email.thread_id,
        "platform": email.platform.value,
        "to": email.sender,
        "subject": result.copywriter.draft_subject,
        "body": result.copywriter.draft_body,
        "original_message_id": email.message_id,
        "agent_result": result.model_dump(mode="json"),
        "status": "pending",
    }
    _supabase().table("drafts").upsert(row, on_conflict="draft_id").execute()


async def process_emails_with_pipeline(user_id: str, emails: list[EmailMessage]) -> dict:
    """Embed emails, run Analyst → Copywriter → Critic, upsert drafts when a reply is drafted."""
    profiler = Profiler()
    profile = await profiler.get_profile(user_id)
    vs = VectorStore()

    drafts_created = 0
    skipped = 0
    errors = 0

    for email in emails:
        if email.is_sent:
            skipped += 1
            continue
        if _draft_exists(user_id, email.message_id):
            skipped += 1
            continue

        try:
            await vs.store_email(user_id, email)
        except Exception as exc:
            logger.warning(
                "embedding_store_failed",
                message_id=email.message_id,
                error=str(exc),
            )

        try:
            ctx = await vs.get_sender_context(user_id, email.sender)
            result = await run_pipeline(email, profile, ctx)
            if result.copywriter:
                _persist_draft(user_id, email, result)
                drafts_created += 1
        except Exception as exc:
            logger.error(
                "pipeline_failed",
                message_id=email.message_id,
                error=str(exc),
            )
            errors += 1

    return {
        "drafts_created": drafts_created,
        "skipped": skipped,
        "pipeline_errors": errors,
    }


def process_emails_with_pipeline_sync(user_id: str, emails: list[EmailMessage]) -> dict:
    return asyncio.run(process_emails_with_pipeline(user_id, emails))


def row_to_email_message(row: dict) -> EmailMessage:
    """Map a Supabase `emails` row to EmailMessage."""
    ts = row.get("timestamp")
    if isinstance(ts, str):
        timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    elif isinstance(ts, datetime):
        timestamp = ts
    else:
        timestamp = datetime.now()

    platform = row.get("platform", "gmail")
    try:
        ep = EmailPlatform(platform)
    except ValueError:
        ep = EmailPlatform.GMAIL

    return EmailMessage(
        platform=ep,
        thread_id=row.get("thread_id") or "",
        message_id=row.get("message_id") or "",
        sender=row.get("sender") or "",
        sender_name=row.get("sender_name") or "",
        recipient=row.get("recipient") or "",
        subject=row.get("subject") or "",
        body_clean=row.get("body_clean") or "",
        body_html=row.get("body_html") or "",
        timestamp=timestamp,
        attachments=row.get("attachments") or [],
        labels=row.get("labels") or [],
        is_read=row.get("is_read", True),
        is_sent=row.get("is_sent", False),
    )
