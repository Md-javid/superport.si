"""Trade Signal Radar.

Pipeline: watch list from active shipments -> news search (SerpApi) -> event extraction (Gemini or heuristic)
-> source-based verification -> match to shipments -> stored as SIGNALS that a human acknowledges or dismisses.
A signal never changes a shipment's stage, risk score or approval. It is context for a person.
"""
import hashlib
import re

from sqlalchemy.orm import Session

from app.catalog import CATALOG
from app.core.config import get_settings
from app.intelligence import gemini_ready, mode, serpapi_client
from app.intelligence.domains import classify, host_of
from app.intelligence.errors import IntelligenceError
from app.models import AuditEvent, FeedbackEvent, Shipment, Signal, SignalMatch, SignalReview, utcnow
from app.radar import extract
from app.services.common import similarity

_STOP = {"with", "from", "that", "this", "pack", "packs", "pcs", "units", "grade", "assorted", "retail", "boxed", "bagged", "for", "and", "the", "systems", "system"}


def clean_port(port: str) -> str:
    return re.sub(r"\s*\(.*?\)", "", port or "").strip()


def build_watch(db: Session) -> dict:
    active = [s for s in db.query(Shipment).all() if s.stage not in ("ready", "rejected")]
    ports = sorted({clean_port(s.port) for s in active if s.port})
    countries = {c for s in active for c in (s.origin, s.destination) if c}
    products, words = [], set()
    for s in active:
        short = s.product_description.split(",")[0][:60]
        if short not in products:
            products.append(short)
        words.update(w for w in re.findall(r"[a-z]{5,}", s.product_description.lower()) if w not in _STOP)
        for item in CATALOG:  # catalog keywords make the heuristic notice "battery" for a "lithium-ion pack"
            if any(k in s.product_description.lower() for k in item["keywords"]):
                words.update(k for k in item["keywords"] if len(k) >= 5)
    carriers = {c.split()[0].lower() for c in (s.carrier for s in active) if c and len(c.split()[0]) >= 3}
    return {"shipments": active, "ports": ports, "countries": countries, "products": products, "product_words": words, "carriers": carriers}


def build_queries(watch: dict, limit: int) -> list[str]:
    """Most useful first, so a small budget still covers ports, carriers, weather and rule changes."""
    ports, carriers = watch["ports"], sorted(watch["carriers"])
    dests = sorted({s.destination for s in watch["shipments"] if s.destination})
    origins = sorted({s.origin for s in watch["shipments"] if s.origin})
    prods = " OR ".join(f'"{p}"' for p in watch["products"][:2])
    ordered = [f"{p} port congestion OR strike OR closure" for p in ports[:2]]
    ordered += [f"{d} customs import duty OR restriction OR notification {prods}".strip() for d in dests[:1]]
    ordered += [f"{c.title()} blank sailing OR schedule change OR vessel cancellation OR service suspension" for c in carriers[:2]]
    ordered += [f"{p} weather warning cyclone OR heavy rain OR storm" for p in ports[:1]]
    ordered += [f"{o} export restriction OR port disruption OR strike" for o in origins[:1]]
    ordered += [f"{p} port congestion OR strike OR closure" for p in ports[2:3]]
    ordered += [f"{d} customs import duty OR restriction OR notification {prods}".strip() for d in dests[1:2]]
    ordered += [f"{p} weather warning cyclone OR heavy rain OR storm" for p in ports[1:2]]
    return ordered[:limit]


def _publisher(raw) -> str:
    return str(raw.get("name", "")) if isinstance(raw, dict) else str(raw or "")


def fetch_articles(queries: list[str], fixture: bool, force: bool) -> tuple[list[dict], list[str]]:
    settings, articles, seen, errors = get_settings(), [], set(), []
    for q in queries:
        try:
            data = serpapi_client.search("google", {"q": q, "tbm": "nws", "hl": "en", "tbs": f"qdr:{settings.radar_window}"}, force=force, fixture=fixture)
        except IntelligenceError as exc:
            errors.append(str(exc))
            if len(errors) >= 2:
                break
            continue
        for r in data.get("news_results") or []:
            url = r.get("link") or ""
            if url and url not in seen:
                seen.add(url)
                articles.append({"title": str(r.get("title", ""))[:200], "url": url, "source": _publisher(r.get("source")), "date": str(r.get("date", "")), "snippet": str(r.get("snippet", ""))[:300], "query": q})
    return articles[:24], errors


def verify_event(event: dict, articles: list[dict]) -> dict:
    sources = []
    for i in event["articles"]:
        a = articles[i - 1]
        sources.append({"title": a["title"], "url": a["url"], "source": a["source"], "date": a["date"], "trust": classify(a["url"])})
    publishers = {(s["source"] or host_of(s["url"])).strip().lower() for s in sources}
    n = len(publishers)
    official = any(s["trust"] == "official" for s in sources)
    conf = {1: 0.35, 2: 0.6}.get(n, 0.8) + (0.1 if official else 0.0)
    label = "official" if official else ("corroborated" if n >= 2 else "single-source")
    return {"sources": sources, "confidence": round(min(conf, 0.9), 2), "verification": label}


def fingerprint(event: dict) -> str:
    words = " ".join(sorted(re.findall(r"[a-z0-9]{4,}", event["title"].lower()))[:8])
    raw = "|".join([event["event_type"], ",".join(sorted(p.lower() for p in event["ports"])), ",".join(sorted(c.lower() for c in event["countries"])), ",".join(sorted(c.lower() for c in event.get("carriers", []))), words])
    return hashlib.sha256(raw.encode()).hexdigest()[:40]


def match_shipments(event: dict, active: list[Shipment]) -> list[tuple[Shipment, str]]:
    out = []
    ev_countries = {c.lower() for c in event["countries"]}
    ev_products = " ".join(event["products"]).lower()
    for s in active:
        port = clean_port(s.port).lower()
        reason = None
        if any(p and (similarity(p, port) >= 0.75 or p.lower() in port or port in p.lower()) for p in event["ports"]):
            reason = f"Discharge port: {clean_port(s.port)}"
        elif event.get("carriers") and any(c.lower().split()[0] in (s.carrier or "").lower() for c in event["carriers"]):
            reason = f"Carrier: {s.carrier}"
        elif event["event_type"] in ("tariff_change", "regulation") and {s.origin.lower(), s.destination.lower()} & ev_countries:
            overlap = [w for w in re.findall(r"[a-z]{5,}", s.product_description.lower()) if w in ev_products]
            if overlap or not event["products"]:
                reason = f"Rule change in {s.destination if s.destination.lower() in ev_countries else s.origin}" + (f" for {overlap[0]}" if overlap else "")
        elif event["severity"] == "high" and event["event_type"] in ("weather", "geopolitical", "closure") and {s.origin.lower(), s.destination.lower()} & ev_countries:
            reason = "Route region"
        if reason:
            out.append((s, reason))
    return out


def scan(db: Session, force: bool = False) -> dict:
    current = mode()
    if current == "off":
        raise IntelligenceError("Radar needs INTELLIGENCE_MODE=fixtures or live.")
    fixture = current == "fixtures"
    settings = get_settings()
    watch = build_watch(db)
    if not watch["shipments"]:
        return {"queries": 0, "articles": 0, "events": 0, "new": 0, "updated": 0, "matched": 0, "errors": [], "engine": "none", "note": "No active shipments to watch."}
    queries = build_queries(watch, settings.radar_max_queries)
    articles, errors = fetch_articles(queries, fixture, force)
    if not articles and errors:
        raise IntelligenceError(errors[0])
    engine = "keyword-heuristic"
    events: list[dict] = []
    if articles:
        if gemini_ready() and not fixture:
            try:
                events, engine = extract.gemini_events(articles, watch)
            except IntelligenceError as exc:
                errors.append(f"Gemini extraction failed, used keyword matching instead: {exc}")
        if not events and engine == "keyword-heuristic" or not gemini_ready() or fixture:
            events, engine = extract.heuristic_events(articles, watch)

    new = updated = matched = 0
    for ev in events:
        proof = verify_event(ev, articles)
        fp = fingerprint(ev)
        row = db.query(Signal).filter_by(fingerprint=fp).first()
        if row:
            known = {s["url"] for s in row.sources or []}
            row.sources = (row.sources or []) + [s for s in proof["sources"] if s["url"] not in known]
            publishers = {(s["source"] or host_of(s["url"])).lower() for s in row.sources}
            row.confidence = max(row.confidence, proof["confidence"], 0.6 if len(publishers) >= 2 else 0)
            row.verification = "official" if proof["verification"] == "official" or row.verification == "official" else ("corroborated" if len(publishers) >= 2 else row.verification)
            row.last_seen = utcnow()
            updated += 1
        else:
            row = Signal(fingerprint=fp, event_type=ev["event_type"], title=ev["title"], summary=ev["summary"], severity=ev["severity"], confidence=proof["confidence"], verification=proof["verification"],
                         locations=ev["ports"] + ev["countries"], products=ev["products"], carriers=ev.get("carriers", []), sources=proof["sources"], engine=engine, source_mode="fixture" if fixture else "live")
            db.add(row)
            new += 1
        db.flush()
        db.query(SignalMatch).filter_by(signal_id=row.id).delete()
        for s, reason in match_shipments(ev, watch["shipments"]):
            db.add(SignalMatch(signal_id=row.id, shipment_id=s.id, reason=reason))
            matched += 1
    db.commit()
    return {"queries": len(queries), "articles": len(articles), "events": len(events), "new": new, "updated": updated, "matched": matched, "errors": errors, "engine": engine, "sample": fixture}


def signal_out(db: Session, sig: Signal, visible_ids: set | None = None, org_id: int | None = None) -> dict:
    matches = db.query(SignalMatch).filter_by(signal_id=sig.id).all()
    if visible_ids is not None:
        matches = [m for m in matches if m.shipment_id in visible_ids]
    ships = {s.id: s for s in db.query(Shipment).filter(Shipment.id.in_([m.shipment_id for m in matches] or [0])).all()}
    rev = db.query(SignalReview).filter_by(signal_id=sig.id, org_id=org_id).first() if org_id is not None else None
    return {"id": sig.id, "event_type": sig.event_type, "title": sig.title, "summary": sig.summary, "severity": sig.severity, "confidence": sig.confidence, "verification": sig.verification,
            "locations": sig.locations or [], "products": sig.products or [], "carriers": sig.carriers or [], "sources": sig.sources or [], "engine": sig.engine, "source_mode": sig.source_mode,
            "status": rev.status if rev else "new", "review_note": rev.note if rev else "",
            "first_seen": sig.first_seen.isoformat(), "last_seen": sig.last_seen.isoformat(),
            "affected": [{"shipment_id": m.shipment_id, "reference": ships[m.shipment_id].reference, "reason": m.reason} for m in matches if m.shipment_id in ships]}


def list_signals(db: Session, status: str = "active", shipment_id: int | None = None, visible_ids: set | None = None, org_id: int | None = None) -> list[dict]:
    out = []
    for sig in db.query(Signal).all():
        o = signal_out(db, sig, visible_ids, org_id)
        if visible_ids is not None and not o["affected"]:
            continue  # a company only sees signals that touch its own or shared shipments
        if shipment_id is not None and not any(a["shipment_id"] == shipment_id for a in o["affected"]):
            continue
        if status == "active" and o["status"] != "new":
            continue
        out.append(o)
    order = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda o: o["last_seen"], reverse=True)
    out.sort(key=lambda o: (order.get(o["severity"], 3), -o["confidence"]))
    return out


def review(db: Session, sig: Signal, action: str, note: str, actor: str, org_id: int) -> None:
    if action not in ("acknowledge", "dismiss"):
        raise ValueError("Unknown action.")
    status = "acknowledged" if action == "acknowledge" else "dismissed"
    row = db.query(SignalReview).filter_by(signal_id=sig.id, org_id=org_id).first()
    if row:
        row.status, row.note, row.reviewed_by, row.created_at = status, note[:500], actor, utcnow()
    else:
        db.add(SignalReview(signal_id=sig.id, org_id=org_id, status=status, note=note[:500], reviewed_by=actor))
    for m in db.query(SignalMatch).filter_by(signal_id=sig.id):
        ship = db.get(Shipment, m.shipment_id)
        if not ship or ship.org_id != org_id:
            continue  # only write to this organisation's own shipments
        db.add(AuditEvent(shipment_id=m.shipment_id, actor=actor, kind="human", action=f"signal_{action}", message=f"{'Acknowledged' if action == 'acknowledge' else 'Dismissed'} signal: {sig.title}", detail={"note": note, "confidence": sig.confidence, "verification": sig.verification}))
        if get_settings().collect_feedback:
            db.add(FeedbackEvent(shipment_id=m.shipment_id, kind="signal_review", field=sig.event_type, ai_value=f"{sig.severity}/{sig.confidence}", human_value=action, action=action, user=actor, context={"verification": sig.verification, "engine": sig.engine}))
    db.commit()
