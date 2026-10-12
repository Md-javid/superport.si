# SuperPort: Handover for the Antigravity agent

Read this file fully before changing anything. It tells you what the product is, what is real and what is simulated, how the code is organised, what is broken or risky, and what to build next in priority order.

Tagline: **Intelligence for Global Trade**. Status: **Phase 1 MVP, demo-grade, not production-ready.**

---

## 1. Purpose and use case

### What it is
SuperPort is an AI copilot for **customs clearance preparation**. A customs broker, import/export compliance officer, or freight forwarder uses it to turn three raw trade documents into a reviewed, clearance-ready file for one shipment.

### The problem it addresses
Preparing a shipment for customs today is manual and error-prone. Someone re-types data from a commercial invoice, packing list and bill of lading, cross-checks them by eye, looks up an HS (tariff) code, checks which permits and certificates apply, and decides how risky the shipment looks. Mistakes cause delays, demurrage, fines and held cargo.

### The core job SuperPort does
1. Take a shipment record plus the three documents.
2. Read the documents and extract the key fields, each with a confidence value.
3. Cross-check the documents against each other and against the shipment record.
4. Recommend an HS code with evidence and alternatives.
5. List compliance flags: missing documents, restrictions, certificates, inconsistencies.
6. Compute an **internal** risk score with explainable factors.
7. Make a **human** approve or reject at every important gate.
8. Produce a printable clearance-ready summary and a full audit trail.

### Primary user
A licensed customs broker or compliance analyst handling import shipments. Secondary: a freight forwarder's operations team preparing files for a broker.

### What the current version is good for
- A **product demo** and design prototype for customers, investors and hackathon judges.
- A **reference architecture** (workflow state machine, provider abstraction, agent registry, human-in-the-loop gates).
- A working skeleton to build real extraction, classification and compliance on top of.

### What it is NOT (do not let anyone claim otherwise)
- It does **not** submit anything to any customs authority.
- The risk score is an **internal estimate for review prioritisation**. It is not, and must never be presented as, a government Green/Orange/Red channel or a prediction of a customs decision.
- HS codes, price bands, restriction text, certificate lists and "lane familiarity" values are **illustrative demo data**, not authoritative tariff or legal data.
- It is not legal advice and has not been validated by a licensed broker.

---

## 2. Non-negotiable principles

1. **Human-in-the-loop is enforced on the server**, not only in the UI. See `backend/app/services/workflow.py`. Do not move gates to the client.
2. **AI recommends, humans decide.** Every AI output carries its source and a "human review required" framing where it affects a decision.
3. **No silent fabrication.** Anything generated rather than read from a document must be labelled (today: `source = "demo-synthesized"`). In production this fallback must be disabled (see roadmap P0-1).
4. **Never present the risk score as an authority decision.** Keep the disclaimer text in `risk.py` and `RiskStep.tsx`.
5. **Explain, do not overwhelm.** Each stage answers: what happened, why, what AI recommends, what needs approval, what happens next (`services/brief.py`, `CopilotBrief.tsx`).
6. **Demo and production integrations stay separated** behind provider interfaces (`backend/app/ai/`). Do not hard-code vendors into services.
7. **Audit everything a human or the AI changes** via `AuditEvent`. Never delete or rewrite events.
8. **Not a government portal.** Keep the UI calm, spacious and plain-language.

---

## 3. What is real vs simulated today

| Area | Status | Detail |
|---|---|---|
| Login, JWT, password hashing | Real (basic) | PBKDF2-SHA256 120k iterations, HS256 JWT, 12 h expiry (x14 with "remember me"). |
| Demo login | Simulated convenience | `POST /api/auth/demo`, enabled by `DEMO_MODE=true`. |
| Google / Apple sign-in | **Stub** | Buttons only show a toast. |
| Forgot password | **Stub** | Toast only. |
| User registration | **Missing** | Only the seeded demo user exists. |
| Shipment CRUD, documents upload, stage workflow, approvals, audit log | Real | Fully persisted via SQLAlchemy. |
| Text-based PDF extraction | Real | `pypdf` text + "Label: value" line parser. Works for the 3 sample PDFs. |
| Scanned/image extraction | **Fake** | If a file has no readable text, `_synthesize()` invents values from the shipment record, labelled "Demo generated". |
| Processing animation | **Cosmetic** | The 5-step pipeline is timed on the client (~3.5 s) while one synchronous API call runs. It does not reflect real stages. |
| Field editing and re-analysis | Real | Edits are persisted, flagged, audited, and trigger re-analysis. |
| Cross-document checks | Real logic, simple | Container, weight, quantity, invoice arithmetic, party-name similarity, origin. |
| HS recommendation | **Rule-based demo** | Keyword match against 7 products in `catalog.py`. Unknown goods fall back to 8479.89 at 41% confidence. |
| LLM usage | **Almost none** | `AI_MODE=live` + `ANTHROPIC_API_KEY` only rewrites the one-sentence HS rationale. HS code selection, compliance and risk do **not** use the LLM. (An earlier chat message overstated this; this document is correct.) |
| Compliance rules | **Demo data** | Restrictions and certificates come from the same 7-product catalog. Rules ignore the destination country. |
| Certificates | **Static** | Listed as "To be attached". No upload or verification. |
| Risk score | Real arithmetic, **arbitrary inputs** | Weights and thresholds are sensible but un-calibrated; origin table and price bands are made up. |
| Sanctions / denied-party screening | **Missing** | |
| Storage | Local disk | `UPLOAD_DIR`. Not suitable for multi-instance deploys. |
| Database | Real | PostgreSQL (Docker) or SQLite. Tables created by `create_all`, **no migrations**. |
| Seed data | Fictional | 7 shipments, seeded only when the users table is empty. |
| Customs submission | **Out of scope** | Regulated integration, separate phase. |

---

## 4. Repository map

```
HANDOVER.md                this file
ANTIGRAVITY_KICKOFF_PROMPT.md   paste-ready first prompt
README.md                  run instructions and demo walkthrough
docker-compose.yml         db (postgres 16) + api + web

backend/                   FastAPI, SQLAlchemy 2, Python 3.12
  app/main.py              app factory, lifespan: create_all + optional seed
  app/core/config.py       Settings (env driven)
  app/core/security.py     password hashing, JWT
  app/db.py                engine/session (sqlite or postgres)
  app/models.py            User, Shipment, Document, AuditEvent
  app/schemas.py           request bodies
  app/catalog.py           DEMO product/rules/lane data  <- replace in production
  app/seed.py              fictional seeded shipments
  app/api/                 auth, shipments, dashboard, misc (health, sample pdfs), deps
  app/services/
    workflow.py            STATE MACHINE and human gates (most important file)
    extraction.py          OCR text -> key/value parse -> fields, demo synthesis fallback
    hs_code.py             HS recommendation
    compliance.py          document completeness, restrictions, certificates, cross-checks
    risk.py                weighted internal risk score
    brief.py               "what happened / why / recommends / approval / next"
    serializers.py         API output shapes, clearance summary
    common.py              number parsing, text similarity helpers
  app/ai/                  provider interfaces + registry (OCRProvider, LLMProvider)
  app/agents/              Agent base, registry, Document/Customs/Compliance/Risk/Exception
  app/sample_data/*.pdf    3 text PDFs (lithium-ion battery shipment, 3.6% weight drift on purpose)
  scripts/make_sample_docs.py   regenerates the PDFs (needs reportlab)
  tests/test_flow.py       8 integration tests (in-memory SQLite)

frontend/                  Next.js 14 App Router, TypeScript, Tailwind 3.4, Framer Motion 11
  next.config.js           rewrites /api/* -> BACKEND_URL (default http://localhost:8000)
  tailwind.config.ts       design tokens (colours, shadows, keyframes)
  src/app/                 login, (app)/dashboard, (app)/shipments, shipments/new, shipments/[id]
  src/components/
    brand/                 Logo, OceanScene (animated gradient + shipping lanes, SVG/CSS only)
    layout/AppShell.tsx    sidebar, mobile drawer, auth guard
    ui/                    Button, Badge, Card/Ring/ProgressBar/etc, Toast
    shipment/              one component per workflow step + stepper + copilot brief
  src/lib/                 api.ts (typed client), auth.tsx, types.ts (mirrors API), utils.ts
```

Size: about 2,200 lines of Python and 2,300 lines of TypeScript/CSS. 17 REST endpoints.

---

## 5. Domain model and workflow

### Tables
- `users`: id, email (unique), name, role, company, password_hash.
- `shipments`: reference (unique, e.g. SP-2026-0001), importer, exporter, origin, destination, port, carrier, container_number, product_description, `stage`, JSON columns `hs_result`, `hs_decision`, `compliance`, `risk`, `analysis_runs`, created_by, timestamps.
- `documents`: shipment_id, doc_type (`commercial_invoice` | `packing_list` | `bill_of_lading`), filename, size, storage_path, `status` (`uploaded` | `ready`), JSON `fields`, JSON `meta`.
- `audit_events`: shipment_id, actor, kind (`system` | `human`), action, message, JSON detail, created_at.

Field object (inside `documents.fields`): `{key, label, value, original, confidence, source, edited}` where `source` is `extracted | demo-synthesized | edited | not-found`.

### Stage machine (`workflow.py`)
```
draft/documents --process--> extraction_review --confirm--> hs_review --HS approve|edit--> final_review --approve--> ready
                                   ^                              |  reject (stays hs_review)         |  reject --> rejected
                                   |-------------- edit ----------+----------------------------------+  edit --> extraction_review
                                                        reanalyze (from hs_review or final_review) --> hs_review
```
Progress map: draft 8, documents 22, extraction_review 42, hs_review 58, final_review 82, ready 100, rejected 82.

Server-enforced rules:
- Cannot confirm extraction without at least one processed document.
- Cannot review HS before extraction is confirmed.
- Cannot take the final decision unless stage is `final_review`; approve additionally requires an accepted HS code.
- If risk level is `high` **or** compliance overall is `action_required`, approval requires a note of at least 8 characters (HTTP 422 otherwise).
- `ready` and `rejected` are closed: documents and fields can no longer be changed.
- HS edit code must match `^\d{4}\.\d{2}(\.\d{2})?$`.

### REST API (prefix `/api`, Bearer token except login/demo/health/samples)
```
POST /auth/login            POST /auth/demo           GET  /auth/me
GET  /dashboard             GET  /health              GET  /samples/{name}.pdf
GET  /shipments             POST /shipments           GET  /shipments/{id}
POST /shipments/{id}/documents            (multipart: doc_type, file; 15 MB cap)
POST /shipments/{id}/documents/samples
POST /shipments/{id}/process
PATCH /shipments/{id}/documents/{doc_id}/fields/{key}   body {value}
POST /shipments/{id}/extraction/confirm
POST /shipments/{id}/hs/review     body {action: approve|edit|reject|reanalyze, hs_code?, note?}
POST /shipments/{id}/decision      body {action: approve|reject|edit|reanalyze, note?}
GET  /shipments/{id}/summary       (only meaningful when stage = ready)
```
OpenAPI docs at `http://localhost:8000/docs`. Frontend types in `src/lib/types.ts` mirror these shapes by hand; keep them in sync.

### Agents
`app/agents/builtin.py` registers `document` (no-op in Phase 1), `customs`, `compliance`, `risk`, and `exception` (declared stub, `implemented = False`). `workflow._analyze()` runs `customs -> compliance -> risk` through `registry.run_pipeline`. To add an agent: subclass `Agent`, implement `run(ctx) -> AgentResult`, register it. The dashboard lists agents from the registry.

---

## 6. Business logic reference (current numbers)

**Extraction** (`extraction.py`): a document is "readable" if at least `max(3, len(specs)//2)` fields parse from the text. Readable: missing fields become `not-found`, confidence 0.91-0.99 for found values. Not readable: every field is synthesized, confidence 0.82-0.94, source `demo-synthesized`.

**HS** (`hs_code.py`): keyword hits against the catalog. `confidence = 0.56 + 0.4 * coverage` (max 0.97), 0.41 with no hits, minus 0.08 if weight-per-unit looks implausible. Alternatives get `confidence - 0.28 - idx * 0.12`.

**Compliance** (`compliance.py`) tolerances: gross weight PL vs BoL warn above 2 percent, issue above 5 percent. Quantity mismatch above 0.1 percent. Invoice qty x price vs total above 0.5 percent. Party names: similarity below 0.6 is an issue, below 0.88 a warning (legal suffixes ignored). Overall: `action_required` if any item is `issue`, `needs_review` if any warning or HS awaiting review, else `clear`.

**Risk** (`risk.py`) weights: document consistency 0.30, classification 0.25, value anomaly 0.20, origin 0.10, missing info 0.15. Levels: low under 30, medium 30-49, high 50 and above. Factor scores: consistency = 38 per issue + 16 per warning (cap 100); classification = (1 - confidence) x 100, x0.4 once a human confirmed the HS; value anomaly = 6 inside the price band, else grows with distance, 50 if no price; origin from `ORIGIN_LANES` (default 20); missing = 35 per missing document + 9 per blank field (cap 100). Nothing here is calibrated against real data.

---

## 7. Frontend and design system

- Palette (in `tailwind.config.ts`): Prussian Blue `#031130`, SalesPort Blue `#185DF1`, Alice Blue `#F3F7FE`. Signal colours green/amber/red are used for risk levels only.
- Fonts: Plus Jakarta Sans (display) and Inter (body) via `@fontsource-variable`, self-hosted, no network at build.
- Motion: Framer Motion for page/step transitions, number counters, rings and bars; CSS keyframes in `tailwind.config.ts` for ambient aurora, waves, lane dashes, shimmer. `prefers-reduced-motion` is respected in `globals.css`.
- Hero effect lives in `components/brand/OceanScene.tsx`. Used on login and the dashboard banner.
- Shipment page (`shipments/[id]/page.tsx`) owns step navigation. `focusFor()` and `maxFor()` decide which step is current and which are unlocked. Each step is a self-contained component receiving the shipment and an `onChange(updated)` callback; the API always returns the full updated shipment.
- Auth: token in `localStorage` (remember me) or `sessionStorage`; `AppShell` redirects to `/login` when unauthenticated; the API client redirects on 401.
- Printing: `.no-print` and `.print-area` classes drive the summary print view.

---

## 8. Running, testing, configuring

```bash
# Docker (postgres)                       # Local (sqlite)
docker compose up --build                 cd backend && python -m venv .venv && source .venv/bin/activate
                                          pip install -r requirements-dev.txt
                                          uvicorn app.main:app --reload --port 8000
                                          cd frontend && npm install && npm run dev
```
Demo login: `demo@superport.ai` / `superport-demo`.

Tests: `cd backend && pytest` (8 passing at handover). `cd frontend && npm run typecheck && npm run build` (both passing). Regenerate sample PDFs: `python backend/scripts/make_sample_docs.py`.

Environment (`backend/.env.example`): `DATABASE_URL`, `SECRET_KEY`, `DEMO_MODE`, `SEED_DEMO_DATA`, `AI_MODE` (demo|live), `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` (default `claude-sonnet-5-5`, verify against current docs), `UPLOAD_DIR`, `CORS_ORIGINS`. Frontend: `BACKEND_URL` (server-side proxy target).

**Verification gaps at handover:** the UI was type-checked, built and smoke-tested over HTTP, but **never opened in a browser**. Docker Compose was **never run**. No frontend tests exist. Do a full visual and interaction pass first (Section 11).

---

## 9. Known issues, risks, tech debt

Security and correctness (fix early):
1. **No tenant isolation.** Every authenticated user sees every shipment. There is no organisation model or roles.
2. Defaults are unsafe for production: weak default `SECRET_KEY`, `DEMO_MODE=true`, `SEED_DEMO_DATA=true`, permissive demo endpoint. Must fail closed in production.
3. JWT in browser storage (XSS exposure), no refresh or revocation, no rate limiting, no lockout.
4. Upload validation is only client-side `accept` plus a 15 MB cap. No server MIME sniffing, no malware scan.
5. **Stale approvals:** editing a field after the HS code was approved re-runs analysis but keeps `hs_decision`. A reviewer may approve a code that no longer matches the data. Decide a policy (recommended: invalidate and send back to `hs_review` if the product or quantity fields change).
6. Audit log is an ordinary mutable table, not tamper-evident.
7. No optimistic locking: two reviewers can overwrite each other.

Product honesty:
8. `_synthesize()` fabricates data (labelled). Must be switchable off, and off by default in production.
9. Processing animation is cosmetic and will mislead once real OCR takes 10-60 s.
10. Compliance and restriction logic ignores destination country entirely.
11. Restriction status is always "warn" for known products; certificate list is static.
12. HS validator rejects national 8 and 10 digit codes (only 6 or 8 digits with dots).
13. Risk constants and `catalog.py` are not sourced or validated.

Engineering:
14. No Alembic migrations (`create_all` on boot).
15. Every field edit triggers full re-analysis synchronously. Fine now, expensive once LLM/OCR calls are added; needs debounce or background jobs.
16. SQLite returns naive datetimes, so timestamps may render with a timezone offset in the UI. Postgres is correct.
17. Dependencies are lower-bounded, not locked for Python. Add a lock file.
18. `frontend/src/lib/types.ts` is hand-maintained; generate from OpenAPI.
19. Accessibility and small-screen layout were not audited.

---

## 10. Roadmap with acceptance criteria

### P0: make the core genuinely real
**P0-1 Real document extraction**
- Add a `FieldExtractor` interface in `app/ai/` that returns structured fields with per-field confidence and a page/region reference when available. Keep `OCRProvider` for plain text.
- Implement at least one hosted provider (LLM vision or a document-AI service) selected by env. Validate its JSON strictly (pydantic), retry on malformed output, never trust it blindly.
- Add `ALLOW_SYNTHETIC_EXTRACTION` (default false outside demo). When false and nothing can be read, fields stay empty with `not-found`.
- Move processing to a background job with a persisted `processing` status and polling; make the UI pipeline reflect real status.
- Acceptance: a scanned PDF and a phone photo of an invoice extract correctly in a fixture test set; no synthesized values when `ALLOW_SYNTHETIC_EXTRACTION=false`; the UI shows real progress and real failures.

**P0-2 Real HS classification**
- Load an authoritative nomenclature (WCO HS plus the destination's national tariff, for example 8-digit India ITC-HS) into the database with full-text or vector search.
- Pipeline: retrieve candidate headings, let an LLM rank them with structured JSON output, validate that every returned code exists in the loaded nomenclature, show the matched heading text as evidence.
- Keep the human review gate, the "AI Recommendation: Human Review Required" label, alternatives and "why not".
- Build an evaluation set of at least 100 labelled products and report top-1 and top-3 accuracy in CI.
- Acceptance: codes outside the nomenclature are impossible; unknown goods yield a low-confidence result with a request for more detail, not a catch-all code.

**P0-3 Real, destination-aware compliance**
- Replace `catalog.py` restrictions with a versioned rules store keyed by (HS prefix, origin, destination), each rule with a source URL and effective date.
- Add denied-party / sanctions screening for importer, exporter and consignee (for example OpenSanctions) and surface hits as compliance issues.
- Add certificate upload per required certificate with status (missing, uploaded, verified by human).
- Acceptance: every restriction shown cites a source and date; changing destination changes the output.

**P0-4 Risk grounded in data, still explainable**
- Replace price bands and lane table with data-derived unit-value statistics (for example UN Comtrade) and documented country/lane indicators.
- Keep the five factor structure, the explanations and the disclaimer. Record the data version used in each score.
- Acceptance: each factor cites its data source; a calibration note documents how weights were chosen.

### P1: make it a product
- Registration, email verification, password reset (transactional email), Google/Apple OAuth, MFA option.
- Organisations, membership and roles (broker, reviewer, admin); scope every query by organisation; add tests that prove isolation.
- Alembic migrations; production settings that refuse to boot with default secrets or demo mode on.
- S3-compatible object storage with signed URLs; server-side file type checks and malware scanning.
- Tamper-evident audit log (append-only, hash-chained), optimistic locking on shipments, stale-approval policy (issue 5).
- Observability: structured logs, error tracking, metrics, request IDs. Rate limiting and security headers.
- OpenAPI-generated TypeScript client; frontend unit tests plus Playwright end-to-end for the full flow; CI running all of it.

### P2: later
Exception Agent (holds, queries, drafted replies), notifications, server-side PDF summary, bulk upload, multi-language, duty and tax estimates, and **regulated customs submission integrations** (do not start without legal and licensing review).

---

## 11. Do this first (suggested first session)

1. Read this file, `README.md`, `workflow.py`, `risk.py`, `compliance.py`, `extraction.py`.
2. Inspect the installed Agentic Awesome Skills and select a **focused set (about 6-8)** covering: planning/architecture, FastAPI backend, database and migrations, authentication and security, LLM/document-processing, testing/e2e, and frontend UX review. Write the chosen skills and why into `docs/skills-used.md`. Do not load the whole catalog.
3. Run it (Docker and local). Click through the full flow in a real browser at desktop and mobile widths. Record every visual or interaction bug in `docs/qa-findings.md` and fix the ones that break the demo.
4. Run `pytest`, `npm run typecheck`, `npm run build`. Keep them green.
5. Propose a short plan for P0-1 before coding it; confirm the choice of extraction provider and nomenclature source with the owner.
6. Work in small commits. Add or update tests with every behaviour change. Update `README.md` and this file when reality changes.

## 12. Definition of done for any change
- Tests added or updated and passing; typecheck and build pass.
- No new fabricated data path that is unlabelled.
- Human gates and disclaimers intact.
- New config documented in `.env.example` and `README.md`.
- UI verified in a browser, including empty, loading and error states.
- Audit events written for any new human or AI action.

## 13. Owner context
The owner is a student and freelance AI/ML developer building this as a serious portfolio and potential commercial product. They prefer a premium, trustworthy, ocean-themed enterprise look, strong motion and gradients, and an honest separation between demo and real functionality. When unsure whether something is real or simulated, label it clearly in the UI rather than blur the line.

---

## 14. v2 changes (read before Section 3, which describes v1)

v2 adds `backend/app/intelligence/` and keeps v1 behaviour when `INTELLIGENCE_MODE=off`. See `V2_README.md` for setup.

- **New:** Gemini client with model auto-detection, SerpApi client, response cache, per-shipment budgets, usage log, evidence table, feedback table, vision document reader, evidence-backed HS ranker with grounding checks, `/api/intelligence/status`, `/api/shipments/{id}/evidence`, `scripts/smoke_live.py`.
- **Changed behaviour:** in live mode unreadable documents are NOT fabricated (fields stay empty with an error). Seeded shipments are `is_demo` and never call external APIs. Field edits and HS approvals no longer re-run HS classification; only "confirm data" and re-analysis do.
- **Corrects Section 3:** with `INTELLIGENCE_MODE=live` the HS code itself now comes from Gemini + SerpApi, not only the rationale. Compliance rules and risk are still rule-based until milestone 3.
- **Still open:** live behaviour has only been tested against mock servers. First task: run `scripts/smoke_live.py` and fix anything it reports. Then continue with milestones 3 to 5 in `V2_README.md`. Gemini model names change; do not hardcode them.

### 14b. Milestones 3 and 4 (added later)
- **Market checks** (`backend/app/market/`): price check (Google Shopping), counterparty check (Google Maps + News with Gemini adjudication), cited rules lookup. Results are stored in `shipments.intel` and feed compliance and risk. Endpoint: `POST /api/shipments/{id}/verify`.
- **Trade Signal Radar** (`backend/app/radar/`): news search, event extraction, source-based verification, shipment matching, human review. Endpoints under `/api/radar/*` and `/api/shipments/{id}/signals`. Optional scheduler via `RADAR_INTERVAL_MINUTES`.
- **Rules to keep:** uncited items are discarded; signals never change a shipment by themselves; adverse news is a signal that needs a person to confirm; demo shipments use labelled sample data and never spend credits.
- **Still not validated live.** Run `scripts/smoke_live.py` first. Known gaps: price check is USD-only, no push notifications, no sanctions-list screening.

### 14c. Milestone 5: ecosystem foundation
- **New:** organisations, roles (admin/member), party types (broker, forwarder, importer, exporter), per-company isolation (`services/access.py`), invitations (shipment and team), checklist portal, comments with mentions, notifications, email service (Resend or console), rate limiting, registration, verification, password reset, production start guard, demo partner personas, upgrade step for older databases (`services/orgs.py`).
- **Access model:** `Shipment.org_id` is the owner. Other companies join through `ShipmentParticipant` and only get `/shipments/{id}/workspace`. Owner-only endpoints use `deps.get_shipment` (404 if no access, 403 for partners).
- **Rules to keep:** never expose AI findings, risk, HS or compliance to partners; radar review state is per organisation; email tokens are never sessions; a missing partner role must not be silently reassigned.
- **Not done:** Google OAuth, Alembic, S3 storage, live Resend test, fine-grained permissions inside a company, partner-side billing.

### 14d. Milestone 6: visibility
- **New:** `TimelineEvent` model and `services/timeline.py` (permissions per step, tracking applied without overriding manual edits), `tracking/` (ISO 6346 validator, provider interface, sample provider), `services/eta.py` (rule-based, every driver listed), `services/control_tower.py`, `api/tracking.py`, Radar carrier events and weather queries, seeded demo timelines.
- **Rules to keep:** sample tracking is always labelled; never invent an ETA when there is no baseline; customs clearance is never marked done by hand; partners never see broker-only review flags in the Control Tower.
- **Not done:** a real tracking provider, structured weather data, learned ETA, push notifications.

### 14e. Milestone 7: copilot, RAG, vector database
- **New:** `app/rag/` (chunker, embedders, `PgVectorStore` and `LocalStore`, indexer, one tenant filter in `build_filter`), `app/copilot/` (specialist agents, Coordinator, drafts), `api/copilot.py` (ask, history, drafts, send, library), `intelligence/gemini_client.embed`, `/api/intelligence/serpapi`, Library, SerpApi and Copilot screens.
- **Rules to keep:** every answer cites evidence and invalid citations are removed; never mix embedders in one search; isolation lives in `build_filter` and must stay in the query; AI drafts, a person sends; agents have distinct registry names (`status_eta`, `document_rag`, ...) so they never replace the analysis agents.
- **Not done:** Gemini function calling (the Coordinator plans deterministically and calls the model once to write), re-ranking, hybrid keyword + vector search, OCR for scanned library uploads, live validation of the Gemini embedding call (run `scripts/smoke_live.py`).
