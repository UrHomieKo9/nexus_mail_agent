"""Seed Data — populates the database with sample test data."""

import sys
import uuid
from datetime import datetime, timedelta, timezone

# Allow running as a standalone script
try:
    from supabase import create_client
    from backend.core.config import settings

    SUPABASE_URL = settings.supabase_url
    SUPABASE_KEY = settings.supabase_service_key
except Exception:
    import os
    from dotenv import load_dotenv

    load_dotenv()
    SUPABASE_URL = os.getenv("SUPABASE_URL", "http://localhost:54321")
    SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

# ── Sample data ──

DEMO_USER_ID = "demo-user-001"
NOW = datetime.now(timezone.utc)


def _ts(days_ago: int = 0, hours_ago: int = 0) -> str:
    return (NOW - timedelta(days=days_ago, hours=hours_ago)).isoformat()


SAMPLE_EMAILS = [
    {
        "user_id": DEMO_USER_ID,
        "platform": "gmail",
        "thread_id": "thread-001",
        "message_id": f"msg-{uuid.uuid4().hex[:8]}",
        "sender": "alice@techstartup.io",
        "sender_name": "Alice Chen",
        "recipient": "demo@nexusmail.app",
        "subject": "Partnership Opportunity — AI Integration",
        "body_clean": (
            "Hi there,\n\nI'm Alice from TechStartup. We're building an AI "
            "platform and saw your product demo. Would love to explore a "
            "potential partnership.\n\nAre you available for a 15-min call "
            "this week?\n\nBest,\nAlice"
        ),
        "timestamp": _ts(days_ago=1),
        "labels": ["INBOX", "IMPORTANT"],
        "is_read": False,
        "is_sent": False,
    },
    {
        "user_id": DEMO_USER_ID,
        "platform": "gmail",
        "thread_id": "thread-002",
        "message_id": f"msg-{uuid.uuid4().hex[:8]}",
        "sender": "support@saascorp.com",
        "sender_name": "Bob from SaasCorp",
        "recipient": "demo@nexusmail.app",
        "subject": "Re: API rate limit issue",
        "body_clean": (
            "Hey,\n\nWe're still hitting the 429 errors on the /v2/data "
            "endpoint. Can you bump our rate limit or suggest a workaround?\n\n"
            "Thanks,\nBob"
        ),
        "timestamp": _ts(days_ago=0, hours_ago=3),
        "labels": ["INBOX"],
        "is_read": True,
        "is_sent": False,
    },
    {
        "user_id": DEMO_USER_ID,
        "platform": "outlook",
        "thread_id": "thread-003",
        "message_id": f"msg-{uuid.uuid4().hex[:8]}",
        "sender": "newsletter@producthunt.com",
        "sender_name": "Product Hunt",
        "recipient": "demo@nexusmail.app",
        "subject": "🚀 Today's Top Products",
        "body_clean": (
            "Check out today's trending launches on Product Hunt! "
            "Featured: AI Code Review, Smart Calendar, and more..."
        ),
        "timestamp": _ts(days_ago=0, hours_ago=6),
        "labels": ["CATEGORY_PROMOTIONS"],
        "is_read": False,
        "is_sent": False,
    },
    {
        "user_id": DEMO_USER_ID,
        "platform": "gmail",
        "thread_id": "thread-004",
        "message_id": f"msg-{uuid.uuid4().hex[:8]}",
        "sender": "carol@enterprise.co",
        "sender_name": "Carol Martinez",
        "recipient": "demo@nexusmail.app",
        "subject": "Follow up: Enterprise pilot discussion",
        "body_clean": (
            "Hi,\n\nJust following up on our conversation from last week "
            "about the enterprise pilot. Our team has reviewed the proposal "
            "and we'd like to move forward with a 90-day trial.\n\nCan you "
            "send over the agreement?\n\nRegards,\nCarol"
        ),
        "timestamp": _ts(days_ago=2),
        "labels": ["INBOX", "STARRED"],
        "is_read": True,
        "is_sent": False,
    },
]

SAMPLE_LEADS = [
    {
        "lead_id": str(uuid.uuid4()),
        "user_id": DEMO_USER_ID,
        "email": "alice@techstartup.io",
        "full_name": "Alice Chen",
        "title": "Head of Partnerships",
        "company": "TechStartup",
        "company_size": "51-200",
        "industry": "Technology",
        "funding_stage": "Series A",
        "estimated_arr": "$2M-$5M",
        "summary": "Interested in AI integration partnership",
        "score": 0.85,
        "interaction_count": 3,
        "last_interaction": _ts(days_ago=1),
    },
    {
        "lead_id": str(uuid.uuid4()),
        "user_id": DEMO_USER_ID,
        "email": "carol@enterprise.co",
        "full_name": "Carol Martinez",
        "title": "VP of Engineering",
        "company": "Enterprise Co",
        "company_size": "1001-5000",
        "industry": "Enterprise Software",
        "funding_stage": "Series C",
        "estimated_arr": "$50M+",
        "summary": "Enterprise pilot — 90-day trial approved",
        "score": 0.92,
        "interaction_count": 7,
        "last_interaction": _ts(days_ago=2),
    },
]

SAMPLE_DRAFTS = [
    {
        "draft_id": str(uuid.uuid4()),
        "user_id": DEMO_USER_ID,
        "thread_id": "thread-001",
        "platform": "gmail",
        "to": "alice@techstartup.io",
        "subject": "Re: Partnership Opportunity — AI Integration",
        "body": (
            "Hi Alice,\n\nThanks for reaching out! I'd love to explore the "
            "partnership opportunity. I'm available this Thursday or Friday "
            "afternoon for a quick call.\n\nFeel free to grab a slot on my "
            "calendar: [calendar link]\n\nLooking forward to it!\n\nBest"
        ),
        "original_message_id": SAMPLE_EMAILS[0]["message_id"],
        "status": "pending",
        "created_at": _ts(hours_ago=1),
    },
]

SAMPLE_CAMPAIGNS = [
    {
        "campaign_id": str(uuid.uuid4()),
        "user_id": DEMO_USER_ID,
        "name": "Q2 Outreach — Series A Startups",
        "subject_template": "Quick question for {{name}} at {{company}}",
        "body_template": (
            "Hi {{name}},\n\nI noticed {{company}} recently raised a Series A "
            "— congrats! We help fast-growing teams like yours automate their "
            "outreach pipeline.\n\nWould you be open to a 10-min chat this week?\n\n"
            "Best,\nThe Nexus Team"
        ),
        "status": "draft",
        "recipients": [
            {"email": "alice@techstartup.io", "name": "Alice", "company": "TechStartup", "status": "pending"},
            {"email": "dave@newventure.com", "name": "Dave", "company": "NewVenture", "status": "pending"},
        ],
        "created_at": _ts(days_ago=0),
        "total_sent": 0,
    },
]

SAMPLE_PROFILE = {
    "user_id": DEMO_USER_ID,
    "avg_sentence_length": 12.5,
    "common_greetings": ["hi", "hey", "hello"],
    "common_signoffs": ["best", "cheers", "thanks"],
    "formality_level": 4.5,
    "vocabulary_frequency": {"team": 15, "product": 12, "call": 10, "love": 8},
    "email_count_analyzed": 150,
    "updated_at": _ts(days_ago=0),
}


def seed():
    """Insert all sample data into Supabase."""
    from supabase import create_client

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    tables = [
        ("emails", SAMPLE_EMAILS),
        ("leads", SAMPLE_LEADS),
        ("drafts", SAMPLE_DRAFTS),
        ("campaigns", SAMPLE_CAMPAIGNS),
        ("linguistic_profiles", [SAMPLE_PROFILE]),
    ]

    for table, data in tables:
        try:
            supabase.table(table).upsert(data).execute()
            print(f"  ✓ Seeded {len(data)} records into '{table}'")
        except Exception as exc:
            print(f"  ✗ Failed to seed '{table}': {exc}")

    print("\nSeed complete. Demo user ID:", DEMO_USER_ID)


if __name__ == "__main__":
    seed()
