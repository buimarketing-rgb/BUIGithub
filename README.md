# BUI – Business Unified Intelligence

**Your Intelligent Business & Product Assistant.**

BUI is a self-hosted AI knowledge platform for a company team. Administrators feed it products, documents, FAQs and
reviewed online research. Team members then ask questions by text or voice and get fast answers grounded in that
approved company knowledge, with sources. BUI never invents specifications, prices, warranty terms or policies. When it
doesn't know, it says so and offers to research online, and marks anything it finds online as unverified.

Everything in the default install is free and open source: PostgreSQL + pgvector, Ollama, sentence-transformers,
SearXNG, the browser's own speech APIs and Docker. No paid API key is required.

---

## Features

| Module | What's included |
|---|---|
| **AI Assistant** | Streaming answers (SSE), Markdown, clickable `[n]` citations with verified/unverified badges, conversation history with full-text search, rename/delete, new chat, copy, regenerate, 👍/👎 feedback, related-question suggestions, follow-up context, 17 languages, clarifying questions for ambiguous product names, product comparison tables, "research it online" when knowledge is missing. |
| **Voice Assistant** | Mic button in chat and a dedicated voice page: Web Speech API speech-to-text, "Hey BUI" wake-phrase stripping, speechSynthesis read-aloud, stop speaking, repeat answer, hands-free **conversation mode**, language selection, microphone-permission handling and browser-support messages. Optional server-side **faster-whisper** fallback (MediaRecorder upload). |
| **Knowledge management** | Manual knowledge entries in 15 categories (Company Information … Other Knowledge); uploads of PDF, DOCX, XLSX, CSV, TXT and MD; product images; tags; product links; draft/published/archived; internal/restricted visibility; full **document versioning** with restore and download; automatic re-indexing on every change; **audit log**. |
| **Product database** | All the requested fields (brand, model, category, description, specifications, features, applications, compatibility, accessories, warranty, installation, maintenance, troubleshooting, pricing, images, documents, FAQs, source URLs, dates, status, version). Search, filter, sort and paginate; product detail page; edit with **version history** and restore; archive; delete. |
| **Online research** | Search by product, name or URL. SearXNG (default) or Brave adapter. Official manufacturer sites first. Honours robots.txt; never bypasses authentication; SSRF-guarded. Extracts specs, features, warranty, installation and FAQ content, and keeps source URLs and retrieval dates. Detects **duplicates** and **conflicts** (against verified data and between sources). **Approval workflow**: nothing reaches the knowledge base until approved, and verified values are never overwritten without an explicit "replace". Manual refresh plus daily/weekly/monthly schedules. |
| **RAG** | Heading-aware chunking, all-MiniLM-L6-v2 embeddings, pgvector HNSW + Postgres full-text **hybrid search** (RRF), IDF-weighted relevance gate, metadata, product and role filtering, source tracking, latest-version-only index, prompt-injection neutralisation. |
| **Model providers** | Ollama (local), any OpenAI-compatible API, and **extractive mode** (no LLM: answers are assembled from verified text). Falls back automatically if the LLM is down. Switchable at runtime in Settings. |
| **Team & security** | Super Admin / Admin / Team Member RBAC; Argon2id; JWT access tokens plus rotating httpOnly refresh tokens with reuse detection; CSRF header; password reset (e-mail via SMTP or an admin-issued one-time link); rate limiting; upload validation by magic bytes; signed file URLs; security headers. |
| **Dashboard & analytics** | Totals, recent updates, most-asked and unanswered questions, a knowledge-health score, questions/day chart, answer rate, latency, feedback, most-searched products, low-confidence answers, and a **knowledge-gap** report that turns unanswered questions into FAQs. |
| **Ops** | Docker Compose (Nginx, Postgres+pgvector, Redis, Ollama, SearXNG), Alembic migrations, background workers, Redis answer cache, backup/restore scripts, admin CLI, JSON export, dark/light themes, responsive UI. |

## Architecture

```
Browser (Next.js 15 · React 19 · Tailwind · Web Speech API)
   │
 Nginx ── /      → Next.js
   └──── /api/*  → FastAPI ──┬─ PostgreSQL 16 + pgvector  (data, versions, audit, vectors, full-text)
                             ├─ Redis                     (answer cache, rate limits)
                             ├─ Ollama / OpenAI-compatible (LLM)  ·  extractive fallback
                             └─ SearXNG                   (online research)
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the answer pipeline, index design and security model.

```
bui/
├── backend/               FastAPI app
│   ├── app/{api,core,models,schemas,services,rag,llm,research,voice,workers,seeds}
│   ├── migrations/        Alembic
│   └── tests/             pytest (real Postgres + pgvector)
├── frontend/              Next.js app (app/, components/, hooks/, services/, types/, public/)
├── docker/                nginx + searxng config
├── scripts/               backup.sh · restore.sh · dev.sh · test.sh
├── docs/                  ARCHITECTURE · ADMIN_GUIDE · DEPLOYMENT
├── docker-compose.yml
└── .env.example
```

## Technologies

**Frontend:** Next.js 15.5, React 19.1, TypeScript, Tailwind CSS 3.4, shadcn/ui-style components (hand-written, Radix-free), Lucide icons, react-markdown + remark-gfm.
**Backend:** Python 3.12, FastAPI 0.115, SQLAlchemy 2, Alembic, psycopg 3, pgvector, Pydantic 2, Argon2, PyJWT, httpx.
**AI:** Ollama (default `llama3.2:3b`), OpenAI-compatible adapter, sentence-transformers `all-MiniLM-L6-v2`.
**Documents:** PyMuPDF, python-docx, openpyxl, pandas, BeautifulSoup.
**Infra:** PostgreSQL 16 + pgvector, Redis 7, SearXNG, Nginx, Docker Compose.

---

## Quick start (Docker)

```bash
cp .env.example .env
```

Edit `.env`: set at least `SECRET_KEY` (generate with the command below), `POSTGRES_PASSWORD`, `PUBLIC_URL` and the `INITIAL_ADMIN_*` values.

```bash
python3 -c "import secrets;print(secrets.token_urlsafe(48))"
```

```bash
docker compose up -d --build
```

Open **http://localhost**. The first build downloads the embedding model, and the `ollama-pull` service downloads the LLM (≈2 GB).
To load sample data (fictional products), with optional demo accounts:

```bash
docker compose exec backend python -m app.seeds.demo --users
```

Demo accounts: `admin@demo.bui` / `DemoAdmin2026!` and `member@demo.bui` / `DemoMember2026!`. Remove all demo data with `--remove`.

### Default administrator

On first start BUI creates a **Super Admin** if none exists:
* e-mail `INITIAL_ADMIN_EMAIL` (default `admin@bui.local`)
* password `INITIAL_ADMIN_PASSWORD`. If left empty, a random password is generated and printed once:

```bash
docker compose logs backend | grep -A3 "FIRST RUN"
```

Sign in, change the password (Settings → Password), then add your team (Team Management).
Locked out? Reset it from the server:

```bash
docker compose exec backend python -m app.cli reset-password --email admin@bui.local
```

## Local development (without Docker)

Requires PostgreSQL 16 with pgvector, Python 3.12+ and Node 20+.

```bash
createdb bui && psql bui -c "CREATE EXTENSION vector;"
```

```bash
./scripts/dev.sh        # venv + deps + migrations + API :8000 + Next.js :3000 (proxies /api)
```

For semantic embeddings install the ML extras:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu && pip install -r backend/requirements-ml.txt
```

Without them BUI uses its built-in fallback embedder. For a local LLM install [Ollama](https://ollama.com) and pull the model:

```bash
ollama pull llama3.2:3b
```

Or set `LLM_PROVIDER=extractive`.

### Database setup & migrations

The schema is managed by Alembic (`backend/migrations`). Docker runs migrations automatically; manually:

```bash
cd backend && alembic upgrade head
```

The initial migration enables `CREATE EXTENSION vector` and creates every table with foreign keys, indexes, HNSW (cosine) and GIN full-text indexes. Company knowledge tables are separate from per-user chat tables (`conversations`, `messages`, `feedback`).

### Environment configuration

All configuration is in `.env` (documented in [.env.example](.env.example)). Credentials and API keys exist only as server environment variables and are never sent to the browser. Runtime behaviour (provider/model, relevance threshold, research policy, official domains, company name) can be changed by a Super Admin in **Settings → System**.

## Testing

Backend tests run against a real PostgreSQL + pgvector database (`TEST_DATABASE_URL`, default `postgresql+psycopg://bui:bui@localhost:5432/bui_test`; **the test database is wiped**):

```bash
cd backend && python -m pytest -q
```

```bash
./scripts/test.sh       # backend tests + frontend type-check + production build
```

**Results from the build session:**
* **56/56 backend tests pass.** They cover authentication (login, refresh rotation and reuse detection, logout, reset, rate limit), permissions (role matrix, restricted/draft hiding, private chat history), product CRUD with versioning/restore/archive and index sync, image validation and signed URLs, upload and parsing of PDF/DOCX/XLSX/CSV/TXT/MD, invalid and oversize files, document versions, FAQ retrieval, hybrid search, chat answers with citations, the no-hallucination "not found" path, comparisons, clarification, follow-ups, cache invalidation, regenerate, feedback, conversation search, prompt-injection handling, the LLM prompt contract and extractive fallback, the research engine (official-first, robots.txt, duplicates, conflicts, approval with and without replace, rejection, schedules, SSRF guard, chat research marked unverified), voice endpoints, analytics/knowledge gaps → FAQ, settings, health, re-index and export.
* **Frontend:** `tsc --noEmit` and `next build` are clean (18 routes).
* **End-to-end (Playwright, Chromium):** 21/21 scripted steps pass against the running app: login, streamed chat with citations, comparison, not-found → research offer, feedback, history search, every module page, product edit → new version, document upload → answered from the new document, settings/health, dark mode, a 390 px mobile layout with no horizontal overflow, and team-member nav restrictions.
* **Docker:** both images build, and the Compose stack (Postgres+pgvector, Redis, SearXNG, backend, frontend, Nginx) starts, migrates and passes the same E2E flow through Nginx, with SSE streaming intact.
* **LLM adapters:** the Ollama and OpenAI-compatible adapters were checked against a mock server speaking both streaming protocols, including the full answer pipeline.

## Known limitations

* **Not verified in the build environment** (its network blocked these downloads): retrieval quality with the real all-MiniLM-L6-v2 model, answer quality with a real Ollama model, live SearXNG web results, and the faster-whisper path. Tests used BUI's built-in fallback embedder and extractive mode. With MiniLM, retrieval should be noticeably better than the fallback; re-tune *Minimum relevance* in Settings if needed.
* **Voice** relies on the browser: Web Speech API recognition works in Chrome, Edge and Safari (not Firefox without server Whisper) and needs HTTPS or localhost. Some browsers send audio to the vendor's speech service. Automated tests could not use a real microphone; voice UI states were checked visually.
* **Scanned/image-only PDFs** are rejected with a clear message (no OCR). Images are stored and shown but not read by the AI.
* **Extractive mode** quotes and structures verified text but cannot paraphrase or translate. Use an LLM for non-English answers. The default embedding model is English-centric (a multilingual alternative is documented).
* Response time depends on the model and hardware. Retrieval itself takes milliseconds, but CPU-only local LLMs can take several seconds per answer.
* Research extraction is heuristic (tables, lists, headings). Pages rendered entirely by JavaScript yield little, and some sites block bots. Every finding still needs admin review by design.
* Single-tenant; no SSO/LDAP or 2FA yet. Password-reset e-mails need SMTP; otherwise admins issue one-time links.
* `ollama/ollama` and `searxng/searxng` use the `latest` tag. Pin them to versions you have tested for production.

## Deployment, backup & restore

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for hardware sizing, HTTPS, model choice, updates and hosting notes. Backups:

```bash
./scripts/backup.sh
```

Restore:

```bash
./scripts/restore.sh backups/bui-….tar.gz
```

Administrators: see [docs/ADMIN_GUIDE.md](docs/ADMIN_GUIDE.md).

## Assumptions & decisions

* **Single origin**: Nginx serves UI and API together, so refresh cookies are first-party and SameSite=Strict.
* **Admin approval = company approval.** Approved research applied to a product becomes verified product data, with the source URL recorded and a new version created. Approved research not applied to a product stays labelled *third-party research*.
* **Team members may trigger chat research** (configurable). Results are shown as unverified and queued for admin review; they are never stored as knowledge automatically.
* **Admins can manage team members; only Super Admins can manage administrators** and system settings.
* **Fallback embedder**: if MiniLM can't load, a deterministic feature-hashing embedder keeps BUI working, and the index rebuilds automatically once the real model is available.
* Demo data uses a **fictional** company ("Demoline") so it can't be mistaken for real product information.
