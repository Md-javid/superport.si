"""Upgrade older databases: give every user an organisation and every shipment an owner."""
from sqlalchemy.orm import Session

from app.models import Organization, Shipment, User
from app.services import checklist, timeline


def backfill(db: Session) -> None:
    first_org = None
    for u in db.query(User).order_by(User.id):
        if u.org_id is None:
            org = Organization(name=u.company or f"{u.name}'s company", type="broker")
            db.add(org)
            db.flush()
            u.org_id, u.org_role, u.email_verified = org.id, "admin", True  # existing accounts predate verification
        first_org = first_org or u.org_id
    if first_org:
        for s in db.query(Shipment).filter(Shipment.org_id.is_(None)):
            s.org_id = first_org
    for s in db.query(Shipment):
        checklist.ensure_checklist(db, s)
        timeline.ensure_timeline(db, s)
    db.commit()
