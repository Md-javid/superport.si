# 🚢 SuperPort: Autonomous Trade Intelligence & Customs Verification

[![Next.js 14](https://img.shields.io/badge/Next.js-14.2-black?style=flat-square&logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.12+-blue?style=flat-square&logo=python)](https://python.org/)
[![SerpApi](https://img.shields.io/badge/Search%20Engine-SerpApi-blueviolet?style=flat-square)](https://serpapi.com/)
[![Google Gemini](https://img.shields.io/badge/AI%20Engine-Google%20Gemini-4285F4?style=flat-square&logo=google)](https://aistudio.google.com/)
[![PostgreSQL + pgvector](https://img.shields.io/badge/Vector%20Store-pgvector%20%2F%20Local-336791?style=flat-square&logo=postgresql)](https://github.com/pgvector/pgvector)
[![Tests Passing](https://img.shields.io/badge/Tests-50%20Passed-success?style=flat-square)](https://github.com/Md-javid/superport.si)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

> **An enterprise AI trade operations platform. Customs brokers, freight forwarders, importers, and exporters collaborate in a single shared workspace where every finding is anchored in real-world ground truth.**

SuperPort ingests trade documents (Commercial Invoices, Packing Lists, Bills of Lading), runs multi-document extraction, and cross-references them against live web signals: official tariff gazettes, wholesale market price listings, physical business registries, and port disruption news. Every recommendation features an interactive, clickable citation—giving human operators the confidence to approve filings fast without hallucination risks.

---

## ⚡ Why SerpApi is the Heart of SuperPort

Global supply chains stall when customs declarations are filed with outdated tariff codes, suspicious price variances, unverified counterparties, or blind ignorance of port delays. 

SuperPort integrates **SerpApi** as its **Horizon Sensory Grid™**—transforming four distinct Google surfaces into structured, citable trade evidence:

```
                            ┌──────────────────────────────────────────────┐
                            │      SUPERPORT HORIZON SENSORY GRID          │
                            │        (Orchestrated via SerpApi)            │
                            └──────────────────────┬───────────────────────┘
                                                   │
        ┌──────────────────────┬───────────────────┴───┬──────────────────────┬──────────────────────┐
        ▼                      ▼                       ▼                      ▼                      ▼
┌────────────────┐     ┌────────────────┐      ┌────────────────┐     ┌────────────────┐     ┌────────────────┐
│ Google Search  │     │ Google Shopping│      │  Google Maps   │     │  Google News   │     │ Google Search  │
│ (HS Code WCO)  │     │ (Price Parity) │      │ (Counterparty) │     │ (Signal Radar) │     │ (Import Rules) │
└───────┬────────┘     └───────┬────────┘      └───────┬────────┘     └───────┬────────┘     └───────┬────────┘
        │                      │                       │                      │                      │
        ▼                      ▼                       ▼                      ▼                      ▼
  Official Tariff        Wholesale Price        Physical Business       Real-Time Port        Destination Rules
  Gazette Evidence       Distribution           Listing Screening      Congestion Alerts      Citation Checklist
```

### 1. Google Search — Evidence-Backed HS Classification & Import Rules
- **Tariff Grounding:** Queries global customs gazettes and WCO schedules to recommend 6-digit and 8-digit Harmonized System (HS) codes. Gemini ranks the candidates, but our verification code validates that the code actually appears in the official web sources. If a code is not found in the search evidence, confidence is strictly capped.
- **Import Rules Checklist:** Automatically gathers required certificates (e.g., Certificate of Origin, EPR certifications, dangerous goods compliance) for the specific destination port. Every single requirement cites its source URL; uncited items are discarded.

### 2. Google Shopping — Anti-Fraud Price Parity Check
- **Trade-Based Anti-Undervaluation:** Compares declared commercial invoice unit prices against live e-commerce and wholesale listings.
- **Statistical Filtering:** Outliers and mismatched accessories (e.g., cables instead of battery packs) are eliminated. Calculates IQR ranges (P25 to P75) to verify if declared invoice pricing is within fair market range (e.g., 102% of median listing price).

### 3. Google Maps — Geospatial Counterparty Screening
- **Physical Entity Verification:** Searches physical location listings for overseas exporters and local importers. Confirms operating status, category (e.g., verified manufacturing facility vs. residential mailbox), address validity, and geographical footprint.

### 4. Google News — Trade Signal Radar
- **Autonomous Disruption Surveillance:** Continuously scans global maritime ports (e.g., Chennai, Rotterdam, Singapore, Yantian) and carriers for adverse events: dockworker strikes, typhoon warnings, customs server outages, and canal bottlenecks.
- **Corroboration Confidence:** Multiple independent news sources boost event confidence (1 publisher = 40%, 2+ publishers = 60%+), directly feeding dynamic ETA drivers and raising alerts on the Control Tower.

---

## 🧠 Gemini Cognitive AI & Trade Copilot

* **Multimodal Vision Ingestion:** Reads scanned invoices, photos, and unformatted PDFs using Gemini Vision models, accurately preserving line items, gross weights, and container numbers.
* **Specialist Agent Squad:** Trade Copilot features 5 focused agents:
  1. `StatusAgent` — Workflow stage, milestones, and rule-based ETA drivers.
  2. `DocumentAgent` — RAG vector search across indexed bills of lading, invoices, and packing lists.
  3. `ComplianceAgent` — Discrepancy checks, missing required certificates, and HS code classifications.
  4. `NewsAgent` — Correlated adverse news events and port delay signals.
  5. `DiscussionAgent` — Multi-party internal broker and partner comments.
* **Grounded Answers with Citations:** Coordinated synthesis agent provides concise answers where every claim links to evidence cards (e.g., `[E1]`, `[E5]`). Clicking any citation opens the exact underlying document passage or news event.
* **Vector Store & RAG:** Embeddings generated via `gemini-embedding-2` (768 dimensions) stored in **PostgreSQL + pgvector** (HNSW index, cosine distance) with automatic fallback to a local vector store for zero-friction development.
* **Feedback Engine:** Every human correction to an HS code or extracted field is stored as structured training data in `feedback_events` to continuously improve accuracy.

---

## 🏛️ System Architecture

```
frontend/ (Next.js 14, TypeScript, Tailwind CSS, Framer Motion)
  ├── src/app/(app)/
  │   ├── dashboard/       Overview metrics, stage breakdown, live telemetry stats
  │   ├── control-tower/   Exception management and urgent trade blockers
  │   ├── shipments/       Shipment listings, stepper workflow, audit trail
  │   ├── radar/           Live port disruption feed and carrier impact matching
  │   ├── library/         Regulatory Knowledge Library with semantic vector search
  │   ├── serpapi/         Horizon Sensory Grid telemetry showcase & search inspection
  │   └── team/            Multi-tenant organization roles and invitations
  └── src/components/      High-polish UI primitives, ocean graphics, and Copilot drawer

backend/ (FastAPI, SQLAlchemy 2, SQLite / PostgreSQL + pgvector)
  ├── app/intelligence/    SerpApi client, Gemini client, cache, per-shipment budgets
  ├── app/market/          Google Shopping price check, Maps entity verification, rules
  ├── app/radar/           Port news extraction, disruption corroboration, shipment matching
  ├── app/rag/             Document chunker, gemini-embedding-2, pgvector / local vector store
  ├── app/copilot/         Specialist agent squad (Status, Docs, Compliance, News, Discussion)
  ├── app/services/        State machine workflow, 6-factor risk scoring, ETA estimator
  └── app/api/             Clean REST endpoints with JWT authentication and tenant isolation
```

---

## 🚀 Quick Start (Up in Under 3 Minutes)

### Prerequisites
- Python 3.12+
- Node.js 18+ & npm 9+
- Git

### 1. Clone & Set Up Backend

```bash
# Clone the repository
git clone https://github.com/Md-javid/superport.si.git
cd superport.si/backend

# Create and activate virtual environment
python -m venv .venv

# Windows (PowerShell):
.\.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the example environment configuration:
```bash
cp .env.example .env
```

Open `.env` and set your API keys:
```env
INTELLIGENCE_MODE=live
GEMINI_API_KEY=your_gemini_api_key       # From https://aistudio.google.com
SERPAPI_API_KEY=your_serpapi_api_key     # From https://serpapi.com
```

> **Zero-Key Mode:** To explore the UI without keys, simply set `INTELLIGENCE_MODE=fixtures`. The platform will display realistically labelled sample search telemetry without making paid calls.

### 3. Verify Live Setup
Run the built-in live smoke test:
```bash
python scripts/smoke_live.py
```
*Output will confirm authentication, SerpApi engines (Search, Shopping, Maps, News), Gemini Flash, and `gemini-embedding-2` vector similarity.*

### 4. Start the Application

**Terminal 1 — Backend:**
```bash
python -m uvicorn app.main:app --port 8000
```
*API docs available at: `http://localhost:8000/docs`*

**Terminal 2 — Frontend:**
```bash
cd ../frontend
npm install
npm run dev
```
*Web application available at: `http://localhost:3000` (or `http://localhost:3001` if port 3000 is occupied).*

---

## 🐳 Docker Deployment (PostgreSQL + pgvector)

To run the complete production stack with native pgvector:

```bash
docker compose up --build
```
This spins up:
- **Web:** Next.js on port `3000`
- **API:** FastAPI on port `8000`
- **Database:** PostgreSQL 16 with `pgvector` extension enabled on port `5432`

---

## 🧪 Automated Test Suite

SuperPort includes 50 comprehensive unit and integration tests covering workflow state machines, role-based isolation, prompt injection safety, caching, search budgeting, and vector similarity:

```bash
cd backend
pytest
```
```text
======================= 49 passed, 1 skipped in 4.82s =======================
```
*(The 1 skipped test runs automatically when `TEST_PG_URL` points to an active PostgreSQL instance with pgvector).*

To validate frontend code and styling:
```bash
cd frontend
npm run typecheck
npm run build
```

---

## 🔒 Security, Privacy & Cost Controls

1. **Strict Tenant & Role Isolation:** Importers, brokers, and forwarders access shared shipments through cryptographically isolated workspace permissions. Partners cannot access internal broker compliance notes.
2. **Search Budgets & Circuit Breakers:**
   - 72-hour automated response cache (`CACHE_TTL_HOURS=72`).
   - Hard cap of 12 searches per shipment (`SERPAPI_BUDGET_PER_SHIPMENT=12`).
   - Daily organization search cap (`SERPAPI_DAILY_CAP=80`).
   - Human edits and approvals **never** trigger paid external API calls.
3. **Data Minimization:** SerpApi search queries transmit generic product descriptions and destination ports—never confidential proprietary formulas or personal identifiers.
4. **Deterministic Human Sovereign Gates:** SuperPort never files declarations automatically. Customs filings require explicit human review and cryptographic audit logging.

---

## 📄 Documentation

- [Architecture Reference](ARCHITECTURE.md) — Module architecture, database schemas, and data pipelines.
- [Quick Start Guide](QUICKSTART.md) — Step-by-step local developer setup instructions.
- [License](LICENSE) — MIT License.
