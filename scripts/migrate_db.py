"""Database migration — creates pgvector extension and all required tables."""

import sys

import psycopg2

# Allow running as a standalone script
try:
    from backend.core.config import settings

    DATABASE_URL = settings.database_url
except Exception:
    import os
    from dotenv import load_dotenv

    load_dotenv()
    DATABASE_URL = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres"
    )


MIGRATIONS = [
    # ── pgvector extension ──
    "CREATE EXTENSION IF NOT EXISTS vector;",

    # ── OAuth tokens ──
    """
    CREATE TABLE IF NOT EXISTS oauth_tokens (
        id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        user_id         TEXT NOT NULL,
        provider        TEXT NOT NULL CHECK (provider IN ('gmail', 'outlook')),
        access_token    TEXT NOT NULL,
        refresh_token   TEXT DEFAULT '',
        token_type      TEXT DEFAULT 'Bearer',
        expires_at      TIMESTAMPTZ,
        scope           TEXT DEFAULT '',
        email           TEXT DEFAULT '',
        updated_at      TIMESTAMPTZ DEFAULT now(),
        UNIQUE (user_id, provider)
    );
    """,

    # ── Emails ──
    """
    CREATE TABLE IF NOT EXISTS emails (
        id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        user_id         TEXT NOT NULL,
        platform        TEXT NOT NULL,
        thread_id       TEXT NOT NULL,
        message_id      TEXT NOT NULL UNIQUE,
        sender          TEXT DEFAULT '',
        sender_name     TEXT DEFAULT '',
        recipient       TEXT DEFAULT '',
        subject         TEXT DEFAULT '',
        body_clean      TEXT DEFAULT '',
        body_html       TEXT DEFAULT '',
        timestamp       TIMESTAMPTZ,
        attachments     JSONB DEFAULT '[]',
        labels          JSONB DEFAULT '[]',
        is_read         BOOLEAN DEFAULT true,
        is_sent         BOOLEAN DEFAULT false,
        created_at      TIMESTAMPTZ DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_emails_user_id ON emails (user_id);
    CREATE INDEX IF NOT EXISTS idx_emails_thread_id ON emails (thread_id);
    CREATE INDEX IF NOT EXISTS idx_emails_timestamp ON emails (timestamp DESC);
    """,

    # ── Email Embeddings (pgvector) ──
    """
    CREATE TABLE IF NOT EXISTS email_embeddings (
        id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        user_id         TEXT NOT NULL,
        message_id      TEXT NOT NULL,
        thread_id       TEXT DEFAULT '',
        sender          TEXT DEFAULT '',
        subject         TEXT DEFAULT '',
        body_snippet    TEXT DEFAULT '',
        platform        TEXT DEFAULT '',
        timestamp       TIMESTAMPTZ,
        embedding       VECTOR(768),
        created_at      TIMESTAMPTZ DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_embeddings_user_id ON email_embeddings (user_id);
    """,

    # ── Drafts ──
    """
    CREATE TABLE IF NOT EXISTS drafts (
        id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        draft_id        TEXT NOT NULL UNIQUE,
        user_id         TEXT NOT NULL,
        thread_id       TEXT DEFAULT '',
        platform        TEXT DEFAULT 'gmail',
        "to"            TEXT DEFAULT '',
        subject         TEXT DEFAULT '',
        body            TEXT DEFAULT '',
        original_message_id TEXT DEFAULT '',
        agent_result    JSONB,
        status          TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'edited', 'rejected', 'sent')),
        created_at      TIMESTAMPTZ DEFAULT now(),
        reviewed_at     TIMESTAMPTZ,
        sent_at         TIMESTAMPTZ,
        sent_message_id TEXT DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_drafts_user_id ON drafts (user_id);
    CREATE INDEX IF NOT EXISTS idx_drafts_status ON drafts (status);
    """,

    # ── Leads ──
    """
    CREATE TABLE IF NOT EXISTS leads (
        id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        lead_id         TEXT NOT NULL UNIQUE,
        user_id         TEXT NOT NULL,
        email           TEXT NOT NULL,
        full_name       TEXT DEFAULT '',
        title           TEXT DEFAULT '',
        company         TEXT DEFAULT '',
        company_size    TEXT DEFAULT '',
        industry        TEXT DEFAULT '',
        funding_stage   TEXT DEFAULT '',
        estimated_arr   TEXT DEFAULT '',
        summary         TEXT DEFAULT '',
        enrichment      JSONB,
        last_interaction TIMESTAMPTZ,
        interaction_count INT DEFAULT 0,
        score           FLOAT DEFAULT 0.0,
        created_at      TIMESTAMPTZ DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_leads_user_id ON leads (user_id);
    CREATE INDEX IF NOT EXISTS idx_leads_score ON leads (score DESC);
    """,

    # ── Campaigns ──
    """
    CREATE TABLE IF NOT EXISTS campaigns (
        id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        campaign_id     TEXT NOT NULL UNIQUE,
        user_id         TEXT DEFAULT '',
        name            TEXT NOT NULL,
        subject_template TEXT DEFAULT '',
        body_template   TEXT DEFAULT '',
        status          TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'paused', 'completed')),
        recipients      JSONB DEFAULT '[]',
        created_at      TIMESTAMPTZ DEFAULT now(),
        started_at      TIMESTAMPTZ,
        completed_at    TIMESTAMPTZ,
        total_sent      INT DEFAULT 0,
        total_opened    INT DEFAULT 0,
        total_replied   INT DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_campaigns_user_id ON campaigns (user_id);
    """,

    # ── Linguistic Profiles ──
    """
    CREATE TABLE IF NOT EXISTS linguistic_profiles (
        id                  UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        user_id             TEXT NOT NULL UNIQUE,
        avg_sentence_length FLOAT DEFAULT 0.0,
        common_greetings    JSONB DEFAULT '[]',
        common_signoffs     JSONB DEFAULT '[]',
        formality_level     FLOAT DEFAULT 5.0,
        vocabulary_frequency JSONB DEFAULT '{}',
        email_count_analyzed INT DEFAULT 0,
        updated_at          TIMESTAMPTZ DEFAULT now()
    );
    """,

    # ── Social Monitors ──
    """
    CREATE TABLE IF NOT EXISTS social_monitors (
        id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        user_id         TEXT NOT NULL,
        type            TEXT DEFAULT 'rss',
        source_url      TEXT NOT NULL,
        label           TEXT DEFAULT '',
        last_checked    TIMESTAMPTZ,
        created_at      TIMESTAMPTZ DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_monitors_user_id ON social_monitors (user_id);
    """,

    # ── Social Feed Items ──
    """
    CREATE TABLE IF NOT EXISTS social_feed_items (
        id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        monitor_id      UUID REFERENCES social_monitors(id) ON DELETE CASCADE,
        user_id         TEXT NOT NULL,
        title           TEXT DEFAULT '',
        link            TEXT DEFAULT '',
        summary         TEXT DEFAULT '',
        published_at    TIMESTAMPTZ,
        created_at      TIMESTAMPTZ DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_feed_items_user_id ON social_feed_items (user_id);
    """,

    # ── pgvector similarity search function ──
    """
    CREATE OR REPLACE FUNCTION match_emails(
        query_embedding VECTOR(768),
        match_threshold FLOAT,
        match_count INT,
        p_user_id TEXT,
        p_sender TEXT DEFAULT NULL
    )
    RETURNS TABLE (
        id UUID,
        user_id TEXT,
        message_id TEXT,
        thread_id TEXT,
        sender TEXT,
        subject TEXT,
        body_snippet TEXT,
        platform TEXT,
        timestamp TIMESTAMPTZ,
        similarity FLOAT
    )
    LANGUAGE plpgsql
    AS $$
    BEGIN
        RETURN QUERY
        SELECT
            ee.id,
            ee.user_id,
            ee.message_id,
            ee.thread_id,
            ee.sender,
            ee.subject,
            ee.body_snippet,
            ee.platform,
            ee.timestamp,
            1 - (ee.embedding <=> query_embedding) AS similarity
        FROM email_embeddings ee
        WHERE ee.user_id = p_user_id
          AND 1 - (ee.embedding <=> query_embedding) > match_threshold
          AND (p_sender IS NULL OR ee.sender = p_sender)
        ORDER BY ee.embedding <=> query_embedding
        LIMIT match_count;
    END;
    $$;
    """,
]


def run_migrations():
    """Execute all migration statements."""
    print(f"Connecting to: {DATABASE_URL[:40]}...")

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    for i, sql in enumerate(MIGRATIONS, 1):
        try:
            cur.execute(sql)
            print(f"  ✓ Migration {i}/{len(MIGRATIONS)} applied")
        except Exception as exc:
            print(f"  ✗ Migration {i}/{len(MIGRATIONS)} failed: {exc}")

    cur.close()
    conn.close()
    print("All migrations complete.")


if __name__ == "__main__":
    run_migrations()
