# ⚡ SuperPort — Quick Start Guide

Get SuperPort running locally in under 5 minutes.

---

## Prerequisites

| Tool | Version | Check |
|---|---|---|
| Python | 3.12+ | `python --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |
| Docker *(optional)* | 20+ | `docker --version` |

## 1. Get Your API Keys

### SerpApi (Required for live intelligence)

1. Sign up at **[serpapi.com](https://serpapi.com)**
2. Go to [Dashboard](https://serpapi.com/dashboard) → copy your API key
3. Free tier: **100 searches/month** — enough for several full demo shipments

### Gemini (Required for document reading + AI reasoning)

1. Go to **[aistudio.google.com](https://aistudio.google.com)**
2. Click "Get API Key" → create a key
3. Free tier available — sufficient for development and demos

---

## 2. Setup

### Option A — Local Development (SQLite)

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/superport.git
cd superport

# --- Backend ---
cd backend
python -m venv .venv

# Activate virtual environment
# Linux / macOS:
source .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
```

Edit `backend/.env` — set these three values:

```env
INTELLIGENCE_MODE=live
GEMINI_API_KEY=your-gemini-key-here
SERPAPI_API_KEY=your-serpapi-key-here
```

```bash
# Start the API server
uvicorn app.main:app --reload --port 8000
```

In a **new terminal**:

```bash
# --- Frontend ---
cd frontend
npm install
npm run dev
```

### Option B — Docker Compose

```bash
cd superport
cp backend/.env.example backend/.env
# Edit backend/.env with your API keys (same as above)

docker compose up --build
```

---

## 3. Verify

### Smoke test (recommended first time)

```bash
cd backend
python scripts/smoke_live.py
```

This uses ~2 SerpApi searches and 3-4 Gemini calls. Every line should say **PASS**.

### Open the app

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |

---

## 4. Demo Walkthrough

### First login

Click **"Explore with the demo account"** on the login page.

- Demo credentials: `demo@superport.ai` / `superport-demo`
- Or register a new account (email verification link appears on-screen in dev mode)

### The full flow (5 minutes)

1. **Dashboard** — Shipments sorted by risk level. Click any shipment to dive in.

2. **Create a shipment** — Click **New Shipment** → **Load demo shipment** for pre-filled data.

3. **Upload documents** — Click **Use sample documents** (3 pre-built PDFs). Hit **Start AI Analysis**.
   - Watch the real-time progress: Uploading → Extracting → Validating → Cross-checking → Ready

4. **Data review** — Click any extracted value to edit it. The cross-check table highlights the intentional 3.6% weight discrepancy between the packing list and bill of lading.

5. **HS Code** — The SerpApi-powered recommendation shows:
   - Recommended code with confidence score
   - Web evidence with clickable source links
   - Alternative codes ranked by relevance
   - Approve, edit, or request re-analysis

6. **Compliance** — Click **Run checks** to trigger:
   - **Price check** (Google Shopping via SerpApi)
   - **Counterparty screening** (Google Maps + News via SerpApi)
   - **Import rules** (Google Search via SerpApi + Gemini)
   - Each result cites its sources

7. **Risk** — Six-factor score with data sources cited for each factor.

8. **Approval** — Approve or reject. High-risk shipments require a written justification.

9. **Summary** — Print-ready clearance file.

### Try the high-risk example

Open shipment **SP-2026-0006** — it has an under-valued invoice, container number mismatch, and different shipper spellings. See how the system catches every issue.

### Try the partner view

Sign out → Click **"Freight forwarder"** or **"Importer"** under "See it as a partner" to experience the shared workspace.

---

## 5. Running Without API Keys

Set `INTELLIGENCE_MODE=fixtures` in your `.env` to see the full UI with sample data — no API keys needed. Great for UI development and demos without spending credits.

| Mode | API Keys Needed | Behaviour |
|---|---|---|
| `off` | None | v1 rule-based logic only |
| `fixtures` | None | Sample web evidence in UI (labelled) |
| `live` | SerpApi + Gemini | Full AI intelligence pipeline |

---

## 6. Running Tests

```bash
# Backend (39 tests, uses mock servers — no API keys needed)
cd backend
pip install -r requirements-dev.txt
pytest

# Frontend (type-checking + production build)
cd frontend
npm run typecheck
npm run build
```

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `ALLOW_SYNTHETIC_EXTRACTION` validation error | Leave the field empty or remove it from `.env` |
| Gemini model not found | Leave `GEMINI_MODEL_FAST` and `GEMINI_MODEL_PRO` empty — auto-detection picks the right model |
| SerpApi 429 error | You've hit the daily cap. Wait 24h or increase `SERPAPI_DAILY_CAP` |
| Port 8000/3000 already in use | Kill existing processes or change ports in the configs |
| Docker build fails | Ensure Docker Desktop is running. Try `docker compose down -v` then rebuild |
| `ModuleNotFoundError` | Ensure your virtual environment is activated |
