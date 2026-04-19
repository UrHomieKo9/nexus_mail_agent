"""Copywriter Agent — Drafts reply using Tone Vault (user's Sent folder profile)."""

import json

from backend.agents.llm_router import llm_router
from backend.api.schemas import CopywriterResult, EmailMessage, LinguisticProfile
from backend.core.logger import get_logger

logger = get_logger("copywriter")

SYSTEM_PROMPT = """You are an email copywriter that drafts replies in the user's own voice.
You will receive:
1. The original email to reply to
2. The user's linguistic profile (Tone Vault)
3. Context from previous interactions with the sender

You must draft a reply that:
- Matches the user's typical greeting style
- Matches the user's typical sign-off style
- Uses similar sentence length and vocabulary
- Has the same formality level
- Addresses all key points from the original email
- Sounds natural and human, NOT like an AI assistant

Respond with a JSON object:
{
  "draft_subject": "the reply subject line",
  "draft_body": "the full reply body text",
  "tone_match_score": 0.0 to 1.0 (how well you matched the user's tone),
  "key_points_addressed": ["list of points from original email that were addressed"]
}

IMPORTANT: Never use robotic phrases like "I hope this email finds you well" unless
that's in the user's profile. Never use "As an AI" or similar disclaimers.
Respond ONLY with the JSON object."""


async def draft_reply(
    email: EmailMessage,
    profile: LinguisticProfile | None = None,
    sender_context: list[dict] | None = None,
    analyst_notes: str = "",
) -> CopywriterResult:
    """Draft a reply to an email using the user's linguistic profile.

    Args:
        email: The email to reply to.
        profile: The user's linguistic profile (Tone Vault).
        sender_context: Previous interactions with this sender.
        analyst_notes: Additional notes from the Analyst agent.

    Returns:
        CopywriterResult with draft subject, body, and tone score.
    """
    prompt_parts = [
        "=== ORIGINAL EMAIL ===",
        f"From: {email.sender}",
        f"Subject: {email.subject}",
        f"Body:\n{email.body_clean[:3000]}",
    ]

    if profile:
        prompt_parts.extend([
            "\n=== YOUR TONE PROFILE ===",
            f"Average sentence length: {profile.avg_sentence_length} words",
            f"Common greetings: {', '.join(profile.common_greetings[:3])}",
            f"Common sign-offs: {', '.join(profile.common_signoffs[:3])}",
            f"Formality level: {profile.formality_level}/10",
        ])

    if sender_context:
        prompt_parts.append("\n=== PREVIOUS INTERACTIONS ===")
        for ctx in sender_context[:3]:
            prompt_parts.append(
                f"- {ctx.get('subject', 'N/A')}: "
                f"{ctx.get('body_snippet', '')[:100]}"
            )

    if analyst_notes:
        prompt_parts.append(f"\n=== ANALYST NOTES ===\n{analyst_notes}")

    prompt = "\n".join(prompt_parts)

    response = await llm_router.generate(prompt, system=SYSTEM_PROMPT, max_tokens=2048)

    try:
        result = _parse_llm_response(response.text)
    except (json.JSONDecodeError, KeyError) as exc:
        logger.warning("copywriter_parse_failed", error=str(exc))
        result = CopywriterResult(
            draft_subject=f"Re: {email.subject}",
            draft_body="Thank you for your email. I'll get back to you shortly.",
            tone_match_score=0.0,
            key_points_addressed=[],
        )

    logger.info(
        "reply_drafted",
        message_id=email.message_id,
        tone_score=result.tone_match_score,
        provider=response.provider,
    )

    return result


def _parse_llm_response(text: str) -> CopywriterResult:
    """Parse the LLM's JSON response into a CopywriterResult."""
    text = text.strip()

    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])

    data = json.loads(text)

    return CopywriterResult(
        draft_subject=data.get("draft_subject", ""),
        draft_body=data.get("draft_body", ""),
        tone_match_score=min(1.0, max(0.0, float(data.get("tone_match_score", 0.0)))),
        key_points_addressed=data.get("key_points_addressed", []),
    )