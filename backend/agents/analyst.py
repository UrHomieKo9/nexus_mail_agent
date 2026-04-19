"""Analyst Agent — Classifies intent: Lead / Support / Spam / Follow-up."""

import json

from backend.agents.llm_router import llm_router
from backend.api.schemas import AnalystResult, EmailMessage, IntentType
from backend.core.logger import get_logger

logger = get_logger("analyst")

SYSTEM_PROMPT = """You are an email intent classifier for a business email agent.
Your job is to read an incoming email and classify its intent.

You must respond with a JSON object containing:
- "intent": one of "lead", "support", "spam", "follow_up", "personal", "newsletter"
- "confidence": a float between 0.0 and 1.0
- "reasoning": a brief explanation of your classification
- "suggested_action": what the agent should do next (e.g., "draft_reply", "enrich_lead", "mark_spam", "escalate")
- "priority": an integer from 1 (lowest) to 10 (highest)

Classification rules:
- "lead": Email from a potential customer, partner, or business opportunity
- "support": Existing customer asking for help or reporting an issue
- "spam": Unsolicited bulk email, phishing, or irrelevant marketing
- "follow_up": Reply to an ongoing conversation or thread
- "personal": Non-business email from a known contact
- "newsletter": Automated mailing list or newsletter content

Respond ONLY with the JSON object, no additional text."""


async def classify_email(email: EmailMessage, sender_context: list[dict] | None = None) -> AnalystResult:
    """Classify an incoming email's intent using the LLM cascade.

    Args:
        email: The email to classify.
        sender_context: Optional previous interactions with this sender.

    Returns:
        AnalystResult with intent, confidence, and suggested action.
    """
    # Build the prompt with email content
    prompt_parts = [
        f"From: {email.sender}",
        f"Subject: {email.subject}",
        f"Body:\n{email.body_clean[:3000]}",
    ]

    if sender_context:
        prompt_parts.append("\nPrevious interactions with this sender:")
        for ctx in sender_context[:3]:
            prompt_parts.append(f"- Subject: {ctx.get('subject', 'N/A')}")

    prompt = "\n".join(prompt_parts)

    response = await llm_router.generate(prompt, system=SYSTEM_PROMPT, max_tokens=512)

    # Parse the LLM response
    try:
        result = _parse_llm_response(response.text)
    except (json.JSONDecodeError, KeyError) as exc:
        logger.warning("analyst_parse_failed", error=str(exc), raw=response.text[:200])
        # Default to follow_up if parsing fails
        result = AnalystResult(
            intent=IntentType.FOLLOW_UP,
            confidence=0.3,
            reasoning="Failed to parse LLM classification, defaulting to follow_up",
            suggested_action="manual_review",
            priority=5,
        )

    logger.info(
        "email_classified",
        message_id=email.message_id,
        intent=result.intent.value,
        confidence=result.confidence,
        provider=response.provider,
    )

    return result


def _parse_llm_response(text: str) -> AnalystResult:
    """Parse the LLM's JSON response into an AnalystResult."""
    # Try to extract JSON from the response
    text = text.strip()

    # Handle markdown code blocks
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])

    data = json.loads(text)

    # Map intent string to enum
    intent_map = {
        "lead": IntentType.LEAD,
        "support": IntentType.SUPPORT,
        "spam": IntentType.SPAM,
        "follow_up": IntentType.FOLLOW_UP,
        "personal": IntentType.PERSONAL,
        "newsletter": IntentType.NEWSLETTER,
    }

    intent_str = data.get("intent", "follow_up").lower()
    intent = intent_map.get(intent_str, IntentType.FOLLOW_UP)

    return AnalystResult(
        intent=intent,
        confidence=min(1.0, max(0.0, float(data.get("confidence", 0.5)))),
        reasoning=data.get("reasoning", ""),
        suggested_action=data.get("suggested_action", "manual_review"),
        priority=min(10, max(1, int(data.get("priority", 5)))),
    )