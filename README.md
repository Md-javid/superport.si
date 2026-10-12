# SuperPort: Intelligence for Global Trade

**An AI trade operations platform. Customs brokers, forwarders, importers and exporters share one workspace where every AI finding comes with a source you can click.**

SuperPort turns the three documents every shipment needs into a reviewed, clearance-ready file, then keeps everyone in the loop: shared checklist, discussion, timeline, ETA, a Control Tower for exceptions, and a Copilot that answers questions from the shipment's own documents with citations. A human approves every important decision.

> Prototype. It never files anything with a customs authority. The risk score is an internal estimate, not a customs decision. HS codes, rules and prices are signals to verify. Demo data is fictional and labelled.

## Powered by SerpApi
SerpApi is the evidence engine. Four Google surfaces become structured, citable data:

| SerpApi | SuperPort feature |
|---|---|
| Google Search | HS code evidence, destination import rules (cited checklist), tariff pages |
| Google Shopping | Live market price check against the invoice unit price |
| Google Maps | Does the importer or exporter have a real business listing? |
| Google News | Adverse-news screening and the **Trade Signal Radar** (port strikes, congestion, carrier changes, tariff changes) that drives ETA and the Control Tower |

Every result is stored with its link, time and trust label, shown in the app, cached, budgeted per shipment and capped per day. See the in-app **SerpApi** page.

## Run it
**Fastest (no keys, sample data clearly labelled):**
```bash
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
INTELLIGENCE_MODE=fixtures uvicorn app.main:app --port 8000      # terminal 1
cd frontend && npm install && npm run dev                          # terminal 2 -> http://localhost:3000
```
**With Docker and PostgreSQL + pgvector:** `docker compose up --build`

**Live mode (real Gemini and SerpApi):** copy `backend/.env.example` to `backend/.env` and set:
```
INTELLIGENCE_MODE=live
GEMINI_API_KEY=...        # aistudio.google.com
SERPAPI_API_KEY=...       # serpapi.com
```
Leave the model names empty (they are auto-detected from your key). Then run `cd backend && python scripts/smoke_live.py`. Every line should say PASS. Never commit `.env`.

Log in with **Explore with the demo account** (broker). Use "See it as a partner" for the forwarder and importer views.

## What is in it
1. **Document AI:** invoice, packing list and bill of lading are read (text PDFs directly, scans with Gemini vision), cross-checked and editable.
2. **Evidence-backed HS code:** SerpApi sources, Gemini ranks, code validates; a code missing from the sources is flagged and capped.
3. **Market checks:** price, counterparties, cited import rules.
4. **Internal risk score** with every factor and its basis.
5. **Human gates:** HS approve/edit/reject, final approval (justification required when risk is high), full audit trail.
6. **Ecosystem:** companies, roles, invitations, shared checklist with reminders, discussion with @mentions, notifications, strict tenant isolation.
7. **Visibility:** shipment timeline, ISO 6346 container check, tracking behind a provider interface, rule-based ETA with listed drivers, Control Tower.
8. **Trade Signal Radar:** news to events to verified signals matched to your shipments.
9. **Copilot and RAG:** specialist agents (status/ETA, documents, compliance and risk, news, discussion) coordinated by one answerer that cites its evidence, plus a private Library of SOPs and rules. Vectors live in **PostgreSQL + pgvector** (HNSW, cosine) with a local fallback for development. Customer updates are drafted by AI and sent by a person.

## Architecture
```
frontend/  Next.js 14, TypeScript, Tailwind, Framer Motion
backend/   FastAPI, SQLAlchemy 2, PostgreSQL + pgvector (SQLite for development)
  app/intelligence   Gemini + SerpApi clients, cache, budgets, evidence, HS ranker, vision reader
  app/market         price, counterparty and rules checks
  app/radar          news -> events -> verification -> shipment matching
  app/rag            chunker, embedders, vector stores (pgvector / local), indexer
  app/copilot        specialist agents, coordinator, update drafts
  app/services       workflow gates, compliance, risk, timeline, ETA, control tower, access control
  app/tracking       ISO 6346 + provider interface
```

## Tests
`cd backend && pytest` runs 50 tests (49 without PostgreSQL). To include the real pgvector test: `TEST_PG_URL=postgresql+psycopg2://user:pass@localhost/db pytest`. Frontend: `npm run typecheck && npm run build`.
Gemini and SerpApi calls are tested against mock servers shaped like their documented responses; use `scripts/smoke_live.py` to verify with your keys.

## More documents
`SUBMISSION.md` (pitch, demo script, judge Q&A, roadmap) · `V2_README.md` (feature details and controls) · `HANDOVER.md` (for developers and AI agents).
