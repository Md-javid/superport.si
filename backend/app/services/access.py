"""Who may see what. Tenant isolation lives here and in the query helpers below."""
from sqlalchemy.orm import Session

from app.models import Organization, Shipment, ShipmentParticipant, User

PARTY_ROLES = ("broker", "forwarder", "importer", "exporter")


def access_for(db: Session, user: User, shipment: Shipment) -> tuple[str | None, str | None]:
    """Return ("owner", None), ("partner", party_role) or (None, None)."""
    if user.org_id is not None and shipment.org_id == user.org_id:
        return "owner", None
    p = db.query(ShipmentParticipant).filter_by(shipment_id=shipment.id, org_id=user.org_id).first()
    return ("partner", p.party_role) if p else (None, None)


def owned_shipments(db: Session, user: User) -> list[Shipment]:
    return db.query(Shipment).filter(Shipment.org_id == user.org_id).order_by(Shipment.updated_at.desc()).all()


def shared_shipments(db: Session, user: User) -> list[tuple[Shipment, str]]:
    rows = db.query(ShipmentParticipant).filter_by(org_id=user.org_id).all()
    out = []
    for p in rows:
        s = db.get(Shipment, p.shipment_id)
        if s:
            out.append((s, p.party_role))
    return out


def accessible_ids(db: Session, user: User) -> set[int]:
    return {s.id for s in owned_shipments(db, user)} | {s.id for s, _ in shared_shipments(db, user)}


def shipment_user_ids(db: Session, shipment: Shipment, exclude_org: int | None = None) -> list[int]:
    org_ids = {shipment.org_id} | {p.org_id for p in db.query(ShipmentParticipant).filter_by(shipment_id=shipment.id)}
    org_ids.discard(exclude_org)
    org_ids.discard(None)
    return [u.id for u in db.query(User).filter(User.org_id.in_(org_ids or {0}))]


def org_of(db: Session, org_id: int | None) -> Organization | None:
    return db.get(Organization, org_id) if org_id else None
