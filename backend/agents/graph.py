"""LangGraph orchestration — wires Analyst → Copywriter → Critic pipeline."""

from datetime import datetime, timezone
from typing import TypedDict

from langgraph.graph import END, StateGraph

from backend.agents.analyst import classify_email
from backend.agents.copywriter import draft_reply
from backend.agents.critic import audit_draft
from backend.api.schemas import (
    AgentPipelineResult,
    AnalystResult,
    CopywriterResult,
    CriticResult,
    DraftStatus,
    EmailMessage,
    IntentType,
    LinguisticProfile,
)
from backend.core.logger import get_logger

logger = get_logger("graph")


class PipelineState(TypedDict, total=False):
    """State that flows through the agent pipeline."""

    email: EmailMessage
    profile: LinguisticProfile | None
    sender_context: list[dict] | None
    analyst_result: AnalystResult | None
    copywriter_result: CopywriterResult | None
    critic_result: CriticResult | None
    pipeline_result: AgentPipelineResult | None
    retry_count: int


# ── Node functions ──


async def analyst_node(state: PipelineState) -> dict:
    """Run the Analyst agent to classify the email."""
    email = state["email"]
    sender_context = state.get("sender_context")

    result = await classify_email(email, sender_context)

    return {"analyst_result": result}


def route_after_analyst(state: PipelineState) -> str:
    """Determine next step based on analyst classification.

    - Spam → end (no draft needed)
    - Newsletter → end (no draft needed)
    - Lead/Support/Follow-up/Personal → copywriter
    """
    analyst_result = state.get("analyst_result")
    if not analyst_result:
        return "copywriter"

    if analyst_result.intent in (IntentType.SPAM, IntentType.NEWSLETTER):
        logger.info(
            "skipping_draft",
            intent=analyst_result.intent.value,
            message_id=state["email"].message_id,
        )
        return END

    return "copywriter"


async def copywriter_node(state: PipelineState) -> dict:
    """Run the Copywriter agent to draft a reply."""
    email = state["email"]
    profile = state.get("profile")
    sender_context = state.get("sender_context")
    analyst_result = state.get("analyst_result")

    analyst_notes = ""
    if analyst_result:
        analyst_notes = f"Intent: {analyst_result.intent.value}. {analyst_result.reasoning}"

    result = await draft_reply(email, profile, sender_context, analyst_notes)

    return {"copywriter_result": result}


async def critic_node(state: PipelineState) -> dict:
    """Run the Critic agent to audit the draft."""
    email = state["email"]
    draft = state.get("copywriter_result")

    if not draft:
        return {"critic_result": None}

    result = await audit_draft(email, draft)

    return {"critic_result": result}


def route_after_critic(state: PipelineState) -> str:
    """Determine next step based on critic result.

    - Approved → end (draft ready for dashboard)
    - Not approved and retries < 2 → back to copywriter with feedback
    - Not approved and retries >= 2 → end (send to dashboard flagged)
    """
    critic_result = state.get("critic_result")
    if not critic_result:
        return END

    if critic_result.approved:
        return END

    retry_count = state.get("retry_count", 0)
    if retry_count < 2:
        return "copywriter"

    # Max retries reached — still goes to dashboard but flagged
    return END


def build_result_node(state: PipelineState) -> dict:
    """Build the final pipeline result from all agent outputs."""
    email = state["email"]
    analyst = state.get("analyst_result")
    copywriter = state.get("copywriter_result")
    critic = state.get("critic_result")

    retry_count = state.get("retry_count", 0)

    # Determine status
    status = DraftStatus.PENDING
    if critic and not critic.approved and retry_count >= 2:
        status = DraftStatus.PENDING  # Still pending — needs human review

    import uuid

    result = AgentPipelineResult(
        email_message_id=email.message_id,
        analyst=analyst or AnalystResult(intent=IntentType.FOLLOW_UP, confidence=0.0),
        copywriter=copywriter,
        critic=critic,
        draft_id=str(uuid.uuid4()),
        status=status,
    )

    return {"pipeline_result": result}


# ── Graph Construction ──


def build_pipeline() -> StateGraph:
    """Build the LangGraph agent pipeline.

    Flow:
    Analyst → (route) → Copywriter → Critic → (route) → END
                   ↓                              ↓
                  END                        Copywriter (retry)
    """
    graph = StateGraph(PipelineState)

    # Add nodes
    graph.add_node("analyst", analyst_node)
    graph.add_node("copywriter", copywriter_node)
    graph.add_node("critic", critic_node)
    graph.add_node("build_result", build_result_node)

    # Set entry point
    graph.set_entry_point("analyst")

    # Add conditional edges
    graph.add_conditional_edges("analyst", route_after_analyst, {
        "copywriter": "copywriter",
        END: "build_result",
    })

    graph.add_edge("copywriter", "critic")

    graph.add_conditional_edges("critic", route_after_critic, {
        "copywriter": "copywriter",
        END: "build_result",
    })

    graph.add_edge("build_result", END)

    return graph


# ── Public API ──

# Compile the graph once at module load
_pipeline = build_pipeline()
compiled_pipeline = _pipeline.compile()


async def run_pipeline(
    email: EmailMessage,
    profile: LinguisticProfile | None = None,
    sender_context: list[dict] | None = None,
) -> AgentPipelineResult:
    """Run the full 3-agent pipeline on an email.

    Args:
        email: The email to process.
        profile: User's linguistic profile (Tone Vault).
        sender_context: Previous interactions with sender.

    Returns:
        AgentPipelineResult with all agent outputs.
    """
    initial_state: PipelineState = {
        "email": email,
        "profile": profile,
        "sender_context": sender_context,
        "analyst_result": None,
        "copywriter_result": None,
        "critic_result": None,
        "pipeline_result": None,
        "retry_count": 0,
    }

    result = await compiled_pipeline.ainvoke(initial_state)

    pipeline_result = result.get("pipeline_result")
    if pipeline_result:
        return pipeline_result

    # Fallback: build result from whatever we have
    analyst = result.get("analyst_result")
    copywriter = result.get("copywriter_result")
    critic = result.get("critic_result")

    import uuid

    return AgentPipelineResult(
        email_message_id=email.message_id,
        analyst=analyst or AnalystResult(intent=IntentType.FOLLOW_UP, confidence=0.0),
        copywriter=copywriter,
        critic=critic,
        draft_id=str(uuid.uuid4()),
        status=DraftStatus.PENDING,
    )