<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Next.js_14-000000?style=for-the-badge&logo=nextdotjs&logoColor=white" alt="Next.js" />
  <img src="https://img.shields.io/badge/SerpApi-4285F4?style=for-the-badge&logo=google&logoColor=white" alt="SerpApi" />
  <img src="https://img.shields.io/badge/Gemini-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white" alt="Gemini" />
  <img src="https://img.shields.io/badge/Tailwind_CSS-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white" alt="Tailwind" />
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL" />
</p>

# 🚢 SuperPort — Intelligence for Global Trade

> **AI-powered customs clearance copilot** that turns raw trade documents into reviewed, clearance-ready shipment files — with real-time web evidence from **SerpApi** and intelligent document understanding from **Gemini**.

SuperPort automates the most error-prone part of international trade: preparing a shipment for customs. Upload your commercial invoice, packing list, and bill of lading — the system extracts data, cross-checks documents, recommends HS tariff codes backed by live web evidence, runs compliance checks, and scores risk. A human approves every critical decision.

---

## ⚡ Why SerpApi Is the Core Intelligence Engine

SuperPort is built around **SerpApi** as its primary source of real-world trade intelligence. Every major decision in the customs workflow is grounded in live web data retrieved through SerpApi's search engines:

| Feature | SerpApi Engine | What It Does |
|---|---|---|
| 🏷️ **HS Code Classification** | Google Search | Searches for the product description + destination to find tariff code references. Gemini ranks candidates using these sources, and our code **verifies every code actually appears in the cited sources**. Ungrounded codes are flagged. |
| 💰 **Price Verification** | Google Shopping | Compares invoice unit prices against live market listings. Outlier detection identifies potential under/over-valuation — a key customs red flag. |
| 🏢 **Counterparty Screening** | Google Maps + Google News | Verifies importers and exporters have real business listings. Scans news for fraud, seizure, or sanctions mentions with AI-powered adjudication to prevent false positives. |
| 📋 **Import Rules Lookup** | Google Search + Gemini | Finds the destination country's requirements for the HS code. **Every rule must cite a source — uncited items are automatically discarded.** |
| 📡 **Trade Signal Radar** | Google News | Monitors for port strikes, vessel delays, tariff changes, and regulatory updates. Signals are matched to active shipments and confidence-scored by source corroboration. |
| 🚢 **Carrier Intelligence** | Google News | Detects blank sailings, schedule changes, and service suspensions affecting shipments. |

### The SerpApi Advantage

- **Real-time grounding** — AI recommendations cite live web sources, not stale databases
- **Multi-engine intelligence** — Google Search, Shopping, Maps, and News in a unified pipeline
- **Trust verification** — every claim is traced to its source with clickable links
- **Cost-controlled** — response caching (72h default), per-shipment budgets, and daily caps prevent runaway costs

---

## 🎯 Key Features

- **AI Document Extraction** — Gemini reads scanned invoices, packing lists, and bills of lading (falls back to `pypdf` for text-based PDFs)
- **Cross-Document Verification** — automated checks for weight, quantity, party name, and arithmetic inconsistencies across all three documents
- **Evidence-Backed HS Codes** — SerpApi + Gemini pipeline with grounding verification, alternatives, and confidence scoring
- **Market Price Check** — invoice values compared against Google Shopping listings
- **Counterparty Due Diligence** — business verification via Google Maps, adverse news screening via Google News
- **Destination-Aware Compliance** — import rules sourced from the web with mandatory citations
- **Explainable Risk Scoring** — six weighted factors, each citing its data source
- **Trade Signal Radar** — real-time monitoring of port events, tariff changes, and carrier disruptions
- **Human-in-the-Loop** — server-enforced approval gates at every critical decision point
- **Multi-Tenant Ecosystem** — organisations, roles, shared workspaces, partner invitations, document checklists
- **Shipment Timeline & Control Tower** — end-to-end visibility with container tracking and ETA estimation
- **Full Audit Trail** — every AI recommendation and human decision is logged

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+** and **Node.js 18+**
- API Keys: **[SerpApi](https://serpapi.com)** (free tier: 100 searches/month) and **[Gemini](https://aistudio.google.com)** (free tier available)

### Option A — Local Development (SQLite, ~3 minutes)

```bash
# 1. Clone and enter
git clone https://github.com/YOUR_USERNAME/superport.git
cd superport

# 2. Backend
cd backend
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env
# Edit .env → set your GEMINI_API_KEY and SERPAPI_API_KEY (see Configuration below)
uvicorn app.main:app --reload --port 8000

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000** → Click **"Explore with the demo account"**

### Option B — Docker Compose (PostgreSQL)

```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your API keys

docker compose up --build
```

Open **http://localhost:3000**

> 📖 See [QUICKSTART.md](QUICKSTART.md) for the full setup guide, demo walkthrough, and troubleshooting.

---

## 🔑 Configuration

All configuration lives in `backend/.env`. Copy from `backend/.env.example` to get started.

### Required Keys (for full intelligence)

| Variable | Source | Purpose |
|---|---|---|
| `SERPAPI_API_KEY` | [serpapi.com/dashboard](https://serpapi.com/dashboard) | **Core search engine** — HS codes, price checks, counterparty screening, compliance rules, trade signals |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) | Document reading (vision), HS code ranking, news adjudication |

### Intelligence Modes

| `INTELLIGENCE_MODE` | Behaviour |
|---|---|
| `off` | No external API calls. Rule-based demo logic only. |
| `fixtures` | Sample web evidence displayed in UI (no keys needed). Great for demos. |
| `live` | **Full power.** Real SerpApi searches + Gemini reasoning. |

### Cost Controls

| Setting | Default | Description |
|---|---|---|
| `SERPAPI_BUDGET_PER_SHIPMENT` | `20` | Max searches per shipment |
| `SERPAPI_DAILY_CAP` | `80` | Hard daily limit across all shipments |
| `GEMINI_BUDGET_PER_SHIPMENT` | `20` | Max Gemini calls per shipment |
| `CACHE_TTL_HOURS` | `72` | Response cache lifetime |
| `RADAR_MAX_QUERIES` | `6` | Searches per Radar scan |

> 💡 The free SerpApi tier (100 searches/month) is enough to demo several shipments end-to-end.

---

## 🧪 Verify Your Setup

```bash
cd backend
python scripts/smoke_live.py
```

This runs a quick integration check (~2 SerpApi searches + 3-4 Gemini calls) and reports PASS/FAIL for each capability.

---

## 📸 Demo Walkthrough

1. **Login** → Click "Explore with the demo account" (or sign up)
2. **Dashboard** → See shipments ranked by risk, highest first
3. **Create Shipment** → Click "Load demo shipment" for pre-filled data
4. **Documents** → Click "Use sample documents" → Start AI analysis
5. **Data Review** → Edit any extracted field; cross-check table highlights discrepancies
6. **HS Code** → View SerpApi-sourced web evidence, approve/edit/reject the recommendation
7. **Compliance** → Click "Run checks" for price verification, counterparty screening, and import rules
8. **Risk** → See the six-factor breakdown with data sources cited
9. **Radar** → Click "Scan now" to monitor trade signals
10. **Approval** → Approve (high-risk shipments require written justification)
11. **Summary** → Print-ready clearance file with full audit trail

> Seeded shipment **SP-2026-0006** is a deliberately high-risk example with under-valued invoice, container mismatch, and inconsistent shipper names.

---

## 🏗️ Architecture

```
superport/
├── backend/                    FastAPI + SQLAlchemy + Python 3.12
│   ├── app/
│   │   ├── api/                REST routers (auth, shipments, dashboard, radar, tracking)
│   │   ├── services/           Business logic (workflow, extraction, HS, compliance, risk)
│   │   ├── intelligence/       Gemini client, SerpApi client, response cache, evidence pipeline
│   │   ├── market/             Price check, counterparty check, cited rules lookup
│   │   ├── radar/              Trade Signal Radar (news, events, matching, verification)
│   │   ├── tracking/           Container tracking provider interface
│   │   ├── agents/             Agent base, registry (Document, Customs, Compliance, Risk)
│   │   ├── ai/                 Provider interfaces (OCR, LLM) + registry
│   │   ├── email/              Transactional email (Resend or console fallback)
│   │   └── core/               Config, security, database
│   ├── tests/                  39 automated tests (mock SerpApi + Gemini responses)
│   └── scripts/                smoke_live.py, make_sample_docs.py
│
├── frontend/                   Next.js 14 + TypeScript + Tailwind CSS + Framer Motion
│   └── src/
│       ├── app/                Pages (login, dashboard, shipments, radar, control tower)
│       ├── components/         UI primitives, brand, layout, shipment workflow steps
│       └── lib/                Typed API client, auth, utilities
│
└── docker-compose.yml          PostgreSQL + API + Web (production-like setup)
```

> 📖 See [ARCHITECTURE.md](ARCHITECTURE.md) for the full technical deep-dive.

---

## 🧪 Testing

```bash
# Backend (39 tests)
cd backend
pip install -r requirements-dev.txt
pytest

# Frontend (type-check + build)
cd frontend
npm run typecheck
npm run build
```

---

## ⚠️ Disclaimers

- SuperPort **does not submit anything to any customs authority**
- The risk score is an **internal estimate for review prioritisation**, not a government channel prediction
- Counterparty screening uses **public web signals only** — it is not sanctions screening
- Web-sourced data is a **signal, not truth** — every critical decision requires human approval
- This is a prototype — not legal advice and not validated by a licensed customs broker

---

## 📄 License

MIT — see [LICENSE](LICENSE)

---

<p align="center">
  <b>Built with 🌊 SerpApi + Gemini for real-time trade intelligence</b><br/>
  <sub>SuperPort — because global trade deserves better than spreadsheets</sub>
</p>
