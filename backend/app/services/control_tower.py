"""Control Tower: only the shipments that need attention, grouped by what is wrong."""
from sqlalchemy.orm import Session

from app.models import ChecklistItem, Shipment, SignalMatch, Signal, SignalReview, TimelineEvent, User
from app.services import access as acc
from app.services import eta as eta_service
from app.services.timeline import effective_status

CATEGORIES = {
    "customs_hold": ("Customs hold", "red"), "port_event": ("Port event", "red"), "vessel_delay": ("Vessel delay", "amber"),
    "missing_document": ("Missing document", "amber"), "needs_review": ("Needs review", "red"), "cleared": ("Cleared", "green"),
}
RANK = {"red": 3, "amber": 2, "green": 1}


def build(db: Session, user: User) -> dict:
    counts = {k: 0 for k in CATEGORIES}
    rows = []
    owned = [(s, "owner", None) for s in acc.owned_shipments(db, user)]
    shared = [(s, "partner", role) for s, role in acc.shared_shipments(db, user)]
    for s, access, role in owned + shared:
        ex = []
        link = f"/shipments/{s.id}" if access == "owner" else f"/shipments/{s.id}/workspace"
        if s.stage == "ready":
            ex.append({"category": "cleared", "severity": "green", "title": "Cleared", "detail": "Approved and ready for handover."})
        elif s.stage != "rejected":
            hold = next((e for e in db.query(TimelineEvent).filter_by(shipment_id=s.id, key="customs_clearance") if effective_status(s, e)[0] in ("blocked", "delayed")), None)
            if hold:
                status, note = effective_status(s, hold)
                ex.append({"category": "customs_hold", "severity": "red", "title": "Customs hold" if status == "blocked" else "Clearance delayed", "detail": note or "Marked by the broker."})
            miss = [i for i in db.query(ChecklistItem).filter_by(shipment_id=s.id, status="missing", required=True)]
            if miss:
                ex.append({"category": "missing_document", "severity": "amber", "title": f"{len(miss)} document{'s' if len(miss) > 1 else ''} missing", "detail": ", ".join(f"{i.label} ({i.party_role})" for i in miss)})
            ids = [m.signal_id for m in db.query(SignalMatch).filter_by(shipment_id=s.id)]
            for sig in db.query(Signal).filter(Signal.id.in_(ids or [0])):
                if db.query(SignalReview).filter_by(signal_id=sig.id, org_id=user.org_id).first():
                    continue
                if sig.severity in ("high", "medium"):
                    ex.append({"category": "port_event", "severity": "red" if sig.severity == "high" else "amber", "title": sig.title, "detail": f"{sig.verification}, {round(sig.confidence * 100)}% confidence"})
            if access == "owner" and ((s.risk or {}).get("level") == "high" or (s.compliance or {}).get("overall") == "action_required"):
                ex.append({"category": "needs_review", "severity": "red", "title": "Needs your review", "detail": "High risk or open compliance issues."})
        eta = eta_service.estimate(db, s) if s.stage not in ("ready", "rejected") else {}
        if eta.get("delay_days", 0) >= 2:
            ex.append({"category": "vessel_delay", "severity": "red" if eta["delay_days"] >= 5 else "amber", "title": f"Expected delay {eta['delay_days']} days", "detail": f"ETA {eta['eta']}"})
        for e in ex:
            counts[e["category"]] += 1
        rows.append({"id": s.id, "reference": s.reference, "product": s.product_description, "route": f"{s.origin} to {s.destination}", "port": s.port, "access": access, "party_role": role, "stage_label": s.stage,
                     "eta": eta.get("eta"), "delay_days": eta.get("delay_days", 0), "exceptions": ex, "severity": max((e["severity"] for e in ex), key=lambda x: RANK[x], default="green"), "link": link,
                     "workspace_link": f"/shipments/{s.id}/workspace", "on_track": not [e for e in ex if e["category"] != "cleared"]})
    rows.sort(key=lambda r: (-RANK[r["severity"]], -len(r["exceptions"]), r["reference"]))
    return {"counts": counts, "labels": {k: v[0] for k, v in CATEGORIES.items()}, "shipments": rows, "total": len(rows)}
