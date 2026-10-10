"""Shipment timeline: seven standard steps, updated by the right party, with tracking events applied on top."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Shipment, TimelineEvent, utcnow

STEPS = [
    ("factory_pickup", "Factory pickup"),
    ("port_arrival_origin", "Arrived at origin port"),
    ("loaded", "Loaded on vessel"),
    ("in_transit", "In transit"),
    ("arrived_destination", "Arrived at destination port"),
    ("customs_clearance", "Customs clearance"),
    ("warehouse_delivery", "Delivered to warehouse"),
]
# Who may update each step (the owner organisation may update any step except as noted).
EDITORS = {
    "factory_pickup": {"exporter", "forwarder"},
    "port_arrival_origin": {"forwarder"},
    "loaded": {"forwarder"},
    "in_transit": {"forwarder"},
    "arrived_destination": {"forwarder"},
    "customs_clearance": set(),  # driven by the broker's workflow; only the owner can mark a hold
    "warehouse_delivery": {"forwarder", "importer"},
}
STATUSES = ("pending", "current", "done", "delayed", "blocked")


def ensure_timeline(db: Session, shipment: Shipment) -> None:
    have = {e.key for e in db.query(TimelineEvent).filter_by(shipment_id=shipment.id)}
    for pos, (key, label) in enumerate(STEPS):
        if key not in have:
            db.add(TimelineEvent(shipment_id=shipment.id, key=key, label=label, position=pos))
    db.flush()


def can_update(key: str, access: str, party_role: str | None) -> bool:
    return access == "owner" or (access == "partner" and party_role in EDITORS.get(key, set()))


def _aware(dt):
    return dt.replace(tzinfo=timezone.utc) if dt is not None and dt.tzinfo is None else dt


def effective_status(shipment: Shipment, e: TimelineEvent) -> tuple[str, str]:
    """Customs clearance follows the broker's workflow unless the owner recorded a hold."""
    if e.key != "customs_clearance":
        return e.status, e.note
    if shipment.stage == "ready":
        return "done", e.note
    if shipment.stage == "rejected":
        return "blocked", "Rejected by the broker."
    if e.source == "manual" and e.status in ("delayed", "blocked"):
        return e.status, e.note
    if shipment.stage in ("hs_review", "final_review"):
        return "current", e.note
    return "pending", e.note


def timeline_out(db: Session, shipment: Shipment, access: str, party_role: str | None) -> list[dict]:
    ensure_timeline(db, shipment)
    rows = db.query(TimelineEvent).filter_by(shipment_id=shipment.id).order_by(TimelineEvent.position).all()
    out = []
    for e in rows:
        status, note = effective_status(shipment, e)
        out.append({"key": e.key, "label": e.label, "status": status, "planned_at": _aware(e.planned_at).isoformat() if e.planned_at else None, "actual_at": _aware(e.actual_at).isoformat() if e.actual_at else None,
                    "source": e.source, "note": note, "updated_by": e.updated_by, "can_update": (access == "owner") if e.key == "customs_clearance" else can_update(e.key, access, party_role)})
    return out


def parse_when(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Use a date such as 2026-11-04.")
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def update_event(db: Session, shipment: Shipment, key: str, *, status: str | None, planned_at: str | None, actual_at: str | None, note: str | None, actor: str, source: str = "manual") -> TimelineEvent:
    ensure_timeline(db, shipment)
    e = db.query(TimelineEvent).filter_by(shipment_id=shipment.id, key=key).one()
    if status is not None:
        if status not in STATUSES:
            raise ValueError("Unknown status.")
        e.status = status
        if status == "done" and not actual_at and not e.actual_at:
            e.actual_at = utcnow()
        if status in ("pending", "current"):
            e.actual_at = None
    if planned_at is not None:
        e.planned_at = parse_when(planned_at) if planned_at != "" else None
    if actual_at:
        e.actual_at = parse_when(actual_at)
    if note is not None:
        e.note = note.strip()[:300]
    e.source, e.updated_by, e.updated_at = source, actor, utcnow()
    return e


def apply_tracking(db: Session, shipment: Shipment, result: dict) -> int:
    """Mark steps done from tracking events. Never overrides something a person set by hand."""
    ensure_timeline(db, shipment)
    changed = 0
    for ev in result.get("events", []):
        key = ev.get("key")
        if not key:
            continue
        row = db.query(TimelineEvent).filter_by(shipment_id=shipment.id, key=key).first()
        if row and row.source != "manual" and row.status != "done":
            row.status, row.actual_at, row.source, row.updated_by, row.updated_at = "done", parse_when(ev["time"]), "tracking", "Tracking", utcnow()
            changed += 1
    done_keys = {r.key for r in db.query(TimelineEvent).filter_by(shipment_id=shipment.id) if r.status == "done"}
    if "in_transit" in done_keys and "arrived_destination" not in done_keys:
        row = db.query(TimelineEvent).filter_by(shipment_id=shipment.id, key="in_transit").first()
        row.status = "current"
        row.actual_at = row.actual_at
    if result.get("eta"):
        arr = db.query(TimelineEvent).filter_by(shipment_id=shipment.id, key="arrived_destination").first()
        if arr and arr.source != "manual":
            arr.planned_at = parse_when(result["eta"])
    return changed
