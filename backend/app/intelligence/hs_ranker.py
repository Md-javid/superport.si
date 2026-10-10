"""Evidence-backed HS classification: SerpApi finds sources, Gemini ranks candidates, code validates.

The model is never trusted blindly:
  * codes must have a valid format and chapter,
  * a code that does not appear in any retrieved source is flagged and its confidence is capped,
  * if anything fails the caller falls back to the rule-based result with a visible reason.
"""
import re

from app.intelligence import enabled_for, gemini_ready, mode, serpapi_ready
from app.intelligence import gemini_client, serpapi_client
from app.intelligence.domains import classify
from app.intelligence.errors import IntelligenceError
from app.intelligence.evidence import replace_evidence
from app.services.common import doc_value

SYSTEM = (
    "You are a customs tariff classification assistant supporting a licensed customs broker. "
    "You recommend; a human decides. Use the Harmonized System. Be honest about uncertainty: "
    "if the description is too vague, give low confidence and say what information is missing. "
    "Never invent sources or URLs. Reply with one JSON object only."
)


def available(shipment) -> bool:
    return enabled_for(shipment) and gemini_ready()


def _product_text(shipment, docs) -> str:
    return (doc_value(docs, "commercial_invoice", "product") or shipment.product_description or "").strip()


def fetch_sources(shipment, product_text: str, force: bool = False) -> tuple[list[dict], str, list[str]]:
    """Return (sources, source_mode, notes). Never raises: web evidence is helpful, not required."""
    notes: list[str] = []
    if not (enabled_for(shipment) and serpapi_ready()):
        return [], "none", notes
    short = product_text[:140]
    queries = [f"{short} HS code tariff classification", f"{short} customs tariff heading {shipment.destination} import"]
    seen: set[str] = set()
    sources: list[dict] = []
    rows: list[dict] = []
    source_mode = "fixture" if mode() == "fixtures" else "live"
    for q in queries:
        try:
            data = serpapi_client.search("google", {"q": q, "hl": "en", "num": 8}, shipment_id=getattr(shipment, "id", None), force=force)
        except IntelligenceError as exc:
            notes.append(str(exc))
            break
        for item in (data.get("organic_results") or [])[:6]:
            url = item.get("link") or ""
            if not url or url in seen:
                continue
            seen.add(url)
            src = {"index": len(sources) + 1, "title": item.get("title", "")[:200], "url": url, "snippet": (item.get("snippet") or "")[:400], "trust": classify(url)}
            sources.append(src)
            rows.append({"engine": "google", "query": q, "title": src["title"], "url": url, "snippet": src["snippet"], "trust": src["trust"], "source_mode": source_mode})
    sources = sources[:10]
    if getattr(shipment, "id", None) and rows:
        replace_evidence(shipment.id, "hs", rows[:10])
    return sources, source_mode, notes


def normalize_code(raw: str) -> str | None:
    digits = re.sub(r"\D", "", str(raw or ""))
    if len(digits) < 6:
        return None
    digits = digits[:8] if len(digits) >= 8 else digits[:6]
    chapter = int(digits[:2])
    if chapter < 1 or chapter > 97 or chapter == 77:
        return None
    return f"{digits[:4]}.{digits[4:6]}" + (f".{digits[6:8]}" if len(digits) == 8 else "")


def _grounding(code: str, sources: list[dict]) -> str:
    plain = code.replace(".", "")
    text = " ".join(f"{s['title']} {s['snippet']}" for s in sources).replace(".", "").replace(" ", "")
    if plain[:6] in text:
        return "code"
    if plain[:4] in text:
        return "heading"
    return "none"


def rank(shipment, docs, hint: dict, force: bool = False) -> dict:
    product = _product_text(shipment, docs)
    sources, source_mode, notes = fetch_sources(shipment, product, force)
    src_lines = "\n".join(f"[{s['index']}] {s['title']} ({s['trust']}, {s['url']}): {s['snippet']}" for s in sources) or "(no web sources available)"
    qty = doc_value(docs, "commercial_invoice", "quantity") or "unknown"
    net = doc_value(docs, "packing_list", "net_weight") or "unknown"
    prompt = (
        f"SHIPMENT\n- Product (shipment record): {shipment.product_description}\n- Product (commercial invoice): {product}\n"
        f"- Quantity: {qty}; net weight: {net}\n- Origin: {shipment.origin}; destination: {shipment.destination}\n\n"
        f"RULE-BASED HINT (may be wrong, do not just repeat it): {hint['code']} {hint['label']}\n\nWEB SOURCES\n{src_lines}\n\n"
        "TASK\nRank the 1 to 4 most plausible HS classifications, best first.\n"
        'Return JSON: {"candidates":[{"code":"XXXX.XX","label":"heading description","chapter":"Chapter NN: title","confidence":0.0,'
        '"evidence":[{"text":"why this fits","source":<source number or null>}],"why_not":"why this is not the first choice (omit for the first)"}],'
        '"rationale":"two plain sentences for a broker","needs_info":["details that would raise confidence"]}\n'
        "Rules: use 6-digit codes formatted XXXX.XX unless a source shows national digits. Cite a source number only if that source supports the point. "
        "Confidence reflects real certainty; vague descriptions must score below 0.6."
    )
    parsed, meta = gemini_client.generate_json("hs_rank", system=SYSTEM, parts=[{"text": prompt}], kind="pro", shipment_id=getattr(shipment, "id", None), force=force)

    cands, seen = [], set()
    for raw in parsed.get("candidates") or []:
        if not isinstance(raw, dict):
            continue
        code = normalize_code(raw.get("code"))
        if not code or code in seen:
            continue
        seen.add(code)
        try:
            conf = max(0.0, min(float(raw.get("confidence", 0)), 0.97))
        except (TypeError, ValueError):
            conf = 0.0
        cands.append({"code": code, "label": str(raw.get("label", ""))[:200], "chapter": str(raw.get("chapter", ""))[:160], "confidence": conf, "evidence": raw.get("evidence") or [], "why_not": str(raw.get("why_not", ""))[:300]})
    if not cands:
        raise IntelligenceError("Gemini did not return a valid HS code.")

    top = cands[0]
    grounded = _grounding(top["code"], sources)
    evidence: list[str] = []
    for ev in top["evidence"][:6]:
        if not isinstance(ev, dict) or not ev.get("text"):
            continue
        idx = ev.get("source")
        mark = f" [{idx}]" if isinstance(idx, int) and 1 <= idx <= len(sources) else ""
        evidence.append(f"{str(ev['text'])[:240]}{mark}")
    if grounded == "none":
        top["confidence"] = min(top["confidence"], 0.8 if sources else 0.75)
        evidence.append("This code was not found in the retrieved sources. Verify it against the official tariff." if sources else "No web sources were available, so this rests on the model alone. Verify it against the official tariff.")
    elif grounded == "heading":
        top["confidence"] = min(top["confidence"], 0.9)
        evidence.append("Only the 4-digit heading appears in the sources. Confirm the subheading.")
    else:
        evidence.append("The code appears in at least one retrieved source.")
    chapter = top["chapter"] or hint.get("chapter", "")
    evidence = evidence or [parsed.get("rationale", "Classified by Gemini.")]

    alternatives = [{"code": c["code"], "label": c["label"], "why_not": c["why_not"] or "Considered less likely for this description.", "confidence": round(min(c["confidence"], top["confidence"] - 0.01), 2)} for c in cands[1:4]]
    same_heading = top["code"][:4] == hint["code"][:4]
    return {
        "product_description": shipment.product_description,
        "code": top["code"],
        "label": top["label"] or hint["label"],
        "chapter": chapter,
        "confidence": round(top["confidence"], 2),
        "evidence": evidence,
        "alternatives": alternatives,
        "rationale": str(parsed.get("rationale") or "")[:600] or hint["rationale"],
        "item_key": hint["item_key"] if same_heading else "generic",
        "engine": f"gemini:{meta['model']}" + ("+serpapi" if sources else ""),
        "sources": sources,
        "sources_mode": source_mode if sources else "none",
        "grounded": grounded,
        "needs_info": [str(x)[:200] for x in (parsed.get("needs_info") or [])][:5],
        "source_notes": notes,
        "fallback_reason": None,
    }
