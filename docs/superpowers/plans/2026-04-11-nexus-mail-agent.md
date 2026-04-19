# Nexus Mail Agent — Full Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the complete Nexus Mail Agent platform — an AI-powered outreach automation and email management system with a 3-agent LLM pipeline, email connectors, semantic memory, lead enrichment, anti-spam jitter engine, and a Next.js dashboard.

**Architecture:** Platform-agnostic connectors normalize Gmail/Outlook into a Unified Mail Schema. A LangGraph pipeline of 3 agents (Analyst → Copywriter → Critic) processes each email. An LLM router cascades through Groq → Gemini → Ollama. Semantic memory uses pgvector + nomic embeddings. Lead enrichment uses a 3-layer waterfall (Hunter → Apollo → Scraper). The Jitter Engine adds anti-spam variation. A Next.js dashboard provides human-in-the-loop review.

**Tech Stack:** Python/FastAPI, LangGraph, Supabase/pgvector, Redis/Celery, Next.js, Authlib OAuth2, Groq/Gemini/Ollama LLMs

---

## File Structure

### Already Implemented (Phase 0)
- `backend/main.py` — FastAPI entry point ✅
- `backend/core/config.py` — Pydantic Settings ✅
- `backend/core/logger.py` — structlog setup ✅
- `docker-compose.yml` — Redis + Supabase Postgres ✅
- `requirements.txt` — All dependencies ✅
- `.env.example` — Environment template ✅

### To Implement

**Phase 1 — Auth Layer:**
- `backend/auth/gmail_auth.py` — Google OAuth2 + token refresh
- `backend/auth/outlook_auth.py` — Microsoft OAuth2 + token refresh

**Phase 2 — Ingestion Engine:**
- `backend/api/schemas.py` — Unified Mail Schema (Pydantic)
- `backend/connectors/base.py` — Abstract connector interface
- `backend/connectors/gmail.py` — Gmail API client
- `backend/connectors/outlook.py` — Microsoft Graph client
- `backend/workers/fetcher.py` — Celery email ingestion task
- `backend/api/routes.py` — FastAPI endpoints

**Phase 3 — Semantic Memory:**
- `scripts/migrate_db.py` — pgvector + tables migration
- `backend/memory/vector_store.py` — Embed + store + query
- `backend/memory/profiler.py` — Digital twin (Sent folder analysis)

**Phase 4 — Agent Pipeline:**
- `backend/agents/llm_router.py` — Groq → Gemini → Ollama cascade
- `backend/agents/analyst.py` — Intent classification agent
- `backend/agents/copywriter.py` — Draft generation agent
- `backend/agents/critic.py` — Hallucination auditor agent
- `backend/agents/graph.py` — LangGraph orchestration

**Phase 5 — Enrichment:**
- `backend/enrichment/hunter.py` — L1 email lookup
- `backend/enrichment/apollo.py` — L2 company data
- `backend/enrichment/scraper.py` — L3 web scraper
- `backend/enrichment/social_monitor.py` — RSS + Google Alerts

**Phase 6 — Outreach + Safety:**
- `backend/workers/sender.py` — Send engine
- `backend/workers/jitter/lexical.py` — Synonym substitution
- `backend/workers/jitter/temporal.py` — Send-time randomization
- `backend/workers/jitter/throttle.py` — Volume hard caps

**Phase 7 — Dashboard + Scripts:**
- `scripts/seed_data.py` — Test data seeder
- `scripts/tunnel_setup.sh` — Cloudflare tunnel config
- `dashboard/` — Next.js frontend (layout, pages, components)
- `tests/` — All test files

---

## Task List

### Task 1: Auth Layer — Gmail OAuth2
**Files:**
- Create: `backend/auth/gmail_auth.py`

- [ ] Implement Gmail OAuth2 flow with Authlib, token storage, and refresh

### Task 2: Auth Layer — Outlook OAuth2
**Files:**
- Create: `backend/auth/outlook_auth.py`

- [ ] Implement Microsoft OAuth2 flow with Authlib, token storage, and refresh

### Task 3: API Schemas — Unified Mail Schema
**Files:**
- Create: `backend/api/schemas.py`

- [ ] Define all Pydantic models: EmailMessage, EmailThread, LeadCard, DraftReply, AgentResult, EnrichmentData, Campaign, etc.

### Task 4: Connectors — Base Interface
**Files:**
- Create: `backend/connectors/base.py`

- [ ] Define abstract base class with fetch_emails, send_email, get_thread, list_labels methods

### Task 5: Connectors — Gmail Client
**Files:**
- Create: `backend/connectors/gmail.py`

- [ ] Implement Gmail API client using google-api-python-client

### Task 6: Connectors — Outlook Client
**Files:**
- Create: `backend/connectors/outlook.py`

- [ ] Implement Microsoft Graph API client

### Task 7: Workers — Email Fetcher
**Files:**
- Create: `backend/workers/fetcher.py`

- [ ] Implement Celery task for periodic email ingestion

### Task 8: API Routes
**Files:**
- Create: `backend/api/routes.py`

- [ ] Implement all FastAPI endpoints: auth, emails, drafts, campaigns, leads, health

### Task 9: DB Migration
**Files:**
- Create: `scripts/migrate_db.py`

- [ ] Create Supabase tables + pgvector extension

### Task 10: Vector Store
**Files:**
- Create: `backend/memory/vector_store.py`

- [ ] Implement pgvector embedding storage and semantic search

### Task 11: Profiler (Digital Twin)
**Files:**
- Create: `backend/memory/profiler.py`

- [ ] Implement linguistic profile extraction from Sent folder

### Task 12: LLM Router
**Files:**
- Create: `backend/agents/llm_router.py`

- [ ] Implement Groq → Gemini → Ollama cascade with fallback

### Task 13: Analyst Agent
**Files:**
- Create: `backend/agents/analyst.py`

- [ ] Implement intent classification: Lead / Support / Spam / Follow-up

### Task 14: Copywriter Agent
**Files:**
- Create: `backend/agents/copywriter.py`

- [ ] Implement draft generation using Tone Vault profile

### Task 15: Critic Agent
**Files:**
- Create: `backend/agents/critic.py`

- [ ] Implement hallucination/bot-speak/policy auditor

### Task 16: LangGraph Orchestration
**Files:**
- Create: `backend/agents/graph.py`

- [ ] Wire Analyst → Copywriter → Critic into LangGraph pipeline

### Task 17: Enrichment — Hunter.io
**Files:**
- Create: `backend/enrichment/hunter.py`

- [ ] Implement L1 email verification + domain lookup

### Task 18: Enrichment — Apollo.io
**Files:**
- Create: `backend/enrichment/apollo.py`

- [ ] Implement L2 company + contact data enrichment

### Task 19: Enrichment — Web Scraper
**Files:**
- Create: `backend/enrichment/scraper.py`

- [ ] Implement L3 website + LinkedIn scraping

### Task 20: Enrichment — Social Monitor
**Files:**
- Create: `backend/enrichment/social_monitor.py`

- [ ] Implement RSS + Google Alerts monitoring

### Task 21: Workers — Send Engine
**Files:**
- Create: `backend/workers/sender.py`

- [ ] Implement Celery send task with jitter integration

### Task 22: Jitter — Lexical
**Files:**
- Create: `backend/workers/jitter/lexical.py`

- [ ] Implement synonym substitution for anti-spam

### Task 23: Jitter — Temporal
**Files:**
- Create: `backend/workers/jitter/temporal.py`

- [ ] Implement send-time randomization

### Task 24: Jitter — Throttle
**Files:**
- Create: `backend/workers/jitter/throttle.py`

- [ ] Implement volume hard caps (3/hr, 30/day)

### Task 25: Scripts — Seed Data
**Files:**
- Create: `scripts/seed_data.py`

- [ ] Create test data seeder

### Task 26: Scripts — Tunnel Setup
**Files:**
- Create: `scripts/tunnel_setup.sh`

- [ ] Create Cloudflare tunnel configuration script

### Task 27: Dashboard — Next.js Scaffold
**Files:**
- Create: `dashboard/package.json`, `dashboard/app/layout.tsx`, pages, components

- [ ] Build Next.js dashboard with inbox triage, draft review, lead cards, campaign manager

### Task 28: Tests
**Files:**
- Create: `tests/test_agents.py`, `tests/test_api.py`, `tests/test_connectors.py`, `tests/test_enrichment.py`, `tests/test_workers.py`

- [ ] Write comprehensive tests for all modules

### Task 29: README
**Files:**
- Modify: `README.md`

- [ ] Write project documentation