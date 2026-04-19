"""Critic Agent — Audits drafts for hallucinations, bot-speak, and policy violations."""

import json

from backend.agents.llm_router import llm_router
from backend.api.schemas import CopywriterResult, CriticResult, EmailMessage
from backend.core.logger import get_logger

logger = get_logger("critic")

SYSTEM_PROMPT = """You are a quality auditor for AI-generated email drafts.
Your job is to review a draft reply and check for:

1. HALLUCINATIONS: Any fabricated facts, dates, numbers, names, or claims not present in the original email
2. BOT-SPEAK: Phrases that sound robotic or AI-generated, such as:
   - "I hope this email finds you well" (unless sender used similar phrasing)
   - "As an AI" or "As a language model"
   - "Please don't hesitate to reach out"
   - "I'd be more than happy to"
   - Excessive use of "delve", "leverage", "navigate", "facilitate"
3. POLICY VIOLATIONS: Any content that could be problematic:
   - Making promises the user didn't authorize
   - Sharing confidential information
   - Agreeing to terms/deals without approval
   - Unprofessional language or tone

Respond with a JSON object:
{
  "approved": true/false,
  "issues": ["list of specific issues found"],
  "hallucination_risk": 0.0 to 1.0,
  "bot_speak_risk": 0.0 to 1.0,
  "policy_violations": ["list of any policy violations"],
  "suggested_fixes": ["specific fixes for each issue"]
}

Be thorough but fair. Minor style differences are acceptable.
Respond ONLY with the JSON object."""


async def audit_draft(
    email: EmailMessage,
    draft: CopywriterResult,
) -> CriticResult:
    """Audit a draft reply for quality issues.

    Args:
        email: The original email being replied to.
        draft: The draft reply from the Copywriter.

    Returns:
        CriticResult with approval status and any issues found.
    """
    prompt_parts = [
        "=== ORIGINAL EMAIL ===",
        f"From: {email.sender}",
        f"Subject: {email.subject}",
        f"Body:\n{email.body_clean[:2000]}",
        "\n=== DRAFT REPLY ===",
        f"Subject: {draft.draft_subject}",
        f"Body:\n{draft.draft_body}",
    ]

    prompt = "\n".join(prompt_parts)

    response = await llm_router.generate(prompt, system=SYSTEM_PROMPT, max_tokens=1024)

    try:
        result = _parse_llm_response(response.text)
    except (json.JSONDecodeError, KeyError) as exc:
        logger.warning("critic_parse_failed", error=str(exc))
        # Default to not approved if we can't parse the result
        result = CriticResult(
            approved=False,
            issues=["Failed to parse critic output — requires manual review"],
            hallucination_risk=0.5,
            bot_speak_risk=0.5,
            policy_violations=[],
            suggested_fixes=["Please review this draft manually"],
        )

    logger.info(
        "draft_audited",
        message_id=email.message_id,
        approved=result.approved,
        issues_count=len(result.issues),
        provider=response.provider,
    )

    return result


def _parse_llm_response(text: str) -> CriticResult:
    """Parse the LLM's JSON response into a CriticResult."""
    text = text.strip()

    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])

    data = json.loads(text)

    return CriticResult(
        approved=bool(data.get("approved", False)),
        issues=data.get("issues", []),
        hallucination_risk=min(1.0, max(0.0, float(data.get("hallucination_risk", 0.0)))),
        bot_speak_risk=min(1.0, max(0.0, float(data.get("bot_speak_risk", 0.0)))),
        policy_violations=data.get("policy_violations", []),
        suggested_fixes=data.get("suggested_fixes", []),
    )