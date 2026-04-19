# Nexus Mail Agent

**AI-powered outreach automation and email management platform.**

Nexus Mail Agent processes incoming emails through a 3-agent LLM pipeline (Analyst → Copywriter → Critic), enriches leads with a 3-layer data waterfall, and sends replies with built-in anti-spam jitter — all managed through a sleek Next.js dashboard.

---

## Architecture

```
┌─────────────┐     ┌──────────────────────────────────────────┐
│  Gmail API  │────▶│         Unified Mail Schema              │
│  Outlook    │     │  (platform-agnostic normalization)       │
└─────────────┘     └──────────────┬───────────────────────────┘
                                   │
                    ┌──────────────▼───────────────┐
                    │     LangGraph Pipeline        │
                    │  ┌─────────┐  ┌───────────┐  │
                    │  │ Analyst │→│Copywriter │  │
                    │  │ (intent)│  │ (Tone     │  │
                    │  └─────────┘  │  Vault)   │  │
                    │               └────┬──────┘  │
                    │               ┌────▼──────┐  │
                    │               │  Critic   │  │
                    │               │ (auditor) │  │
                    │               └───────────┘  │
                    └──────────────┬───────────────┘
                                   │
          ┌──────────┐    ┌────────▼────────┐    ┌──────────────┐
          │ Enrichment│    │   Dashboard     │    │ Jitter Engine│
          │ Waterfall │    │  (Next.js)      │    │ Lexical +    │
          │ Hunter →  │    │  Human-in-loop  │    │ Temporal +   │
          │ Apollo →  │    │  review & send  │    │ Throttle     │
          │ Scraper   │    └─────────────────┘    └──────────────┘
          └──────────┘
```

### LLM Router Cascade

The system never depends on a single LLM provider:

| Priority | Provider | Model | Use Case |
|----------|----------|-------|----------|
| 1 (Primary) | Groq | Llama 3.3 70B | Fast inference |
| 2 (Fallback) | Gemini | 2.0 Flash-Lite | Rate limit fallback |
| 3 (Local) | Ollama | Llama 3.2 | Offline/local dev |

### Semantic Memory

Emails are embedded using `nomic-embed-text` via Ollama and stored in **pgvector** for similarity search. This enables context-aware replies — the agents know what you discussed with each sender previously.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | Python, FastAPI, Pydantic |
| Agents | LangGraph, LangChain |
| LLMs | Groq, Gemini, Ollama |
| Database | Supabase (Postgres + pgvector) |
| Task Queue | Celery + Redis |
| Auth | Authlib (OAuth2) |
| Embeddings | nomic-embed-text (768d) |
| Dashboard | Next.js 14, TypeScript |
| Scraping | BeautifulSoup, feedparser |

---

## Quick Start

### 1. Clone & Configure

```bash
git clone https://github.com/your-org/nexus-mail-agent.git
cd nexus-mail-agent
cp .env.example .env
# Edit .env with your API keys
```

### 2. Start Infrastructure

```bash
docker-compose up -d   # Redis + Postgres (via supabase/postgres image)
```

### Database: Supabase vs local Postgres

The Python code uses the **Supabase HTTP client** (`supabase.create_client`) for CRUD. That requires a real **Supabase project URL** and **service role key** in `.env` (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`).  

`docker-compose` only starts **Redis and Postgres**. Running `scripts/migrate_db.py` applies the schema to that Postgres (`DATABASE_URL`), but the API will still need a Supabase-compatible REST layer unless you switch the backend to direct SQL. For local development, point `SUPABASE_URL` / keys at a hosted Supabase project (recommended), or run the full Supabase stack locally so the URL matches your client.

### 3. Run Database Migrations

```bash
python scripts/migrate_db.py
```

### 4. (Optional) Seed Demo Data

```bash
python scripts/seed_data.py
```

### 5. Install Backend Dependencies

```bash
pip install -r requirements.txt
```

### 6. Start the API Server

```bash
uvicorn backend.main:app --reload --port 8000
```

### 7. Start Celery Worker

```bash
celery -A backend.celery_app:celery_app worker --loglevel=info
```

Verify registration: `celery -A backend.celery_app:celery_app inspect registered`

### 8. Start the Dashboard

```bash
cd dashboard
npm install
npm run dev
```

Optional: set `NEXT_PUBLIC_DEFAULT_USER_ID` (e.g. in `dashboard/.env.local`) so the UI defaults to your Supabase `user_id`. You can also change **User ID** in the sidebar at runtime (stored in `localStorage`).

Visit **http://localhost:3000** for the dashboard and **http://localhost:8000/docs** for the API docs.

### Environment notes

| Variable | Purpose |
|----------|---------|
| `PIPELINE_AFTER_FETCH` | If `true` (default), after each fetch the worker runs the Analyst → Copywriter → Critic pipeline and writes drafts. Set `false` to ingest only and run `POST /api/v1/emails/{user_id}/process-pipeline` manually. |
| `NEXT_PUBLIC_DEFAULT_USER_ID` | Dashboard default user id for API calls |

---

## Project Structure

```
nexus-mail-agent/
├── backend/
│   ├── main.py                    # FastAPI entry point
│   ├── core/
│   │   ├── config.py              # Pydantic Settings (.env)
│   │   └── logger.py              # structlog setup
│   ├── api/
│   │   ├── schemas.py             # Unified Mail Schema (Pydantic)
│   │   └── routes.py              # All API endpoints
│   ├── auth/
│   │   ├── gmail_auth.py          # Google OAuth2
│   │   └── outlook_auth.py        # Microsoft OAuth2
│   ├── connectors/
│   │   ├── base.py                # Abstract interface
│   │   ├── gmail.py               # Gmail API client
│   │   └── outlook.py             # Microsoft Graph client
│   ├── agents/
│   │   ├── llm_router.py          # Groq → Gemini → Ollama cascade
│   │   ├── analyst.py             # Intent classifier
│   │   ├── copywriter.py          # Draft generator (Tone Vault)
│   │   ├── critic.py              # Hallucination auditor
│   │   └── graph.py               # LangGraph orchestration
│   ├── memory/
│   │   ├── vector_store.py        # pgvector embeddings + search
│   │   └── profiler.py            # Digital Twin (Sent folder)
│   ├── enrichment/
│   │   ├── hunter.py              # L1 — email verification
│   │   ├── apollo.py              # L2 — company data
│   │   ├── scraper.py             # L3 — web scraping
│   │   └── social_monitor.py      # RSS + Google Alerts
│   ├── celery_app.py              # Celery application + task registration
│   ├── pipeline_runner.py         # LangGraph pipeline + draft persistence
│   └── workers/
│       ├── fetcher.py             # Email ingestion task
│       ├── sender.py              # Send engine
│       └── jitter/
│           ├── lexical.py         # Synonym substitution
│           ├── temporal.py        # Send-time randomization
│           └── throttle.py        # Volume hard caps
├── dashboard/                     # Next.js 14 frontend
│   ├── app/
│   │   ├── layout.tsx             # Root layout
│   │   ├── page.tsx               # Dashboard overview
│   │   ├── inbox/page.tsx         # Inbox triage
│   │   ├── drafts/page.tsx        # Draft review
│   │   ├── leads/page.tsx         # Lead cards
│   │   └── campaigns/page.tsx     # Campaign manager
│   └── package.json
├── scripts/
│   ├── migrate_db.py              # Database migration
│   ├── seed_data.py               # Test data seeder
│   └── tunnel_setup.sh            # Cloudflare tunnel
├── tests/                         # pytest test suite
├── docker-compose.yml             # Redis + Postgres
├── requirements.txt               # Python dependencies
└── .env.example                   # Environment template
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/auth/connect` | Initiate OAuth2 flow |
| `GET` | `/api/v1/auth/callback/gmail` | Gmail OAuth callback |
| `GET` | `/api/v1/auth/callback/outlook` | Outlook OAuth callback |
| `POST` | `/api/v1/emails/fetch` | Trigger email fetch |
| `GET` | `/api/v1/stats/{user_id}` | Aggregate counts (emails, drafts, leads, campaigns) |
| `POST` | `/api/v1/emails/{user_id}/process-pipeline` | Run agent pipeline on stored emails |
| `GET` | `/api/v1/emails/{user_id}` | List stored emails |
| `GET` | `/api/v1/emails/{user_id}/thread/{id}` | Get thread |
| `GET` | `/api/v1/drafts/{user_id}` | List drafts |
| `POST` | `/api/v1/drafts/{id}/review` | Approve/reject draft |
| `POST` | `/api/v1/drafts/{id}/send` | Send draft |
| `GET` | `/api/v1/leads/{user_id}` | List lead cards |
| `POST` | `/api/v1/leads/enrich` | Enrich a lead |
| `POST` | `/api/v1/campaigns` | Create campaign |
| `POST` | `/api/v1/campaigns/start` | Start campaign |
| `POST` | `/api/v1/campaigns/{id}/pause` | Pause campaign |
| `GET` | `/health` | Health check |

---

## Running Tests

```bash
python -m pytest tests/ -v
```

---

## License

MIT
