"""Counterparty check: does the company have a public business listing, and does adverse news mention it?

This is NOT sanctions screening. Name collisions are common, so news is only called 'adverse'
when Gemini judges that the article clearly refers to the same company.
"""
from app.intelligence import gemini_client, gemini_ready, serpapi_client
from app.intelligence.domains import classify
from app.intelligence.errors import IntelligenceError
from app.intelligence.evidence import replace_evidence
from app.services.common import similarity

RISK_WORDS = 'fraud OR seizure OR sanctions OR smuggling OR "customs violation" OR investigation OR scam'
SYSTEM = "You screen news for a customs compliance analyst. Be strict: similar names are not the same company. Reply with one JSON object only."


def _source_name(raw) -> str:
    return str(raw.get("name", "")) if isinstance(raw, dict) else str(raw or "")


def _maps(name: str, country: str, shipment_id, fixture: bool, force: bool) -> dict | None:
    data = serpapi_client.search("google_maps", {"type": "search", "q": f"{name} {country}".strip()}, shipment_id=shipment_id, force=force, fixture=fixture)
    results = data.get("local_results") or ([data["place_results"]] if data.get("place_results") else [])
    best, best_sim = None, 0.0
    for r in results:
        sim = similarity(name, r.get("title"))
        if sim > best_sim:
            best, best_sim = r, sim
    if best is None or (best_sim < 0.6 and not fixture):
        return None
    return {"title": best.get("title", ""), "address": best.get("address", ""), "rating": best.get("rating"), "reviews": best.get("reviews"), "website": best.get("website", ""), "type": best.get("type", ""), "match": round(best_sim, 2)}


def _news(name: str, shipment_id, fixture: bool, force: bool) -> list[dict]:
    if fixture:
        return []  # the shared sample news belongs to the Radar, not to a company
    data = serpapi_client.search("google", {"q": f'"{name}" {RISK_WORDS}', "tbm": "nws", "hl": "en"}, shipment_id=shipment_id, force=force)
    out = []
    for r in (data.get("news_results") or [])[:5]:
        url = r.get("link") or ""
        if url:
            out.append({"title": str(r.get("title", ""))[:200], "url": url, "source": _source_name(r.get("source")), "date": str(r.get("date", "")), "snippet": str(r.get("snippet", ""))[:300], "trust": classify(url), "verdict": "possible", "reason": "Not screened by AI."})
    return out


def run(shipment, *, fixture: bool, force: bool = False) -> dict:
    sid = getattr(shipment, "id", None)
    parties = [("Importer", shipment.importer, shipment.destination), ("Exporter", shipment.exporter, shipment.origin)]
    results = []
    for role, name, country in parties:
        entry = {"role": role, "name": name, "country": country, "place": None, "articles": [], "errors": []}
        for label, fn in (("place", lambda: _maps(name, country, sid, fixture, force)), ("articles", lambda: _news(name, sid, fixture, force))):
            try:
                entry[label] = fn()
            except IntelligenceError as exc:
                entry["errors"].append(str(exc))
        results.append(entry)
    if all(e["errors"] and e["place"] is None and not e["articles"] for e in results):
        raise IntelligenceError(results[0]["errors"][0])

    screened = False
    if not fixture and gemini_ready() and any(e["articles"] for e in results):
        blocks = []
        for p, e in enumerate(results):
            arts = "\n".join(f"  [{i}] {a['title']} ({a['source']}, {a['date']}): {a['snippet']}" for i, a in enumerate(e["articles"], 1)) or "  (no articles)"
            blocks.append(f"PARTY {p}: {e['name']} ({e['role']}, {e['country']})\n{arts}")
        prompt = ("\n\n".join(blocks) + '\n\nReturn JSON: {"verdicts":[{"party":0,"index":1,"verdict":"adverse|possible|unrelated","reason":"one short sentence"}]}\n'
                  "adverse = the article clearly names this same company AND reports fraud, sanctions, smuggling, seizure or customs violations. "
                  "possible = a similar name but the identity is unclear. unrelated = a different company or topic.")
        try:
            parsed, _ = gemini_client.generate_json("company_screen", system=SYSTEM, parts=[{"text": prompt}], kind="fast", shipment_id=sid, force=force)
            for v in parsed.get("verdicts", []):
                try:
                    art = results[int(v["party"])]["articles"][int(v["index"]) - 1]
                except (KeyError, ValueError, IndexError, TypeError):
                    continue
                art["verdict"] = v.get("verdict") if v.get("verdict") in ("adverse", "possible", "unrelated") else "possible"
                art["reason"] = str(v.get("reason", ""))[:200]
            screened = True
        except IntelligenceError:
            pass

    rows, order = [], {"low": 0, "unknown": 1, "medium": 2, "high": 3}
    overall = "low"
    for e in results:
        relevant = [a for a in e["articles"] if a["verdict"] != "unrelated"]
        adverse = [a for a in relevant if a["verdict"] == "adverse"]
        if adverse:
            level, summary = "high", f"{len(adverse)} article(s) appear to report misconduct by this company."
        elif relevant:
            level, summary = "medium", f"{len(relevant)} news item(s) mention a similar name with risk words. Identity unclear." + ("" if screened else " Not screened by AI.")
        elif e["place"]:
            level, summary = "low", "Public business listing found. No adverse news found."
        else:
            level, summary = "unknown", "No public business listing found. This is a weak signal."
        if e["errors"]:
            summary += " Some lookups failed: " + e["errors"][0]
        e.update({"level": level, "summary": summary, "articles": relevant})
        rows.append(e)
        overall = level if order[level] > order[overall] else overall

    mode_label = "fixture" if fixture else "live"
    if sid:
        ev = []
        for e in rows:
            if e["place"]:
                ev.append({"engine": "google_maps", "query": e["name"], "title": f"{e['role']}: {e['place']['title']}", "url": e["place"]["website"], "snippet": f"{e['place']['address']} | rating {e['place']['rating']} ({e['place']['reviews']} reviews)", "trust": "web", "source_mode": mode_label})
            ev += [{"engine": "google_news", "query": e["name"], "title": a["title"], "url": a["url"], "snippet": f"{a['verdict']}: {a['reason']}", "trust": a["trust"], "source_mode": mode_label} for a in e["articles"]]
        replace_evidence(sid, "company", [x for x in ev if x["url"]])
    return {"kind": "company", "status": "ok", "parties": rows, "overall_level": overall, "screened_by_ai": screened, "source_mode": mode_label,
            "disclaimer": "Public web signals only. This is not sanctions or denied-party screening."}
