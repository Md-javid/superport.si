# SuperPort: submission kit

## One line
**SuperPort turns the open web into cited evidence for customs and trade teams, so every flag has a source you can click and a human makes the call.**

## The 20-second pitch
"Getting cargo through customs means checking a dozen facts that live on the web: tariff pages, market prices, company records, port news. Today people do it by hand and by WhatsApp. SuperPort uses SerpApi to fetch that evidence, Gemini to reason over it, and a shared workspace so brokers, forwarders and importers see the same shipment. Every finding is cited. Every decision is human."

## The problem
- A wrong HS code, a mismatched weight or a missing certificate means fines, holds and storage fees.
- The answers exist online, but nobody has time to search, compare and write them down for every shipment.
- Four companies touch each shipment and coordinate over email and WhatsApp.

## Why SerpApi is the heart of it (say this slowly)
1. **Evidence, not opinions.** SerpApi turns Google results into structured data. SuperPort stores each result with link, time and trust label (official, reference, general web). The AI is never allowed to answer without a source.
2. **Four Google surfaces, five features, one pipeline:**
   - *Google Search* gives HS evidence and a cited list of import rules for the destination.
   - *Google Shopping* gives a live market price check: "the invoice says 46 dollars, the market says 400."
   - *Google Maps* checks the importer and exporter exist.
   - *Google News* powers the Trade Signal Radar and adverse-news screening.
   - Radar signals then feed the ETA estimate, the Control Tower and the Copilot's answers.
3. **Verified, not trusted.** Gemini's answers are checked by code: invalid HS codes are dropped, a code not found in the sources is flagged and capped, rules without a citation are discarded, news is only "adverse" when the AI judges it is the same company, and signals show how many independent publishers confirm them.
4. **Built for cost.** Cache, per-shipment budgets, a daily cap and a visible usage page. It is designed to run as a real SaaS, not a demo.
5. **One search feeds many places.** A single port-news search updates the Radar, shifts the ETA of every affected shipment, raises an exception on the Control Tower and shows up in the Copilot's answer with its link.

## The 3-minute demo script
| Time | Do | Say |
|---|---|---|
| 0:00 | Login page, click the demo account | "SuperPort for a customs broker." |
| 0:15 | Dashboard, then **Control Tower** | "Most shipments are boring. This shows only what needs attention." |
| 0:35 | Open SP-2026-0001, **Partner workspace** | "Same shipment, shared with the forwarder and importer. One checklist, one thread." |
| 0:55 | **Copilot**: ask "Why is this shipment delayed?" | "It consults specialist agents and cites every claim. Click E3: the evidence." |
| 1:20 | Back to the AI workflow, **HS code** step | "SerpApi found these sources, Gemini ranked, our code checked. Official sources are labelled." |
| 1:50 | **Compliance**, click Run checks | "Live Google Shopping prices, Maps and News for the companies, and a cited rules list." |
| 2:20 | **Radar**, click Scan now | "News becomes signals with confidence. Two publishers means 60 percent. It touches these shipments." |
| 2:40 | **SerpApi** page | "Four Google surfaces, every result stored with its source." |
| 2:55 | Sign out, sign in as the forwarder | "The partner sees the workspace but never the broker's AI findings." |

Run the demo in `live` mode with keys. If the network fails, `fixtures` mode still works and labels every sample.

## Judge Q&A
- **Is the AI hallucinating?** Answers are generated only from numbered evidence and every citation is validated. If the evidence is missing, it says so.
- **Is this legal advice or a customs decision?** No. It never files anything. The risk score is internal. A human approves.
- **Why would a broker pay?** It removes data entry and lookups, catches mistakes before they cost money, and a shared workspace replaces email threads.
- **Is customer data safe?** Strict per-company isolation (tested), rate limits, audit trail, and the vector search is filtered per company and per role in the database query itself.
- **What if SerpApi or Gemini is down?** Each step degrades visibly to rules with a reason on screen.
- **What is real and what is simulated?** Real: workflow, approvals, isolation, RAG with pgvector, all SerpApi and Gemini integrations. Simulated and labelled: demo shipments, sample tracking data. Not built: real tracking provider, customs filing.

## Honest limits (say them before they are asked)
Tracking is sample data until a provider is connected. The price check works for USD invoices. Company checks are public-web signals, not sanctions screening. Live Gemini and SerpApi calls are tested with mock servers and a one-command live check.

## Business
- **Customer:** small and mid-size customs brokers and freight forwarders first (the pain is daily and they buy quickly), then importers.
- **Pricing ideas (to validate):** per seat plus per shipment, with the Radar and Library as add-ons.
- **Moat:** every correction a broker makes is saved as structured feedback (with consent) to train HS and price models. The network of brokers, forwarders and importers inside shared shipments grows more valuable with every invitation.

## Roadmap
**Next 30 days (launch readiness):** Google login, Alembic migrations, cloud file storage, billing and plans, end-to-end browser tests, monitoring, a real tracking provider adapter.
**Next 90 days (more SerpApi):** Google Finance for exchange rates and duty estimates, Google Lens to identify products from photos, Google Trends for demand signals, Google Images and Patents for counterfeit and brand checks, supplier trust profiles built from Maps, News and platform history, a structured weather feed.
**6 to 12 months (learning):** fine-tune HS retrieval and price anomaly models on saved corrections, learned ETA from shipment history, inbound email and WhatsApp ingestion, multi-language, ICEGATE and other filing integrations after licensing and legal review.

## Tags for the submission form
SerpApi, Gemini, RAG, pgvector, PostgreSQL, multi-agent, FastAPI, Next.js, B2B SaaS, logistics, customs, trade compliance.

## Before you submit (10-minute checklist)
1. Add both keys to `backend/.env`, set `INTELLIGENCE_MODE=live`, run `python scripts/smoke_live.py`, fix any FAIL.
2. Click through the demo script once in a real browser.
3. Record the 3-minute video from the script above.
4. Screenshot the SerpApi page, the Copilot with evidence open, the HS evidence and the Radar.
