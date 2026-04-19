"""FastAPI routes — all API endpoints for dashboard + webhooks."""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from supabase import create_client

from backend.api.schemas import (
    AuthConnectRequest,
    Campaign,
    CampaignCreateRequest,
    CampaignStartRequest,
    DraftReply,
    DraftReview,
    EmailFetchRequest,
    EmailMessage,
    EmailPlatform,
    EmailSendRequest,
    LeadCard,
    PaginatedResponse,
)
from backend.auth.gmail_auth import (
    get_authorization_url as gmail_auth_url,
    handle_callback as gmail_callback,
    store_tokens as gmail_store_tokens,
)
from backend.auth.outlook_auth import (
    get_authorization_url as outlook_auth_url,
    handle_callback as outlook_callback,
    store_tokens as outlook_store_tokens,
)
from backend.connectors.gmail import GmailConnector
from backend.connectors.outlook import OutlookConnector
from backend.core.config import settings
from backend.core.logger import get_logger
from backend.pipeline_runner import process_emails_with_pipeline, row_to_email_message
from backend.workers.fetcher import fetch_user_emails

logger = get_logger("routes")
router = APIRouter()

_connectors = {
    EmailPlatform.GMAIL: GmailConnector(),
    EmailPlatform.OUTLOOK: OutlookConnector(),
}


# ── Auth Routes ──


@router.post("/auth/connect")
async def auth_connect(request: AuthConnectRequest, req: Request):
    """Initiate OAuth2 flow for the specified provider."""
    if request.provider == EmailPlatform.GMAIL:
        url = gmail_auth_url(req, request.redirect_uri)
    elif request.provider == EmailPlatform.OUTLOOK:
        url = outlook_auth_url(req, request.redirect_uri)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {request.provider}")

    return {"authorization_url": url, "provider": request.provider.value}


@router.get("/auth/callback/gmail")
async def gmail_auth_callback(request: Request):
    """Handle Gmail OAuth2 callback."""
    token_data = await gmail_callback(request)
    user_id = token_data.get("sub") or token_data.get("email")
    gmail_store_tokens(user_id, token_data)
    return {"status": "ok", "provider": "gmail", "email": token_data.get("email")}


@router.get("/auth/callback/outlook")
async def outlook_auth_callback(request: Request):
    """Handle Outlook OAuth2 callback."""
    token_data = await outlook_callback(request)
    user_id = token_data.get("email")
    outlook_store_tokens(user_id, token_data)
    return {"status": "ok", "provider": "outlook", "email": token_data.get("email")}


# ── Email Routes ──


@router.post("/emails/fetch")
async def fetch_emails(request: EmailFetchRequest):
    """Trigger email fetching for a user."""
    task = fetch_user_emails.delay(request.user_id, request.provider.value, request.max_results)
    return {"status": "queued", "task_id": task.id}


@router.get("/stats/{user_id}")
async def user_stats(user_id: str):
    """Aggregate counts for dashboard overview."""
    supabase = create_client(settings.supabase_url, settings.supabase_service_key)

    def _count(table: str) -> int:
        res = (
            supabase.table(table)
            .select("*", count="exact")
            .eq("user_id", user_id)
            .execute()
        )
        return res.count if getattr(res, "count", None) is not None else len(res.data or [])

    return {
        "user_id": user_id,
        "emails": _count("emails"),
        "drafts": _count("drafts"),
        "leads": _count("leads"),
        "campaigns": _count("campaigns"),
    }


@router.post("/emails/{user_id}/process-pipeline")
async def process_stored_emails_pipeline(user_id: str, max_emails: int = 30):
    """Run the 3-agent pipeline on recently stored inbox emails (skips messages that already have drafts)."""
    if max_emails < 1 or max_emails > 200:
        raise HTTPException(status_code=400, detail="max_emails must be between 1 and 200")

    supabase = create_client(settings.supabase_url, settings.supabase_service_key)

    result = (
        supabase.table("emails")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_sent", False)
        .order("timestamp", desc=True)
        .limit(max_emails)
        .execute()
    )

    rows = result.data or []
    emails = [row_to_email_message(row) for row in rows]
    stats = await process_emails_with_pipeline(user_id, emails)
    return {"status": "ok", "user_id": user_id, "emails_considered": len(emails), **stats}


@router.get("/emails/{user_id}")
async def list_emails(
    user_id: str,
    platform: EmailPlatform | None = None,
    page: int = 1,
    page_size: int = 20,
):
    """List stored emails for a user."""
    supabase = create_client(settings.supabase_url, settings.supabase_service_key)

    query = (
        supabase.table("emails")
        .select("*")
        .eq("user_id", user_id)
        .order("timestamp", desc=True)
        .range((page - 1) * page_size, page * page_size - 1)
    )

    if platform:
        query = query.eq("platform", platform.value)

    result = query.execute()

    return PaginatedResponse(
        items=result.data,
        page=page,
        page_size=page_size,
    )


@router.get("/emails/{user_id}/thread/{thread_id}")
async def get_thread(user_id: str, thread_id: str):
    """Get all messages in an email thread."""
    supabase = create_client(settings.supabase_url, settings.supabase_service_key)

    result = (
        supabase.table("emails")
        .select("*")
        .eq("user_id", user_id)
        .eq("thread_id", thread_id)
        .order("timestamp")
        .execute()
    )

    return {"thread_id": thread_id, "messages": result.data}


# ── Draft Routes ──


@router.get("/drafts/{user_id}")
async def list_drafts(
    user_id: str,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
):
    """List draft replies for human review."""
    supabase = create_client(settings.supabase_url, settings.supabase_service_key)

    query = (
        supabase.table("drafts")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .range((page - 1) * page_size, page * page_size - 1)
    )

    if status:
        query = query.eq("status", status)

    result = query.execute()
    return PaginatedResponse(items=result.data, page=page, page_size=page_size)


@router.post("/drafts/{draft_id}/review")
async def review_draft(draft_id: str, review: DraftReview):
    """Human review action on a draft — approve, edit, or reject."""
    supabase = create_client(settings.supabase_url, settings.supabase_service_key)

    update_data: dict[str, Any] = {
        "status": review.action.value,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    }

    if review.edited_body:
        update_data["body"] = review.edited_body
    if review.edited_subject:
        update_data["subject"] = review.edited_subject

    result = (
        supabase.table("drafts")
        .update(update_data)
        .eq("draft_id", draft_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Draft not found")

    logger.info("draft_reviewed", draft_id=draft_id, action=review.action.value)
    return {"status": "ok", "draft_id": draft_id, "action": review.action.value}


@router.post("/drafts/{draft_id}/send")
async def send_draft(draft_id: str, request: EmailSendRequest):
    """Send an approved draft through the connector."""
    supabase = create_client(settings.supabase_url, settings.supabase_service_key)

    draft_result = (
        supabase.table("drafts")
        .select("*")
        .eq("draft_id", draft_id)
        .execute()
    )

    if not draft_result.data:
        raise HTTPException(status_code=404, detail="Draft not found")

    draft = draft_result.data[0]

    # Import here to avoid circular imports
    from backend.workers.sender import send_email_task

    task = send_email_task.delay(
        draft_id=draft_id,
        apply_jitter=request.apply_jitter,
    )

    return {"status": "queued", "task_id": task.id}


# ── Lead Routes ──


@router.get("/leads/{user_id}")
async def list_leads(
    user_id: str,
    page: int = 1,
    page_size: int = 20,
):
    """List lead cards for a user."""
    supabase = create_client(settings.supabase_url, settings.supabase_service_key)

    result = (
        supabase.table("leads")
        .select("*")
        .eq("user_id", user_id)
        .order("score", desc=True)
        .range((page - 1) * page_size, page * page_size - 1)
        .execute()
    )

    return PaginatedResponse(items=result.data, page=page, page_size=page_size)


@router.post("/leads/enrich")
async def enrich_lead(email: str):
    """Trigger lead enrichment for a given email address."""
    from backend.enrichment.hunter import HunterEnrichment
    from backend.enrichment.apollo import ApolloEnrichment
    from backend.enrichment.scraper import WebScraper

    hunter = HunterEnrichment()
    apollo = ApolloEnrichment()
    scraper = WebScraper()

    # Layer 1: Hunter.io
    data = await hunter.lookup(email)

    # Layer 2: Apollo.io (if domain found)
    if data.get("company_domain"):
        apollo_data = await apollo.lookup(email, data.get("company_domain", ""))
        data.update(apollo_data)

    # Layer 3: Web scraper (if company website found)
    if data.get("company_website"):
        scrape_data = await scraper.scrape_company(data["company_website"])
        data.update(scrape_data)

    return data


# ── Campaign Routes ──


@router.post("/campaigns")
async def create_campaign(request: CampaignCreateRequest):
    """Create a new outreach campaign."""
    supabase = create_client(settings.supabase_url, settings.supabase_service_key)

    import uuid

    campaign_id = str(uuid.uuid4())
    recipients = [
        {"email": email, "status": "pending"}
        for email in request.recipient_emails
    ]

    record = {
        "campaign_id": campaign_id,
        "user_id": request.user_id,
        "name": request.name,
        "subject_template": request.subject_template,
        "body_template": request.body_template,
        "recipients": recipients,
        "status": "draft",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    supabase.table("campaigns").insert(record).execute()

    return {"status": "ok", "campaign_id": campaign_id}


@router.get("/campaigns/{user_id}")
async def list_campaigns(user_id: str):
    """List all campaigns for a user."""
    supabase = create_client(settings.supabase_url, settings.supabase_service_key)

    result = (
        supabase.table("campaigns")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )

    return {"campaigns": result.data}


@router.post("/campaigns/start")
async def start_campaign(request: CampaignStartRequest):
    """Start an outreach campaign."""
    supabase = create_client(settings.supabase_url, settings.supabase_service_key)

    supabase.table("campaigns").update({
        "status": "active",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }).eq("campaign_id", request.campaign_id).execute()

    from backend.workers.sender import process_campaign

    task = process_campaign.delay(request.campaign_id, request.apply_jitter)

    return {"status": "started", "campaign_id": request.campaign_id, "task_id": task.id}


@router.post("/campaigns/{campaign_id}/pause")
async def pause_campaign(campaign_id: str):
    """Pause an active campaign."""
    supabase = create_client(settings.supabase_url, settings.supabase_service_key)

    supabase.table("campaigns").update({
        "status": "paused",
    }).eq("campaign_id", campaign_id).execute()

    return {"status": "paused", "campaign_id": campaign_id}


# ── Webhook Routes ──


@router.post("/webhooks/gmail")
async def gmail_webhook(request: Request):
    """Handle Gmail push notifications (Pub/Sub webhook)."""
    body = await request.json()
    logger.info("gmail_webhook_received", data=body)

    # Decode the Pub/Sub message and trigger fetch
    # In production, decode the base64 data from the Pub/Sub message
    return {"status": "ok"}


@router.post("/webhooks/outlook")
async def outlook_webhook(request: Request):
    """Handle Outlook change notifications."""
    body = await request.json()
    logger.info("outlook_webhook_received", data=body)

    # Validate the client state and trigger fetch
    return {"status": "ok"}