"""Check your real API keys end to end.   Run from backend/:   python scripts/smoke_live.py [--doc path/to/invoice.pdf]

Reads keys from backend/.env. Uses a handful of calls (about 2 SerpApi searches, 3 Gemini calls).
Never prints your keys.
"""
import argparse
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["INTELLIGENCE_MODE"] = "live"

from app.core.config import get_settings  # noqa: E402
from app.db import ensure_schema  # noqa: E402
from app.intelligence import doc_reader, gemini_client, hs_ranker, serpapi_client  # noqa: E402
from app.intelligence.errors import IntelligenceError  # noqa: E402
from app.market import company_check, price_check, rules_lookup  # noqa: E402
from app.radar import extract  # noqa: E402
from app.services import hs_code  # noqa: E402

ok = True


def step(name, fn):
    global ok
    try:
        out = fn()
        print(f"  PASS  {name}" + (f"  ->  {out}" if out else ""))
        return True
    except IntelligenceError as exc:
        ok = False
        print(f"  FAIL  {name}  ->  {exc}")
    except Exception as exc:  # noqa: BLE001
        ok = False
        print(f"  FAIL  {name}  ->  {type(exc).__name__}: {exc}")
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--doc", help="optional invoice/packing list PDF or image to test document reading")
    args = parser.parse_args()
    s = get_settings()
    print("SuperPort live check")
    print(f"  GEMINI_API_KEY set: {bool(s.gemini_api_key)}   SERPAPI_API_KEY set: {bool(s.serpapi_api_key)}")
    ensure_schema()

    print("\nSerpApi")
    step("Google search returns results", lambda: f"{len(serpapi_client.search('google', {'q': 'lithium-ion accumulators HS code 8507', 'hl': 'en'}, force=True).get('organic_results', []))} results")

    print("\nGemini")
    models = []

    def list_():
        nonlocal models
        models = gemini_client.list_models()
        fast, pro = gemini_client.pick_models(models)
        return f"{len(models)} models; auto-picked fast={fast}, pro={pro}"

    step("List models for your key", list_)
    step("Tiny JSON test", lambda: gemini_client.generate_json("smoke", system="Reply with JSON only.", parts=[{"text": 'Return {"ok": true}'}], kind="fast", force=True)[0])

    print("\nEvidence-backed HS classification")
    shipment = SimpleNamespace(id=None, product_description="Lithium-ion battery packs, 48V 100Ah, for energy storage systems", destination="India", origin="China", is_demo=False)

    def hs():
        hint = hs_code.recommend_rules(shipment, [])
        r = hs_ranker.rank(shipment, [], hint, force=True)
        return f"{r['code']} ({r['label']}), confidence {r['confidence']}, grounded={r['grounded']}, {len(r['sources'])} sources"

    step("Classify a sample product", hs)

    print("\nMilestone 3: market checks")
    doc = SimpleNamespace(doc_type="commercial_invoice", fields=[{"key": "unit_price", "value": "612.50"}, {"key": "currency", "value": "USD"}, {"key": "product", "value": "Lithium-ion battery packs, 48V 100Ah"}])
    ship = SimpleNamespace(id=None, importer="Tata Power Company Ltd", exporter="Contemporary Amperex Technology Co. Limited", origin="China", destination="India", port="Chennai Port (INMAA)", product_description="Lithium-ion battery packs, 48V 100Ah", is_demo=False)

    def price():
        r = price_check.run(ship, [doc], fixture=False, force=True)
        return f"{r['status']}: {r['summary'][:140]}"

    def company():
        r = company_check.run(ship, fixture=False, force=True)
        return "; ".join(f"{p['role']} {p['level']} ({'listing found' if p['place'] else 'no listing'}, {len(p['articles'])} news)" for p in r["parties"]) + f"; screened by AI: {r['screened_by_ai']}"

    def rules():
        r = rules_lookup.run(ship, {"code": "8507.60", "label": "Lithium-ion accumulators"}, None, fixture=False, force=True)
        return f"{r['status']}: {r['summary']}"

    step("Price check (Google Shopping)", price)
    step("Counterparty check (Google Maps + News)", company)
    step("Rules lookup (Google Search + Gemini)", rules)

    print("\nMilestone 4: Trade Signal Radar")
    watch = {"ports": ["Chennai Port"], "countries": {"India", "China"}, "products": ["Lithium-ion battery packs"], "product_words": {"battery", "lithium"}}
    arts = []

    def news():
        data = serpapi_client.search("google", {"q": "Chennai Port congestion OR strike OR closure OR cyclone", "tbm": "nws", "hl": "en", "tbs": "qdr:m"}, force=True)
        for r in data.get("news_results") or []:
            src = r.get("source")
            arts.append({"title": r.get("title", ""), "url": r.get("link", ""), "source": src.get("name", "") if isinstance(src, dict) else str(src or ""), "date": str(r.get("date", "")), "snippet": str(r.get("snippet", "")), "query": ""})
        return f"{len(arts)} articles" + (f"; first: {arts[0]['title'][:80]}" if arts else "")

    step("News search for a port", news)
    if arts:
        step("Gemini event extraction", lambda: f"{len(extract.gemini_events(arts[:12], watch)[0])} events")
        step("Keyword fallback extraction", lambda: f"{len(extract.heuristic_events(arts, watch)[0])} events")

    if args.doc:
        print("\nDocument reading")
        path = args.doc
        data = open(path, "rb").read()
        specs = [("product", "Product"), ("quantity", "Quantity"), ("total_value", "Total value"), ("currency", "Currency"), ("consignee", "Consignee"), ("shipper", "Shipper")]

        def read():
            values, info = doc_reader.read_document("Commercial Invoice", specs, os.path.basename(path), data, None)
            for k, v in values.items():
                print(f"          {k}: {v['value']!r}  (confidence {v['confidence']})")
            return f"model {info['model']}"

        step("Read your document", read)

    print("\nResult:", "ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED (see above)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
