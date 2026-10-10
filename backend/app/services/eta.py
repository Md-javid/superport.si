"""ETA estimate. A transparent rule-based estimate, not machine learning.

Baseline = carrier ETA (tracking) or the planned arrival date. Delays come from open Radar signals that touch the
shipment (weighted by how well each is confirmed) and from missing required documents. Every driver is listed.
"""
from datetime import timezone

from sqlalchemy.orm import Session

from app.models import ChecklistItem, Shipment, SignalMatch, SignalReview, Signal, TimelineEvent, utcnow

DAYS = {"congestion": {"high": 3, "medium": 2, "low": 1}, "strike": {"high": 4, "medium": 2, "low": 1}, "weather": {"high": 3, "medium": 1, "low": 0},
        "closure": {"high": 3, "medium": 2, "low": 1}, "carrier": {"high": 4, "medium": 2, "low": 1}}


def _aware(dt):
    return dt.replace(tzinfo=timezone.utc) if dt is not None and dt.tzinfo is None else dt


def estimate(db: Session, shipment: Shipment) -> dict:
    tracking = shipment.tracking or {}
    planned = db.query(TimelineEvent).filter_by(shipment_id=shipment.id, key="arrived_destination").first()
    arrived = bool(planned and planned.status == "done")
    base, basis = None, "none"
    if tracking.get("eta"):
        from app.services.timeline import parse_when

        base, basis = parse_when(tracking["eta"]), "sample tracking" if tracking.get("sample") else "carrier tracking"
    elif planned and planned.planned_at:
        base, basis = _aware(planned.planned_at), "planned arrival date"
    if arrived:
        return {"eta": None, "arrived": True, "basis": "arrived", "message": "The shipment has arrived at the destination port.", "drivers": [], "delay_days": 0}
    if base is None:
        return {"eta": None, "arrived": False, "basis": "none", "message": "Add a planned arrival date, or connect tracking, to get an ETA.", "drivers": [], "delay_days": 0}

    drivers, total, unverified = [], 0.0, 0
    sig_ids = [m.signal_id for m in db.query(SignalMatch).filter_by(shipment_id=shipment.id)]
    for sig in db.query(Signal).filter(Signal.id.in_(sig_ids or [0])):
        dismissed = db.query(SignalReview).filter_by(signal_id=sig.id, org_id=shipment.org_id, status="dismissed").first()
        days = DAYS.get(sig.event_type, {}).get(sig.severity, 0)
        if dismissed or not days:
            continue
        weighted = days * sig.confidence
        total += weighted
        unverified += sig.verification == "single-source"
        drivers.append({"label": sig.title, "days": round(weighted, 1), "kind": "signal", "detail": f"{sig.verification}, {round(sig.confidence * 100)}% confidence"})
    missing = [i.label for i in db.query(ChecklistItem).filter_by(shipment_id=shipment.id, status="missing", required=True)]
    if missing:
        d = min(3, len(missing))
        total += d
        drivers.append({"label": "Missing documents: " + ", ".join(missing), "days": float(d), "kind": "documents", "detail": "Customs cannot clear the cargo without them"})
    delay = round(total)
    confidence = {"carrier tracking": 0.8, "sample tracking": 0.5, "planned arrival date": 0.6}[basis] - 0.05 * unverified - (0.05 if missing else 0)
    confidence = round(max(0.3, confidence), 2)
    from datetime import timedelta

    eta = base + timedelta(days=delay)
    spread = max(1, round(delay * 0.5) + (1 if basis != "carrier tracking" else 0))
    risk = "low" if delay <= 1 else ("moderate" if delay <= 4 else "high")
    return {"eta": eta.date().isoformat(), "baseline": base.date().isoformat(), "earliest": (eta - timedelta(days=1)).date().isoformat(), "latest": (eta + timedelta(days=spread)).date().isoformat(),
            "delay_days": delay, "confidence": confidence, "risk": risk, "basis": basis, "drivers": drivers, "arrived": False,
            "message": "Estimate from simple rules, not a guarantee. It improves as tracking and history are connected."}
