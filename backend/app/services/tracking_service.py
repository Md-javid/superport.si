from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models import AuditEvent, Shipment, utcnow
from app.services import timeline
from app.tracking import iso6346
from app.tracking.providers import TrackingNotConfigured, get_provider


def summary(shipment: Shipment) -> dict:
    t = shipment.tracking or {}
    check = iso6346.validate(shipment.container_number)
    try:
        provider = get_provider()
        connected, name, sample = provider.name != "none", provider.name, provider.sample
    except TrackingNotConfigured:
        connected, name, sample = False, "none", False
    reason = check["reason"]
    return {"connected": connected, "provider": name, "sample": sample, "fetched_at": t.get("fetched_at"), "status": t.get("status"), "location": t.get("location"), "vessel": t.get("vessel"),
            "voyage": t.get("voyage"), "eta": t.get("eta"), "events": t.get("events", []), "container": {"number": check["normalized"] or shipment.container_number, "valid": check["valid"], "reason": reason},
            "search_url": "https://www.google.com/search?q=" + (check["normalized"] or shipment.container_number) + "+container+tracking"}


def refresh(db: Session, shipment: Shipment, actor: str) -> dict:
    provider = get_provider()
    result = provider.track(shipment.container_number, shipment.carrier, shipment.origin, shipment.port)
    shipment.tracking = {**result, "provider": provider.name, "sample": provider.sample, "fetched_at": utcnow().isoformat()}
    flag_modified(shipment, "tracking")
    changed = timeline.apply_tracking(db, shipment, result)
    db.add(AuditEvent(shipment_id=shipment.id, actor=actor, kind="human", action="tracking_refreshed", message=f"Refreshed tracking ({provider.name}). {changed} timeline step(s) updated.", detail={"sample": provider.sample}))
    return summary(shipment)
