# SuperPort: Intelligence layer, ecosystem and visibility (Milestones 1 to 7)

v2 adds real AI and live web evidence on top of v1. Nothing in v1 was removed. With `INTELLIGENCE_MODE=off` (the default) the app behaves exactly like v1.

## What is new
1. **Gemini reads scanned documents.** If a PDF has no clean text, or you upload a photo, Gemini extracts the fields. If nothing can read the file, the fields stay empty with a clear message. v2 never invents values in live mode.
2. **Evidence-backed HS codes.** SerpApi searches Google for the product, Gemini ranks the most likely codes using those sources, and our code checks the answer (valid format, valid chapter, does the code appear in the sources?). Every source is a clickable link with a trust label.
3. **Cost controls.** Responses are cached, each shipment has a search and call budget, and field edits or approvals never trigger paid calls. Only "confirm data" and "request re-analysis" do.
4. **Feedback capture.** Every correction and decision is saved as structured data for future model training.
5. **Intelligence panel** on the dashboard showing mode, which keys are set, and usage.

## Setup (10 minutes)
1. Get keys. Gemini: Google AI Studio (aistudio.google.com). SerpApi: serpapi.com (dashboard shows your key and free searches).
2. In `backend/`, copy `.env.example` to `.env` and set:
   ```
   INTELLIGENCE_MODE=live
   GEMINI_API_KEY=your-key
   SERPAPI_API_KEY=your-key
   ```
   Leave the model names empty. Google changes model names and restricts old ones for new keys, so v2 asks your key which models it can use and picks the newest Flash and Pro.
3. Never commit `.env` or paste keys in chat. If a key leaks, rotate it.
4. Check everything with your real keys (uses about 2 searches and 3 to 4 Gemini calls):
   ```
   cd backend
   python scripts/smoke_live.py
   python scripts/smoke_live.py --doc path/to/a/scanned_invoice.pdf   # optional: test document reading
   ```
   Every line should say PASS. If not, the message tells you what to fix.
5. Start the app as in README.md, create a shipment, upload documents, and confirm the data. The HS step now shows "Web evidence".

Upgrading a v1 database: tables and the new `is_demo` column are added automatically on start.

## Modes
| Mode | What happens |
|---|---|
| `off` | v1 behaviour. No external calls. |
| `fixtures` | Sample web evidence appears in the UI, clearly labelled "not real search results". For showing the interface without keys. |
| `live` | Real Gemini and SerpApi. Fabricated demo values are turned off. |

The 7 seeded shipments are marked "Demo" and always use the simulated engine, so they never spend API credits. Create your own shipment (the "Load demo shipment" button works) to see the live path.

## How the AI works here, in plain words
- **LLM (large language model):** software trained on huge amounts of text that can read and write. Gemini is one. It is good at reasoning, but it can state wrong things confidently.
- **Vision model:** the same kind of model that can also look at images and PDFs. We use it to read scanned invoices, replacing old-style OCR that only turns pixels into text without understanding.
- **Grounding:** forcing the AI to base answers on real sources. SerpApi fetches Google results, we give them to Gemini as numbered sources, and Gemini must cite them. Then our code checks whether the HS code actually appears in those sources. If it does not, the confidence is capped at 80 percent and the screen warns you.
- **Confidence:** a model's own certainty is unreliable. We cap Gemini's confidence on documents at 95 percent and lower it when a value is missing from the file's own text.
- **Why a human still approves:** web results and AI answers are signals, not truth. Every important step keeps its approve, edit, reject gate.
- **Deep learning, your data advantage:** deep learning means models that learn patterns from examples. Gemini is already one. To build your own, you need examples. Every time a broker corrects a field or HS code, v2 stores the AI value, the human value and the context in the `feedback_events` table. In later milestones this becomes training data for: embeddings (turning products and company names into numbers so similar ones match), anomaly detection (learning what a normal price looks like), and a classifier fine-tuned on your users' corrected HS codes. Those models are not in this milestone because they need real data first. Make sure your terms get customer consent to use this data.

## Cost controls
| Control | Setting | Default |
|---|---|---|
| Response cache | `CACHE_TTL_HOURS` | 72 |
| SerpApi searches per shipment | `SERPAPI_BUDGET_PER_SHIPMENT` | 12 |
| Gemini calls per shipment | `GEMINI_BUDGET_PER_SHIPMENT` | 20 |
| HS classification | only on "Confirm data" and "Request re-analysis" | about 2 searches + 1 Gemini call |
| Document reading | only for files with no clean text | 1 Gemini call per file |
| Models | Flash for reading, Pro for HS ranking | change in `.env` |

The dashboard shows live calls and cache hits for the last 30 days. Check current prices and free-tier limits on both providers' pages before you launch.

## Privacy
- SerpApi receives the product description and destination in search queries. No company names are sent in this milestone.
- Gemini receives scanned documents and product details. Check Google's terms for your plan: free tiers may allow prompts to be used to improve their products, so use a paid plan for real customer documents.

## What was tested
- 16 automated tests pass (8 from v1, 8 new). The new ones use mock servers that return responses shaped like the documented Gemini and SerpApi APIs. They verify caching, budgets, key hiding, grounding checks, validation, fallbacks, and that edits and approvals cost nothing.
- **Not tested against the live services.** I could not reach Gemini or SerpApi from my environment. Run `scripts/smoke_live.py` with your keys to confirm, and send me any failure output.
- The frontend type-checks and builds, and fixtures mode was verified end to end over HTTP. It has not been checked visually in a browser.

## Milestone 3: market checks (SerpApi is the main engine)
On the **Compliance** step, click **Run checks**. It uses about 7 SerpApi searches and 2 to 3 Gemini calls, and the results are cached.

| Check | SerpApi engine | What it does |
|---|---|---|
| Price check | Google Shopping | Compares the invoice unit price with live listings (Gemini removes accessories and multipacks, then outliers are trimmed). Shows the market range and the listings. Replaces the made-up price bands in the risk score. Only for invoices in USD. |
| Counterparties | Google Maps + Google News | Looks for a public business listing for the importer and exporter, and for fraud, seizure or sanctions news. Gemini decides whether an article is really about the same company. Only a clear match is called "Adverse". |
| Import rules | Google Search + Gemini | Finds the destination country's requirements for the HS code and writes a checklist. **Every item must cite a source; uncited items are discarded.** Replaces the demo catalog text. |

How it changes the rest of the app:
- Compliance shows a new "Counterparty check" item, and restrictions and certificates come from web sources with `[n]` citations.
- Risk uses the market price for "Value anomaly" and adds a sixth "Counterparty check" factor only when real data exists. Each factor shows its basis.
- Adverse news makes compliance "action required", so approval needs a written justification. A person still decides.
- This is **not** sanctions screening. It uses public web signals only. Similar company names are common, so a person must confirm any match.
- Demo shipments and fixtures mode show clearly labelled **sample data** and spend no credits.

## Milestone 4: Trade Signal Radar
Open **Radar** in the sidebar and click **Scan now** (or set `RADAR_INTERVAL_MINUTES` for automatic scans).

1. **Watch list:** ports, countries and products from your active shipments.
2. **Search:** SerpApi Google News (past week by default), up to `RADAR_MAX_QUERIES` searches per scan.
3. **Extract events:** Gemini turns articles into events (strike, congestion, weather, tariff change, regulation, closure). Events with no real article behind them are discarded. Without Gemini a transparent keyword method is used and labelled.
4. **Verify:** confidence comes from how many independent publishers report it: 1 source = 35%, 2 = 60%, 3 or more = 80%, plus 10% for an official source, never above 90%. Labels: Unverified, Corroborated, Official source found.
5. **Match:** each signal is linked to the shipments it may affect (same discharge port, a rule change in the origin or destination country for that product, or a major regional event).
6. **Human review:** Acknowledge or Dismiss with a note. This is written to the shipment's audit trail and saved as feedback data.

A signal never changes a shipment's stage, risk score or approval. It is context for a person. This follows your rule: SERP data is a signal, not truth.

## Milestone 5: the ecosystem foundation
SuperPort is no longer only for one broker. Companies now have their own accounts and invite the other parties into a shared shipment workspace.

**Accounts and companies**
- Sign up with your company (broker, forwarder, importer or exporter). Email confirmation and password reset work end to end, and links are single-use. In development with no email service, the link is shown on screen ("demo mode") instead of an inbox.
- A company has admins and members. Admins invite teammates from the **Team** page.
- Companies never see each other's data. Every list, workspace, document, radar signal and review is scoped to the company.

**Shared workspace per shipment** (button "Partner workspace" on the broker's shipment)
- **Invitations:** the broker invites a forwarder, importer or exporter by email. They create an account (or accept with an existing one) and land in the shipment.
- **Document checklist:** invoice, packing list, bill of lading, certificate of origin and insurance, each assigned to the party that must provide it. Anyone can see what is missing. The owner can add requests and send reminders (in-app and email, at most once an hour per item).
- **Core documents feed the AI:** when the exporter uploads the invoice or the forwarder uploads the bill of lading, it goes straight into the broker's extraction pipeline. Uploads are locked once classification starts, so the AI never works from changed documents.
- **Discussion:** one thread per shipment with @mentions, replacing email and WhatsApp.
- **Notifications:** a bell with unread count for comments, mentions, uploads, reminders and new participants.
- **Activity feed:** a safe, shared history (uploads, joins, approvals).

**What partners cannot see:** the AI findings, risk score, HS code, compliance results and internal notes. Partners get the workspace only; the broker's AI workflow stays private.

**Try it in 30 seconds (demo mode):** on the login page click "Explore with the demo account" (the broker), then sign out and use "Freight forwarder" or "Importer" under "See it as a partner". Shipment SP-2026-0001 has a shared discussion, and its Certificate of Origin is missing.

**Security added:** password rules, rate limits on login, sign-up and reset, email tokens that can never be used as a session, no account enumeration on password reset, and the server refuses to start in production with unsafe defaults (`ENVIRONMENT=production`).

**Not in this milestone (moved to the hardening milestone):** Google login (needs OAuth credentials), Alembic migrations (older databases are upgraded automatically by an additive upgrade step), cloud file storage (files stay on local disk), and live testing of the Resend email integration.

## Milestone 6: visibility and the Control Tower
**Shipment timeline** (top of the shared workspace, visible to every participant): factory pickup, origin port, loaded, in transit, destination port, customs clearance, warehouse delivery.
- The right party updates each step: the exporter or forwarder for pickup, the forwarder for sea legs, the forwarder or importer for delivery. The broker can update any step.
- Customs clearance follows the broker's workflow automatically. The broker can record a delay or a hold, but must give a reason, and it can never be marked "done" by hand.
- Every update is logged and notifies the other participants.

**Container tracking**
- Container numbers are checked with the real ISO 6346 check digit, so a typo is caught. Demo shipments use fictional numbers and show a note.
- Tracking sits behind a provider interface (`app/tracking/providers.py`). The default `sample` provider returns demo data and is always labelled "Sample data, not the real position". Tracking events fill in timeline steps but never overwrite a step a person set by hand.
- **No real tracking provider is connected.** To go live, pick a tracking API (this needs a paid contract) and add a small adapter. Until then the timeline works by hand.

**ETA estimate** (simple, transparent rules, not machine learning)
- Baseline = the carrier ETA from tracking, or the planned arrival date someone entered. With neither, it says so instead of inventing an ETA.
- Delays are added from open Radar signals that touch the shipment (weighted by how well confirmed each is) and from missing required documents. Each driver is listed with its days. You get a likely range, a confidence and a delay-risk level.
- It will become a learned model once enough shipment history exists.

**Control Tower** (new sidebar item): a board of only the shipments that need attention, worst first. Categories: customs hold, port event, vessel delay, missing document, needs review (broker only), cleared. Partners see only their shared shipments and never the broker's internal review flags.

**Radar 2.0:** new carrier events (blank sailings, schedule changes, service suspensions) matched to shipments by carrier, plus dedicated weather-warning searches per port. Queries are prioritised so a small budget still covers ports, carriers, weather and rule changes. A structured weather feed is a possible later addition.

**Try it:** log in as the demo broker, open **Control Tower**, then open a shipment's **Partner workspace**. SP-2026-0006 has a seeded customs delay, and every demo shipment has the missing Certificate of Origin. Click **Scan now** on the Radar to see carrier and port signals feed the ETA.

## Milestone 7: Copilot, RAG and the vector database
**Vector database:** PostgreSQL with the **pgvector** extension. Passages are stored in `rag_chunks`, vectors in `rag_vectors` (cosine distance, HNSW index). With SQLite (development) a local fallback store is used, so everything still runs. The status card on the **Library** page shows which one is active. Docker Compose now uses the `pgvector/pgvector:pg16` image.

**Embeddings:** Gemini (model auto-detected from your key, 768 dimensions by default). Without a key a local keyword embedder is used and clearly labelled "Keyword matching: it matches words, not meaning". Each passage remembers which embedder made it, and searches never mix embedders. If you switch, the Library offers a one-click re-index.

**What is indexed:** each shipment's extracted fields and document text, the discussion, and your Library of SOPs, regulations and rate sheets (PDF with text, TXT, MD, CSV). Shipments are indexed only when their content changes, so nothing is re-embedded needlessly.

**Isolation (enforced inside the database query):** a company never retrieves another company's passages. Partners only retrieve the discussion and the documents assigned to their role, and never the broker's library.

**Specialist agents and the Coordinator:**
| Agent | Looks at |
|---|---|
| Status and ETA | timeline, tracking, ETA drivers, checklist |
| Document (RAG) | document passages, discussion, Library |
| Compliance and Risk (broker only) | HS code, compliance items, internal risk |
| News and Signals | Radar signals that touch the shipment |
| Discussion | the recent conversation |
| Communication | drafts updates for a person to send |
| Coordinator | plans which specialists to consult, merges their evidence, answers only from it |

The Copilot panel on every workspace shows the answer, clickable citations [E1], which agents were consulted and whether the answer is grounded. Invalid citations are removed. If the evidence is missing, it says what is missing. Without Gemini it lists the findings directly.

**Customer updates:** the Communication agent drafts an email from the shipment facts. You edit it and press send. Nothing is sent automatically.

## Cost and safety controls (all milestones)
| Control | Setting | Default |
|---|---|---|
| Daily SerpApi cap, whole app | `SERPAPI_DAILY_CAP` | 80 |
| SerpApi searches per shipment | `SERPAPI_BUDGET_PER_SHIPMENT` | 20 |
| Radar searches per scan | `RADAR_MAX_QUERIES` | 6 |
| Cache | `CACHE_TTL_HOURS` | 72 |
| Radar automatic scans | `RADAR_INTERVAL_MINUTES` | 0 (manual) |

## What was tested (updated)
- 50 automated tests pass (including real PostgreSQL + pgvector, tenant and role isolation, citation validation, incremental indexing, drafts): 8 from v1, 8 for milestones 1 and 2, 7 for milestones 3 and 4, 6 for milestone 6 (ISO 6346, timeline permissions, tracking and ETA, Control Tower, carrier events), 10 for milestone 5 (sign-up, verification, reset, rate limits, tenant isolation, invitations, partner permissions, checklist, comments and notifications, reminders, locking, team, email request shape, production guard). They use mock servers shaped like the documented SerpApi and Gemini responses. They cover caching, the daily cap, price statistics, counterparty adjudication, uncited rules being dropped, risk and compliance changes, de-duplication of radar signals, matching, and the keyword fallback.
- **Still not tested against the live services** (I cannot reach them from my environment). `scripts/smoke_live.py` now also checks the price check, counterparty check, rules lookup, news search and event extraction with your keys.
- The frontend builds and type-checks, and the sample-data mode was verified end to end over HTTP. It has not been checked visually in a browser.

## Known limits
- Google Shopping prices are fetched for the US market in USD, so the price check only runs for USD invoices. Retail is higher than import pricing, so the comparison band is wide.
- A company missing from Google Maps is only a weak signal and does not raise the risk much.
- News matching relies on port and country names. Unusual spellings can be missed.
- No push notifications yet. The Radar shows signals when you open it.

## Next
8. Intelligence and business: supplier profiles, rate intelligence, learning from corrections, billing, Google login, Alembic, cloud storage, end-to-end tests.
