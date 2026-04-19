"""Pydantic models — Unified Mail Schema and API request/response types."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ── Enums ──


class EmailPlatform(str, Enum):
    GMAIL = "gmail"
    OUTLOOK = "outlook"


class IntentType(str, Enum):
    LEAD = "lead"
    SUPPORT = "support"
    SPAM = "spam"
    FOLLOW_UP = "follow_up"
    PERSONAL = "personal"
    NEWSLETTER = "newsletter"


class DraftStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    EDITED = "edited"
    REJECTED = "rejected"
    SENT = "sent"


class CampaignStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


# ── Core Email Models ──


class EmailMessage(BaseModel):
    """Unified Mail Schema — every email normalised into this object."""

    platform: EmailPlatform
    thread_id: str
    message_id: str = ""
    sender: str
    sender_name: str = ""
    recipient: str = ""
    subject: str
    body_clean: str = Field(default="", description="HTML-stripped body text")
    body_html: str = Field(default="", description="Original HTML body")
    timestamp: datetime
    attachments: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    is_read: bool = True
    is_sent: bool = False

    model_config = {"from_attributes": True}


class EmailThread(BaseModel):
    """A conversation thread containing multiple messages."""

    thread_id: str
    platform: EmailPlatform
    subject: str
    messages: list[EmailMessage] = Field(default_factory=list)
    participant_emails: list[str] = Field(default_factory=list)
    last_message_at: datetime | None = None
    label: str = ""

    model_config = {"from_attributes": True}


# ── Agent Models ──


class AnalystResult(BaseModel):
    """Output from the Analyst agent."""

    intent: IntentType
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    suggested_action: str = ""
    priority: int = Field(default=5, ge=1, le=10)


class CopywriterResult(BaseModel):
    """Output from the Copywriter agent."""

    draft_subject: str
    draft_body: str
    tone_match_score: float = Field(default=0.0, ge=0.0, le=1.0)
    key_points_addressed: list[str] = Field(default_factory=list)


class CriticResult(BaseModel):
    """Output from the Critic agent."""

    approved: bool
    issues: list[str] = Field(default_factory=list)
    hallucination_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    bot_speak_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    policy_violations: list[str] = Field(default_factory=list)
    suggested_fixes: list[str] = Field(default_factory=list)


class AgentPipelineResult(BaseModel):
    """Full output from the 3-agent pipeline."""

    email_message_id: str
    analyst: AnalystResult
    copywriter: CopywriterResult | None = None
    critic: CriticResult | None = None
    draft_id: str = ""
    status: DraftStatus = DraftStatus.PENDING


# ── Enrichment Models ──


class EnrichmentData(BaseModel):
    """Lead enrichment data from the 3-layer waterfall."""

    email: str
    email_verified: bool = False
    company_domain: str = ""
    company_name: str = ""
    company_size: str = ""
    industry: str = ""
    title: str = ""
    first_name: str = ""
    last_name: str = ""
    linkedin_url: str = ""
    company_website: str = ""
    company_description: str = ""
    funding_stage: str = ""
    estimated_arr: str = ""
    recent_news: list[str] = Field(default_factory=list)
    enrichment_layers_completed: int = Field(default=0, ge=0, le=3)

    model_config = {"from_attributes": True}


class LeadCard(BaseModel):
    """Assembled lead card displayed in the dashboard."""

    lead_id: str = ""
    email: str
    full_name: str = ""
    title: str = ""
    company: str = ""
    company_size: str = ""
    industry: str = ""
    funding_stage: str = ""
    estimated_arr: str = ""
    summary: str = ""
    enrichment: EnrichmentData | None = None
    last_interaction: datetime | None = None
    interaction_count: int = 0
    score: float = Field(default=0.0, ge=0.0, le=1.0)

    model_config = {"from_attributes": True}


# ── Campaign Models ──


class CampaignRecipient(BaseModel):
    """A single recipient in a campaign."""

    email: str
    name: str = ""
    company: str = ""
    status: str = "pending"
    sent_at: datetime | None = None
    opened: bool = False
    replied: bool = False


class Campaign(BaseModel):
    """An outreach campaign."""

    campaign_id: str = ""
    name: str
    subject_template: str
    body_template: str
    status: CampaignStatus = CampaignStatus.DRAFT
    recipients: list[CampaignRecipient] = Field(default_factory=list)
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_sent: int = 0
    total_opened: int = 0
    total_replied: int = 0

    model_config = {"from_attributes": True}


# ── Draft Models ──


class DraftReply(BaseModel):
    """A draft reply awaiting human review."""

    draft_id: str = ""
    thread_id: str
    platform: EmailPlatform
    to: str
    subject: str
    body: str
    original_message_id: str = ""
    agent_result: AgentPipelineResult | None = None
    status: DraftStatus = DraftStatus.PENDING
    created_at: datetime | None = None
    reviewed_at: datetime | None = None

    model_config = {"from_attributes": True}


class DraftReview(BaseModel):
    """Human review action on a draft."""

    action: DraftStatus
    edited_body: str | None = None
    edited_subject: str | None = None


# ── Linguistic Profile (Digital Twin) ──


class LinguisticProfile(BaseModel):
    """User's linguistic profile extracted from Sent folder."""

    user_id: str = ""
    avg_sentence_length: float = 0.0
    common_greetings: list[str] = Field(default_factory=list)
    common_signoffs: list[str] = Field(default_factory=list)
    formality_level: float = Field(default=5.0, ge=0.0, le=10.0)
    vocabulary_frequency: dict[str, int] = Field(default_factory=dict)
    avg_response_time_minutes: float = 0.0
    email_count_analyzed: int = 0
    last_updated: datetime | None = None

    model_config = {"from_attributes": True}


# ── API Request/Response Models ──


class AuthConnectRequest(BaseModel):
    """Request to initiate OAuth2 flow."""

    provider: EmailPlatform
    redirect_uri: str


class AuthCallbackRequest(BaseModel):
    """OAuth2 callback parameters."""

    provider: EmailPlatform
    code: str
    state: str = ""


class EmailFetchRequest(BaseModel):
    """Request to fetch emails for a user."""

    user_id: str
    provider: EmailPlatform
    max_results: int = Field(default=50, ge=1, le=500)
    query: str = ""


class EmailSendRequest(BaseModel):
    """Request to send a drafted email."""

    draft_id: str
    apply_jitter: bool = True


class CampaignCreateRequest(BaseModel):
    """Request to create a new outreach campaign."""

    user_id: str
    name: str
    subject_template: str
    body_template: str
    recipient_emails: list[str]


class CampaignStartRequest(BaseModel):
    """Request to start a campaign."""

    campaign_id: str
    apply_jitter: bool = True


class PaginatedResponse(BaseModel):
    """Generic paginated response wrapper."""

    items: list = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    has_next: bool = False