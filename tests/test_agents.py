"""Tests for the 3-agent pipeline: Analyst → Copywriter → Critic."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from backend.agents.analyst import classify_email, _parse_llm_response as parse_analyst
from backend.agents.copywriter import draft_reply, _parse_llm_response as parse_copywriter
from backend.agents.critic import audit_draft, _parse_llm_response as parse_critic
from backend.agents.llm_router import LLMResponse
from backend.api.schemas import (
    AnalystResult,
    CopywriterResult,
    CriticResult,
    EmailMessage,
    EmailPlatform,
    IntentType,
    LinguisticProfile,
)


@pytest.fixture
def sample_email():
    return EmailMessage(
        platform=EmailPlatform.GMAIL,
        thread_id="t-001",
        message_id="m-001",
        sender="alice@company.com",
        sender_name="Alice",
        subject="Partnership Opportunity",
        body_clean="Hi, I'd love to discuss a partnership between our companies.",
        timestamp=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_profile():
    return LinguisticProfile(
        avg_sentence_length=12.5,
        common_greetings=["hi", "hey"],
        common_signoffs=["best", "cheers"],
        formality_level=4.5,
    )


# ── Analyst Agent ──


class TestAnalystParser:
    def test_parse_valid_response(self):
        raw = '{"intent":"lead","confidence":0.95,"reasoning":"Business inquiry","suggested_action":"draft_reply","priority":8}'
        result = parse_analyst(raw)
        assert result.intent == IntentType.LEAD
        assert result.confidence == 0.95
        assert result.priority == 8

    def test_parse_markdown_wrapped(self):
        raw = '```json\n{"intent":"spam","confidence":0.9,"reasoning":"Bulk email","suggested_action":"mark_spam","priority":1}\n```'
        result = parse_analyst(raw)
        assert result.intent == IntentType.SPAM

    def test_parse_unknown_intent_defaults_to_follow_up(self):
        raw = '{"intent":"unknown_type","confidence":0.5,"reasoning":"Unclear","suggested_action":"review","priority":5}'
        result = parse_analyst(raw)
        assert result.intent == IntentType.FOLLOW_UP

    def test_confidence_clamped(self):
        raw = '{"intent":"lead","confidence":1.5,"reasoning":"","suggested_action":"","priority":5}'
        result = parse_analyst(raw)
        assert result.confidence == 1.0


@pytest.mark.asyncio
async def test_classify_email(sample_email):
    mock_response = LLMResponse(
        text='{"intent":"lead","confidence":0.9,"reasoning":"Partnership inquiry","suggested_action":"draft_reply","priority":8}',
        provider="groq",
        model="llama-3.3-70b",
    )
    with patch("backend.agents.analyst.llm_router") as mock_router:
        mock_router.generate = AsyncMock(return_value=mock_response)
        result = await classify_email(sample_email)
        assert isinstance(result, AnalystResult)
        assert result.intent == IntentType.LEAD


@pytest.mark.asyncio
async def test_classify_email_fallback_on_parse_error(sample_email):
    mock_response = LLMResponse(text="not valid json", provider="groq", model="test")
    with patch("backend.agents.analyst.llm_router") as mock_router:
        mock_router.generate = AsyncMock(return_value=mock_response)
        result = await classify_email(sample_email)
        assert result.intent == IntentType.FOLLOW_UP
        assert result.confidence == 0.3


# ── Copywriter Agent ──


class TestCopywriterParser:
    def test_parse_valid_response(self):
        raw = '{"draft_subject":"Re: Partnership","draft_body":"Hi Alice, thanks for reaching out!","tone_match_score":0.88,"key_points_addressed":["partnership"]}'
        result = parse_copywriter(raw)
        assert result.draft_subject == "Re: Partnership"
        assert result.tone_match_score == 0.88

    def test_tone_score_clamped(self):
        raw = '{"draft_subject":"Re: Test","draft_body":"Body","tone_match_score":2.0,"key_points_addressed":[]}'
        result = parse_copywriter(raw)
        assert result.tone_match_score == 1.0


@pytest.mark.asyncio
async def test_draft_reply(sample_email, sample_profile):
    mock_response = LLMResponse(
        text='{"draft_subject":"Re: Partnership","draft_body":"Hey Alice, sounds great!","tone_match_score":0.9,"key_points_addressed":["partnership"]}',
        provider="gemini",
        model="gemini-2.0-flash-lite",
    )
    with patch("backend.agents.copywriter.llm_router") as mock_router:
        mock_router.generate = AsyncMock(return_value=mock_response)
        result = await draft_reply(sample_email, sample_profile)
        assert isinstance(result, CopywriterResult)
        assert "Partnership" in result.draft_subject


# ── Critic Agent ──


class TestCriticParser:
    def test_parse_approved(self):
        raw = '{"approved":true,"issues":[],"hallucination_risk":0.1,"bot_speak_risk":0.05,"policy_violations":[],"suggested_fixes":[]}'
        result = parse_critic(raw)
        assert result.approved is True
        assert result.hallucination_risk == 0.1

    def test_parse_rejected_with_issues(self):
        raw = '{"approved":false,"issues":["Uses AI language"],"hallucination_risk":0.2,"bot_speak_risk":0.8,"policy_violations":[],"suggested_fixes":["Remove AI phrasing"]}'
        result = parse_critic(raw)
        assert result.approved is False
        assert len(result.issues) == 1


@pytest.mark.asyncio
async def test_audit_draft(sample_email):
    draft = CopywriterResult(
        draft_subject="Re: Partnership",
        draft_body="Sounds great, let's connect!",
        tone_match_score=0.9,
    )
    mock_response = LLMResponse(
        text='{"approved":true,"issues":[],"hallucination_risk":0.05,"bot_speak_risk":0.1,"policy_violations":[],"suggested_fixes":[]}',
        provider="groq",
        model="test",
    )
    with patch("backend.agents.critic.llm_router") as mock_router:
        mock_router.generate = AsyncMock(return_value=mock_response)
        result = await audit_draft(sample_email, draft)
        assert isinstance(result, CriticResult)
        assert result.approved is True
