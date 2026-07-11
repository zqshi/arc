# Arc

> **Languages:** [简体中文](./README.md) | **English** (current)

> Every project you've done makes the next one faster and better.

Arc is an AI-native project delivery engine.
It doesn't just help you "manage projects" — it chains **requirement clarification, solution design, development execution, quality gating, and experience distillation** into a single unbroken delivery pipeline. What's done doesn't evaporate; pitfalls you've hit won't repeat.

## What Problem Does It Solve

There are already plenty of AI tools. Cursor helps you write code, ChatGPT helps you analyze requirements, v0 helps you generate prototypes.
But have you noticed — **they're disconnected from each other**:

- The requirements you spent half an hour clarifying in ChatGPT? You have to re-explain them from scratch when you switch to Cursor.
- The code is done, but why you chose approach A over approach B isn't recorded anywhere.
- The pitfall you hit last project? You hit it again this project — all the experience lives in your head, and resets to zero when someone else takes over.
- Every AI tool is "use and discard" — none of them knows what project you're working on, what stage you're at, or what decisions you've made.

The problem isn't that any single stage isn't fast enough — it's that **the stages don't connect at all**.

Arc builds exactly this overlooked highway.

## In One Sentence

Arc = a "context highway" for project delivery + a "experience asset bank" across projects.
Acquisition relies on the former (immediate efficiency gains), retention relies on the latter (compounding assets that get more valuable with use).

## Why It's Worth Looking At

- It's not another Jira / Linear — no scheduling, no resource allocation, no burndown charts
- It's not another AI coding tool — it doesn't compete with Cursor / Claude Code on single-point efficiency
- It's not an unsupervised autonomous agent — humans make decisions at key nodes, AI boosts efficiency at the execution layer
- It's **the only system that lets AI across all stages share the same project context**

## What You'll Feel Immediately

- From "re-explaining context to every tool" to "AI always knows what you're doing" — **zero context fragmentation**
- From "starting every project from scratch" to "AI proactively reminds you of pitfalls from last time" — **gets smarter with use**
- From "discovering unclear requirements after code is written" to "gate checks at every stage" — **built-in quality**
- From "can't answer when the client asks why this design" to "find the decision rationale in three seconds" — **traceable delivery**

## Core Value

### 1. Zero Context Fragmentation — Primary Acquisition Hook

From requirements analysis to deployment, AI always holds the complete project context. Everything you discussed with AI during the requirements phase is still remembered during development. No need to manually shuttle information between tools.

No existing product achieves this today. Cursor doesn't know your requirements, ChatGPT doesn't know what your code looks like, Jira doesn't know your technical decisions.

### 2. Smarter With Use — Core Moat Strategy

On your first project, the AI's suggestions are similar to ChatGPT. By your fifth project, the AI can directly tell you "last time you built a similar feature, you hit pitfall X — here's how to avoid it this time."

Experience accumulates automatically along two dimensions:
- **Personal experience**: tied to the user, reusable across projects. Your tech stack preferences, pitfall records, best practices
- **Project experience**: tied to the project, reusable across versions. Architecture constraints, tech debt, known issues

Experience data is non-portable — the longer you use it, the higher the switching cost. This creates a positive flywheel: more experience → more accurate AI → more user reliance → more experience.

### 3. Built-in Quality — Seven-Stage Gate System

At the end of each stage, the system evaluates deliverable quality — missing boundary conditions in requirements, overlooked concurrency handling in technical design, test cases not covering exception paths. Nothing moves forward until it passes the gate. Quality isn't an afterthought inspection; it's a process guarantee.

### 4. Traceable Delivery — Complete Chain from Requirements to Code

Any line of code can be traced back to its requirement origin, and any decision can be traced back to its discussion context and experience basis. For freelancers delivering projects and teams that need to produce delivery docs, this is tangible delivery value.

## How Arc Works

```
Project → Version → Requirement (three layers, no more)

Each requirement enters a 7-stage Pipeline:

Requirement Clarification (human-led, AI probes & structures)
   ↓
UI/UX Design (AI proposes, human selects)
   ↓
Technical Architecture (AI advises, human decides)
   ↓
Development Implementation (Agent executes, human reviews)
   ↓
Test Verification (Agent runs tests, human inspects)
   ↓
Deployment (Agent prepares, human approves)
   ↓
Experience Distillation (AI extracts, human confirms)

Each stage has a quality gate — nothing advances until it passes
Each stage's context — automatically passed to the next stage
Every completion — experience is automatically distilled and stored
```

## Who It's For

**Primary users: "AI-augmented" individuals and small teams with project delivery needs.**

- **Strong individual contractors**: freelancers / indie developers / full-stack PMs, managing 2-5 projects simultaneously, tired of starting every new project from scratch
- **Small team leads**: leaders of 3-10 person teams, need lightweight project management but don't want Jira, worried about team experience walking out the door with departing members

**Not suitable for:** Large enterprise PMOs that need SAFe/Jira-style heavy management; traditional teams that code purely by hand and reject AI involvement; casual users who just need a simple page.

## Current Capabilities

**Project Workspace**
- Project → Version → Requirement three-layer management
- Version activation / release / auto carry-over of incomplete requirements
- Requirement dependency system (blocked status display, dependency graph)
- Multi-tenant isolation architecture (Organization + Membership + org-scoped queries)

**Dual-Mode Delivery Engine**
- **Pipeline mode**: seven-stage Pipeline (with quality gate validation), stage conversation + deliverable management, skip / rollback
- **Conversation mode**: free-form conversation-driven, AgentLoop goal-driven + AutoPilot self-driving mode (max 12 rounds)
- Deliverable 8-stage decomposition (interaction design / visual specs / prototype design as independent stages)
- Prototype product preview (Blob URL + S3 persistent publishing)

**Domain Modeling**
- Project-level domain model auto-extraction (distilled from technical architecture deliverables)
- DDD three-stage autonomous modeling (strategic design → event storming → tactical modeling, AI-driven without manual intervention)
- Event storming data extraction (domain events + commands auto-merged into aggregate models)
- LLM-driven domain model quality review (strategy / tactics / naming / completeness four dimensions, scoring + issue list + improvement suggestions)
- Strategic design (subdomain partitioning + bounded contexts) + Tactical design (aggregates / entities / value objects / domain events)
- Dependency graph visualization (SVG connectors + hover highlight + click-to-lock + empty-state fallback grouping)
- Incremental merge refresh (manual trigger + auto extraction, continuous accumulation without data loss)

**Experience Engine**
- Personal experience + project experience dual dimensions
- Vector semantic search (pgvector) + automatic similar experience recall
- Confidence half-life decay (based on last-used time, active experience never expires)
- Experience distillation (project experience → personal experience, AI strips project-specific details)
- Batch experience extraction (manual trigger + auto extraction)
- Reuse effect tracking (category aggregation, expiry stats, top reuse ranking)

**Agent Orchestration**
- Multi-agent integration (OpenHands / Codex / Claude Code / Cursor)
- Multi-model adaptation (Anthropic / OpenAI / DeepSeek) + resilience layer
- Registry + Adapter pattern, dispatch on demand

**Monetization Foundation**
- Free / Pro / Team three-tier pricing (QuotaService + UsageDaily + frontend usage display)
- GitHub integration (Issue ↔ Todo bidirectional sync, Webhook HMAC-SHA256 verification)
- Cloud deployment (docker-compose.prod.yml, K8s manifests, GHCR CI/CD)

**Engineering Foundation**
- Authentication (account password + SMS verification code + JWT dual-token + refresh token revocation)
- Role-based permissions (admin / member / viewer, project member management)
- Real-time conversation (WebSocket + IDOR protection)
- SSE auto-reconnect + heartbeat detection
- API rate limiting (IP sliding window) + SMS anti-abuse
- Security hardening (path traversal protection, CSP injection, FK index optimization)
- Docker one-click deployment (multi-stage build, non-root execution)

**Native Client Build & Distribution**
- Three-platform CI orchestration (Windows / iOS / HarmonyOS, GitHub Actions matrix: hosted + self-hosted runners)
- Build readiness detection (CIRunnerKind tri-state + GHA token / S3 live probe + cache background refresh + frontend grayed-out)
- Five-platform signing chain (APPLE / WINDOWS / ANDROID / IOS / HARMONY signers + Fernet credential encryption)
- Unified BUILD artifact anchor (build → sign → distribute chain convergence)

**Capability & Skill Injection**
- Capability registry (Agent / Skill / MCP declaration management, env → DB migration + hot reload)
- Stage-level capability config (seven stages × capability checkboxes, instant save)
- Real skill injection execution chain (ClaudeCode `--mcp-config` real injection / Codex `/responses` tools / MCP SSE streaming)

**BaaS Auto-Assembly**
- Domain model → Supabase schema provisioning (CREATE SCHEMA + meta-model tables + business tables + RLS)
- RLS row-level isolation (user_id = auth.uid() + DEFAULT auth.uid(), not deny-all) + Supabase convention roles pre-built
- Conversation / pipeline dual-path auto-trigger provision (ArtifactPostProcessHooks reuses DomainModelService.provision_baas unified entry)
- Assembly observability dual view (product baas-status endpoint + frontend card / ops Prometheus metrics)

**Process Constraints & Gates**
- Three-tier constraints (STRICT / MODERATE / FREE, dependency DAG three tiers share hard invariants)
- Gate thresholds sourced from GateProfile (structural short-circuit + LLM scoring + pattern guard intercepting illegal operations)
- Process engine content orchestration (methodology / phase prompt / gate thresholds configurable)

**Production Observability**
- Structured access logs (method / path / status / duration / request_id)
- Probe separation (/health liveness + /ready readiness probing DB / Redis / S3, failure returns 503 to drain traffic)
- Prometheus metrics (HTTP QPS / latency + Agent task duration + BaaS provision full-path instrumentation)

## Tech Stack

| Layer | Choice |
|-------|--------|
| Backend | Python 3.12 · FastAPI · SQLAlchemy (async) · DDD four-layer architecture |
| Data | PostgreSQL 16 (pgvector) · Alembic Migration |
| Frontend | React 19 · TypeScript 6 · Vite 8 · Tailwind CSS 4 · PWA (Workbox) |
| AI | Anthropic · OpenAI · DeepSeek (multi-model dynamic switching + resilience layer) |
| Agent | OpenHands · Codex · Claude Code · Cursor (Registry + Adapter) |
| Deployment | Docker Compose · K8s manifests · GHCR CI/CD · non-root execution |
| Storage | S3 + BaaS unified storage layer (StorageAdapter) |
| Native Client | Tauri · Capacitor · GitHub Actions CI matrix (Windows / iOS / HarmonyOS) |
| Observability | Structured logging · /ready probe · Prometheus metrics |

## Quick Start

Requirements: Docker & Docker Compose · Node.js >= 22 · Python 3.12

### 1. Clone the Project

```bash
git clone https://github.com/zqshi/arc.git
cd arc
```

### 2. Environment Configuration

```bash
cp .env.example .env
# Edit .env, fill in at least one LLM API Key
# Production must set ARC_JWT_SECRET (openssl rand -hex 32)
```

### 3. Start

```bash
docker compose up -d
```

Service URLs:

- Frontend: http://localhost:3001
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### 4. Local Development

**Backend:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
docker compose up db -d
alembic upgrade head
ARC_DEBUG=true uvicorn arc.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

DEBUG mode auto-creates seed accounts: demo/demo123, test/test123

## Pre-Production Configuration

```bash
# Security (required)
ARC_JWT_SECRET=<openssl rand -hex 32>   # Refuses to start if unset
ARC_SIGNING_SECRET_KEY=<Fernet key>      # Signing credential encryption key, empty = dev fallback to plaintext (must set for production)
ARC_DEBUG=false
ARC_CORS_ORIGINS=https://your-domain
ARC_PROMETHEUS_TOKEN=<openssl rand -hex 32>  # /metrics bearer auth, empty = no verification (metrics exposed bare, must set for production)

# Database (required)
ARC_DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/arc

# Redis (required for multi-replica / multi-worker)
ARC_REDIS_URL=redis://redis:6379/0  # Cross-process event bus + rate limit shared counter; empty = single-worker in-memory (multi-replica rate limiting bypassed by replica count)

# Object Storage (recommended for production, otherwise preview static files write to local and need a writable volume mount)
ARC_STORAGE_ENDPOINT=https://s3.example.com
ARC_STORAGE_ACCESS_KEY=...
ARC_STORAGE_SECRET_KEY=...
ARC_STORAGE_BUCKET=arc-previews
ARC_STORAGE_PUBLIC_URL=https://cdn.example.com

# AI (configure at least one)
ARC_ANTHROPIC_API_KEY=sk-ant-...
ARC_OPENAI_API_KEY=sk-...
ARC_DEEPSEEK_API_KEY=sk-...

# SMS (don't use mock in production)
ARC_SMS_MOCK_MODE=false

# CI Build Orchestration (optional, only needed for Windows/iOS/HarmonyOS native client builds)
ARC_GHA_TOKEN=<PAT with actions:write permission>
ARC_GHA_OWNER=<owner>
ARC_GHA_REPO=<repo>
```

For full variable descriptions, see [.env.example](.env.example) (maps 1:1 to `backend/src/arc/config.py`). For full production deployment process (backup / alerting / secrets / Redis cloud hosting integration), see the [Deployment Runbook](./docs/deploy-runbook.md).

## Kubernetes Deployment

Production can deploy with `kubectl apply -k k8s/`. **Two prerequisites must be completed first**, otherwise deployment will fail:

```bash
# 1. Generate real Secrets (k8s/secrets.example.yml is only a placeholder template, real secrets.yml is gitignored and not committed)
cp k8s/secrets.example.yml k8s/secrets.yml
#   Fill in real values: ARC_DATABASE_URL / ARC_JWT_SECRET / at least one LLM Key / ARC_CORS_ORIGINS
#   Signing credential key ARC_SIGNING_SECRET_KEY generation:
#     python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 2. Replace image registry placeholders (ghcr.io/YOUR_ORG/arc-backend|arc-frontend in k8s/kustomization.yml)
#   with your actual GHCR org or private registry address
```

```bash
kubectl apply -k k8s/
```

Deployment manifest overview:
- `namespace.yml` — creates the arc namespace
- `configmap.yml` — non-sensitive config (maps to `backend/src/arc/config.py` fields)
- `secrets.yml` — sensitive config (**not committed, generated by copying `secrets.example.yml`**)
- `backend.yml` / `frontend.yml` / `redis.yml` — workloads
- `ingress.yml` — ingress routing

> Local storage mode (without `ARC_STORAGE_ENDPOINT`) requires mounting a writable volume to the backend Pod and setting `ARC_PREVIEW_STATIC_DIR=/app/data/static/previews`, otherwise preview static file writes will fail; production recommends configuring object storage.

## Common Commands

```bash
docker compose up -d                              # Full-stack start
ARC_DEBUG=true uvicorn arc.main:app --reload      # Backend development
cd frontend && npm run dev                        # Frontend development
cd backend && pytest -x                           # Backend tests
cd frontend && npm test                           # Frontend tests
cd backend && ruff check src/                     # lint
cd backend && alembic upgrade head                # Database migration
```

## Project Structure

```text
arc/
├── backend/
│   └── src/arc/
│       ├── domain/              # Domain layer (entities, value objects, repository interfaces)
│       │   ├── experience/      #   Experience entity (decay, reuse tracking)
│       │   ├── todo/            #   Requirement entity + value objects
│       │   └── artifact/        #   Deliverable entity
│       ├── application/         # Application layer
│       │   ├── agent/           #   Multi-agent orchestration (Registry + Adapter)
│       │   ├── ai/              #   LLM adapter + resilience layer
│       │   ├── auth/            #   Authentication (JWT + SMS + rate limiting)
│       │   ├── execution/       #   AgentLoop + DomainModelExtractor + Validator
│       │   ├── pipeline/        #   Seven-stage Pipeline service
│       │   ├── planning/        #   Planning engine (docs + roadmap)
│       │   └── experience/      #   Experience engine (vector search + dual-dimension accumulation)
│       ├── infrastructure/      # Infrastructure layer (ORM, repository implementations, storage adapters)
│       └── interface/           # Interface layer
│           ├── routes/          #   REST API (split by module, SQL pagination)
│           ├── ws/              #   WebSocket (conversation + IDOR protection)
│           ├── schemas/         #   Request/response schemas
│           └── middleware/      #   Middleware (API rate limiting, quota interception)
├── frontend/src/
│   ├── api/                     # API client (proactive token refresh, SSE reconnect)
│   ├── components/              # UI components + Artifact renderer
│   │   └── project/             #   Project detail subcomponents (domain model graph, experience library)
│   ├── contexts/                # React Context
│   ├── hooks/                   # Custom Hooks
│   └── pages/                   # Pages
├── docs/                        # Product vision, module breakdown, version management
│   └── versions/                #   Version snapshots + backlog
├── k8s/                         # Kubernetes deployment manifests
├── docker-compose.yml           # Development environment orchestration
├── docker-compose.prod.yml      # Production environment orchestration
├── CONTRIBUTING.md              # Documentation alignment spec
├── CHANGELOG.md                 # Changelog
└── .env.example                 # Environment variable template
```

## Documentation

- Product Vision: [docs/arc-product-vision.md](./docs/arc-product-vision.md)
- Module Breakdown: [docs/arc-module-breakdown.md](./docs/arc-module-breakdown.md)
- Agent Upgrade Plan: [docs/agent-upgrade-plan.md](./docs/agent-upgrade-plan.md)
- Changelog: [CHANGELOG.md](./CHANGELOG.md)
- Contributing: [CONTRIBUTING.md](./CONTRIBUTING.md)
- Environment Variables: [.env.example](./.env.example)
- Deployment Runbook: [docs/deploy-runbook.md](./docs/deploy-runbook.md)
- API Docs: visit http://localhost:8000/docs after startup

## Version History

| Version | Milestone | Status |
|---------|-----------|--------|
| v0.x | MVP — Project management + Pipeline + Experience library + Agent orchestration | done |
| v1.0 | Multi-user collaboration — Roles & permissions + Project members + Experience access control | done |
| v1.1 | Engineering hardening — Test coverage + unified pagination + Docker security | done |
| v1.2 | Delivery enhancement — AgentLoop + Domain modeling + Prototype preview + S3 storage | done |
| v2.0 | Monetization — Multi-tenancy + Billing + GitHub integration + Cloud deployment | done |
| v2.1 | DDD engineering — Three-stage autonomous modeling + Event storming + LLM quality review + schema alignment | done |
| v2.2-2.9 | Quality & intelligence upgrade — ContextEngine + DriftDetection + Checkpoints + GitSync | done |
| v3.0-3.8 | Domain model upgrade — Infrastructure upgrade + Impact analysis + Upgrade execution + Frontend integration | done |
| v5.1-5.2 | Context & priority — Prompt injection + AI Changelog + Priority visualization | done |
| v5.3 | Prototype preview architecture upgrade — Version dimension + S3 persistence + Empty-state protection | done |
| v5.4 | Deployment layer realization — Storage refactor + Deployment domain modeling + S3 static deployment | done |
| v5.5-5.6 | BaaS upgrade — Supabase runtime + Domain model templates + Project type framework | done |
| v6.0-6.2 | Container build chain — Tauri Linux build + Signing chain + Distribution | done |
| v6.3-6.6 | Governance & quality — Spec propagation + prompt intent-driven + Code quality fix wrap-up | done |
| v6.7-6.8 | Runtime entry — Credential API + skill hot reload + charter gates + Capability registry | done |
| v6.9-6.10 | Orchestration & modeling — Explicit artifact modeling + Type-based orchestration + Configurable process content | done |
| v6.11-6.13 | Production hardening — Full k8s + Domain error standardization + web/android build + Real signing | done |
| v6.14-6.16 | Governance convergence — Settings UX + DAG dependency guard + execution_mode retirement + Threshold source-of-truth | done |
| v6.17-6.18 | Production governance — Unified skill injection chain + Import cycle governance + CI builder image + MCP SSE | done |
| v6.19 | Native client platform expansion — Windows / iOS / HarmonyOS build targets + Readiness detection + Signers | Code complete, end-to-end pending credentials |
| v6.20 | LLM multi-vendor credentials — Fernet injection encryption + adapter health probe + Project-level llm_provider_id pointer | done |
| v6.21 | LLM chain deepening — Request-level resolve_from_project + env fallback + Frontend 10-component split | done |
| v6.22 | Scan chain fix — Worker uses DB credentials + 4xx no-retry + force rescan | done |
| v6.23 | Integration & scan governance — Integration suite flaky fix (33s deterministic) + Scan connects to DB + Experience/frontend UX | done |
| v6.24 | BaaS end-to-end + strict gate fix — Unified provision entry + RLS row-level isolation + Conversation blocking bug + Gate infinite loop fix (passed → score-driven + prompt rubric-ized + confirm review emergency escape valve) | done |

## License

[MIT](https://opensource.org/licenses/MIT)
