"""Destination rules lookup: find import requirements on the web and turn them into a CITED checklist.

Every item must point at a retrieved source. Items the model cannot cite are dropped, never shown.
"""
from app.intelligence import gemini_client, gemini_ready, serpapi_client
from app.intelligence.domains import classify
from app.intelligence.errors import IntelligenceError
from app.intelligence.evidence import replace_evidence

SYSTEM = ("You extract import requirements for a customs analyst from numbered web sources. Use ONLY what the sources say. "
          "Never add requirements from memory. Cite the source number for every item. Reply with one JSON object only.")


def run(shipment, hs_result, hs_decision, *, fixture: bool, force: bool = False) -> dict:
    code = (hs_decision or {}).get("code") or hs_result["code"]
    product = (hs_result.get("label") or shipment.product_description)[:80]
    sid = getattr(shipment, "id", None)
    queries = [f"{shipment.destination} import requirements {product} HS {code} permit certificate", f"{shipment.destination} import restrictions duty {product} HS {code}"]
    sources, seen = [], set()
    for q in queries:
        data = serpapi_client.search("google", {"q": q, "hl": "en"}, shipment_id=sid, force=force, fixture=fixture)
        for r in (data.get("organic_results") or [])[:6]:
            url = r.get("link") or ""
            if url and url not in seen:
                seen.add(url)
                sources.append({"index": len(sources) + 1, "title": str(r.get("title", ""))[:200], "url": url, "snippet": str(r.get("snippet", ""))[:400], "trust": classify(url)})
    sources = sources[:10]
    mode_label = "fixture" if fixture else "live"
    base = {"kind": "rules", "hs_code": code, "destination": shipment.destination, "sources": sources, "source_mode": mode_label}
    if sid and sources:
        replace_evidence(sid, "rules", [{"engine": "google", "query": queries[0], "title": s["title"], "url": s["url"], "snippet": s["snippet"], "trust": s["trust"], "source_mode": mode_label} for s in sources])
    if fixture or not gemini_ready():
        return {**base, "status": "sources_only", "restrictions": [], "certificates": [], "duty_notes": [], "summary": "Sources found. Turn on live Gemini to turn them into a checklist."}
    if not sources:
        return {**base, "status": "no_findings", "restrictions": [], "certificates": [], "duty_notes": [], "summary": "No web sources were found."}

    listing = "\n".join(f"[{s['index']}] {s['title']} ({s['trust']}, {s['url']}): {s['snippet']}" for s in sources)
    prompt = (f"Goods: {product}. HS code: {code}. Origin: {shipment.origin}. Destination: {shipment.destination}.\n\nSOURCES\n{listing}\n\n"
              'Return JSON: {"restrictions":[{"text":"...","source":1}],"certificates":[{"name":"...","level":"required|likely|unsure","source":1}],"duty_notes":[{"text":"...","source":1}]}\n'
              "Only include items stated in the sources. Keep each text under 200 characters. Empty lists are fine.")
    parsed, _ = gemini_client.generate_json("rules_extract", system=SYSTEM, parts=[{"text": prompt}], kind="pro", shipment_id=sid, force=force)

    def valid(item):
        return isinstance(item, dict) and isinstance(item.get("source"), int) and 1 <= item["source"] <= len(sources)

    out, dropped = {"restrictions": [], "certificates": [], "duty_notes": []}, 0
    for key, field in (("restrictions", "text"), ("duty_notes", "text"), ("certificates", "name")):
        seen_text = set()
        for item in parsed.get(key) or []:
            text = str(item.get(field, "")).strip()[:220] if isinstance(item, dict) else ""
            if not text or not valid(item) or text.lower() in seen_text:
                dropped += 1
                continue
            seen_text.add(text.lower())
            entry = {field: text, "source": item["source"], "trust": sources[item["source"] - 1]["trust"]}
            if key == "certificates":
                entry["level"] = item.get("level") if item.get("level") in ("required", "likely", "unsure") else "unsure"
            out[key].append(entry)
    found = sum(len(v) for v in out.values())
    return {**base, "status": "ok" if found else "no_findings", **out, "dropped_uncited": dropped,
            "summary": f"{found} cited item(s) from {len(sources)} sources." + (f" {dropped} uncited item(s) were discarded." if dropped else "") + " Verify against the official notification before filing."}
