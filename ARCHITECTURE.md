# 🏗️ SuperPort — Architecture

Technical architecture reference for SuperPort's AI-powered customs clearance platform.

---

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (Next.js 14)                │
│  App Router · TypeScript · Tailwind CSS · Framer Motion  │
│  Port 3000                                               │
└──────────────────────┬──────────────────────────────────┘
                       │ REST API (Bearer JWT)
┌──────────────────────▼──────────────────────────────────┐
│                     Backend (FastAPI)                     │
│  SQLAlchemy · Pydantic · Python 3.12                     │
│  Port 8000                                               │
│                                                          │
│  ┌─────────┐  ┌──────────┐  ┌─────────┐  ┌───────────┐ │
│  │ Services │  │ Intel    │  │ Market  │  │ Radar     │ │
│  │ workflow │  │ gemini   │  │ price   │  │ news      │ │
│  │ extract  │  │ serpapi  │  │ party   │  │ events    │ │
│  │ hs_code  │  │ cache    │  │ rules   │  │ matching  │ │
│  │ comply   │  │ evidence │  │         │  │ verify    │ │
│  │ risk     │  │ feedback │  │         │  │           │ │
│  └─────────┘  └──────────┘  └─────────┘  └───────────┘ │
└──────────────────────┬──────────────────────────────────┘
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ Database │ │  SerpApi │ │  Gemini  │
    │ Postgres │ │ (Search) │ │  (LLM)  │
    │ / SQLite │ │          │ │          │
    └──────────┘ └──────────┘ └──────────┘
```

---

## Backend Modules

### Core (`app/core/`)
- **`config.py`** — Pydantic Settings with environment variable loading
- **`security.py`** — PBKDF2-SHA256 password hashing, HS256 JWT tokens

### Services (`app/services/`)
The business logic layer, independent of API transport.

| Service | File | Responsibility |
|---|---|---|
| **Workflow** | `workflow.py` | State machine with server-enforced human gates. The most important file. |
| **Extraction** | `extraction.py` | Document reading → key-value field parsing → confidence scoring |
| **HS Code** | `hs_code.py` | Tariff code recommendation (rule-based or SerpApi+Gemini in live mode) |
| **Compliance** | `compliance.py` | Cross-document checks, restrictions, certificates, counterparty results |
| **Risk** | `risk.py` | Six-factor weighted score with explainable breakdown |
| **Brief** | `brief.py` | "What happened / why / recommends / approval / next" copilot summaries |
| **Serializers** | `serializers.py` | API response shaping, clearance summary generation |

### Intelligence Layer (`app/intelligence/`)
The SerpApi + Google Gemini integration — the core differentiator.

- **Gemini client (`gemini_client.py`)** — Built on the official Google GenAI SDK (`google.genai`). Strictly leverages **Gemini 3.5 Flash-Lite** via the new **Interactions API** (`client.interactions.create`) for ultra-low-latency structured reasoning, alongside multimodal document parsing (`Part.from_bytes`) and vector embedding generation (`gemini-embedding-001`).
- **SerpApi client (`serpapi_client.py`)** — Interfaces with Google Search, Google Shopping, Google Maps, and Google News with automated JSON caching and wallet guards.
- **Response cache (`cache.py`)** — SHA-256 deduplication across identical queries (configurable 72-hour TTL).
- **Evidence pipeline (`evidence.py`)** — Search → rank → URL grounding verification → confidence adjustment.
- **Usage log (`cache.py`)** — Per-shipment budget tracking and hard daily organization caps to prevent unexpected API costs.
- **Feedback capture (`feedback.py`)** — Human edits and approvals are logged as structured dataset events for future model fine-tuning.

### Market Checks (`app/market/`)
SerpApi-powered real-world verification (triggered by "Run checks" on the Compliance step):

- **Price check** — Google Shopping comparison with outlier detection
- **Counterparty check** — Google Maps existence + Google News adverse media
- **Rules lookup** — Google Search for destination-specific import requirements

### Trade Signal Radar (`app/radar/`)
Continuous trade intelligence monitoring:

- **News search** — SerpApi Google News for ports, countries, products
- **Event extraction** — Gemini converts articles to structured events (or keyword fallback)
- **Source verification** — confidence scoring by independent publisher count
- **Shipment matching** — links signals to affected shipments

### Agents (`app/agents/`)
Thin orchestration layer over services:

- `DocumentAgent` — document processing coordination
- `CustomsAgent` — HS code pipeline
- `ComplianceAgent` — compliance rule evaluation
- `RiskAgent` — risk factor computation
- `ExceptionAgent` — planned stub for hold/query handling

### Tracking (`app/tracking/`)
Container tracking with provider interface:

- ISO 6346 container number validation
- `sample` provider (demo data, always labelled)
- Extensible for real tracking APIs (MarineTraffic, etc.)

---

## Shipment Workflow State Machine

```
draft/documents ──process──► extraction_review ──confirm──► hs_review ──approve──► final_review ──approve──► ready
                                    ▲                           │                        │
                                    │◄──────── edit ────────────┤                        │
                                    │                      reject (stays)           reject ──► rejected
                                    │◄──────── reanalyze ──────┤────────────────────────┤
```

**Server-enforced rules:**
- Cannot confirm extraction without at least one processed document
- Cannot review HS before extraction is confirmed
- Cannot take final decision unless stage is `final_review`
- High-risk or action-required shipments need a justification (≥8 chars) to approve
- `ready` and `rejected` are terminal — no further document changes

---

## Database Schema

| Table | Key Fields |
|---|---|
| `users` | id, email, name, role, company, password_hash |
| `shipments` | reference, importer, exporter, origin, destination, stage, hs_result, compliance, risk, org_id |
| `documents` | shipment_id, doc_type, filename, status, fields (JSON), meta (JSON) |
| `audit_events` | shipment_id, actor, kind, action, message, detail (JSON) |
| `feedback_events` | shipment_id, field corrections, HS decisions (training data) |

Supports **PostgreSQL** (production) and **SQLite** (development). Tables created automatically on first boot.

---

## Frontend Architecture

- **Framework:** Next.js 14 App Router with TypeScript
- **Styling:** Tailwind CSS 3.4 with custom design tokens (Prussian Blue → SalesPort Blue → Alice Blue)
- **Motion:** Framer Motion for page transitions, number counters, progress indicators
- **Fonts:** Plus Jakarta Sans (display) + Inter (body), self-hosted via `@fontsource-variable`
- **Auth:** JWT in localStorage/sessionStorage with automatic 401 redirect
- **API Client:** Typed client in `src/lib/api.ts` mirroring backend schemas

### Component Structure

```
src/components/
├── brand/          Logo, OceanScene (animated gradient hero)
├── layout/         AppShell (sidebar, mobile drawer, auth guard)
├── ui/             Button, Badge, Card, Ring, ProgressBar, Toast
└── shipment/       One component per workflow step + stepper + copilot brief
```

---

## API Reference

All endpoints under `/api`, authenticated via Bearer token (except login/demo/health).

### Auth
| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/login` | Email + password login |
| POST | `/auth/demo` | One-click demo login |
| GET | `/auth/me` | Current user info |

### Shipments
| Method | Endpoint | Description |
|---|---|---|
| GET | `/shipments` | List all shipments |
| POST | `/shipments` | Create shipment |
| GET | `/shipments/{id}` | Get shipment detail |
| POST | `/shipments/{id}/documents` | Upload document (multipart, 15MB cap) |
| POST | `/shipments/{id}/documents/samples` | Load sample documents |
| POST | `/shipments/{id}/process` | Start AI analysis |
| PATCH | `/shipments/{id}/documents/{doc}/fields/{key}` | Edit extracted field |
| POST | `/shipments/{id}/extraction/confirm` | Confirm extraction |
| POST | `/shipments/{id}/hs/review` | HS code decision |
| POST | `/shipments/{id}/decision` | Final approval/rejection |
| GET | `/shipments/{id}/summary` | Clearance-ready summary |
| POST | `/shipments/{id}/verify` | Run market checks |
| GET | `/shipments/{id}/evidence` | Get web evidence |
| GET | `/shipments/{id}/signals` | Get matched radar signals |

### Radar
| Method | Endpoint | Description |
|---|---|---|
| GET | `/radar/signals` | List trade signals |
| POST | `/radar/scan` | Trigger a radar scan |

### Intelligence
| Method | Endpoint | Description |
|---|---|---|
| GET | `/intelligence/status` | Mode, key status, usage stats |

Interactive API docs at **http://localhost:8000/docs**

---

## Security Model

- **Authentication:** PBKDF2-SHA256 (120k iterations), HS256 JWT (12h expiry)
- **Tenant isolation:** `org_id` scoping on all queries
- **Rate limiting:** login, signup, password reset endpoints
- **Partner access:** shared workspace only — AI findings, risk, HS, compliance are broker-private
- **Production guard:** server refuses to start with default secrets when `ENVIRONMENT=production`
- **Email tokens:** single-use, never usable as sessions
