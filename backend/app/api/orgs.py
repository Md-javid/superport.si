import hashlib
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.config import get_settings
from app.db import get_db
from app.email import service as mail
from app.models import AuditEvent, Invitation, Notification, Organization, Shipment, ShipmentParticipant, User, utcnow

router = APIRouter(tags=["organisations"])


def make_invitation(db: Session, *, kind: str, org: Organization, email: str, invited_by: User, shipment: Shipment | None = None, party_role: str | None = None) -> tuple[Invitation, str]:
    email = email.lower().strip()
    for old in db.query(Invitation).filter_by(email=email, org_id=org.id, kind=kind, status="pending", shipment_id=shipment.id if shipment else None):
        old.status = "revoked"
    token = secrets.token_urlsafe(32)
    inv = Invitation(kind=kind, org_id=org.id, shipment_id=shipment.id if shipment else None, email=email, party_role=party_role, token_hash=hashlib.sha256(token.encode()).hexdigest(),
                     invited_by=invited_by.id, expires_at=utcnow() + timedelta(days=7))
    db.add(inv)
    db.flush()
    return inv, f"{get_settings().app_url}/invite/{token}"


def send_invitation(db: Session, inv: Invitation, link: str, inviter: User, org: Organization, shipment: Shipment | None) -> dict:
    what = f"the shipment {shipment.reference} as {inv.party_role}" if shipment else f"the {org.name} team"
    return mail.send(db, inv.email, f"{inviter.name} invited you to {what} on SuperPort", f"{inviter.name} from {org.name} invited you to join {what}.\n\nOpen your invitation:\n{link}\n\nThe link works for 7 days.", link)


def _find(db: Session, token: str) -> Invitation | None:
    return db.query(Invitation).filter_by(token_hash=hashlib.sha256(token.encode()).hexdigest()).first()


def _valid(inv: Invitation | None) -> bool:
    return bool(inv and inv.status == "pending" and inv.expires_at.replace(tzinfo=utcnow().tzinfo) > utcnow())


@router.get("/invitations/{token}")
def invitation_info(token: str, db: Session = Depends(get_db)):
    inv = _find(db, token)
    if not _valid(inv):
        raise HTTPException(410, "This invitation is no longer valid. Ask for a new one.")
    org = db.get(Organization, inv.org_id)
    shipment = db.get(Shipment, inv.shipment_id) if inv.shipment_id else None
    return {"kind": inv.kind, "email": inv.email, "inviter_org": org.name if org else "", "party_role": inv.party_role, "shipment_reference": shipment.reference if shipment else None, "expires_at": inv.expires_at.isoformat()}


@router.post("/invitations/{token}/accept")
def accept_invitation(token: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    inv = _find(db, token)
    if not _valid(inv):
        raise HTTPException(410, "This invitation is no longer valid. Ask for a new one.")
    if inv.email.lower() != user.email.lower():
        raise HTTPException(403, "This invitation was sent to a different email address.")
    if inv.kind != "shipment":
        raise HTTPException(409, "Team invitations are accepted by creating a new account from the invitation link.")
    if user.org_id == inv.org_id:
        raise HTTPException(409, "You already belong to the organisation that owns this shipment.")
    if not db.query(ShipmentParticipant).filter_by(shipment_id=inv.shipment_id, org_id=user.org_id).first():
        db.add(ShipmentParticipant(shipment_id=inv.shipment_id, org_id=user.org_id, party_role=inv.party_role, invited_by=inv.invited_by))
        db.add(AuditEvent(shipment_id=inv.shipment_id, actor=user.name, kind="human", action="participant_joined", message=f"{user.org.name} joined as {inv.party_role}."))
        if inv.invited_by:
            db.add(Notification(user_id=inv.invited_by, shipment_id=inv.shipment_id, kind="participant_joined", title=f"{user.org.name} joined the shipment", body=f"{user.name} accepted your invitation as {inv.party_role}.", link=f"/shipments/{inv.shipment_id}/workspace"))
    inv.status = "accepted"
    db.commit()
    return {"shipment_id": inv.shipment_id}


@router.get("/team")
def team(db: Session = Depends(get_db), user: User = Depends(current_user)):
    org = db.get(Organization, user.org_id)
    members = db.query(User).filter_by(org_id=user.org_id).order_by(User.id).all()
    pending = db.query(Invitation).filter_by(org_id=user.org_id, kind="team", status="pending").all()
    return {"org": {"id": org.id, "name": org.name, "type": org.type},
            "members": [{"id": m.id, "name": m.name, "email": m.email, "org_role": m.org_role, "email_verified": bool(m.email_verified)} for m in members],
            "invitations": [{"id": i.id, "email": i.email, "expires_at": i.expires_at.isoformat()} for i in pending if _valid(i)],
            "can_invite": user.org_role == "admin" and bool(user.email_verified)}


class TeamInviteIn(BaseModel):
    email: EmailStr


@router.post("/team/invitations", status_code=201)
def invite_teammate(body: TeamInviteIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.org_role != "admin":
        raise HTTPException(403, "Only organisation admins can invite teammates.")
    if not user.email_verified:
        raise HTTPException(403, "Confirm your email address before inviting people.")
    if db.query(User).filter(User.email == body.email.lower()).first():
        raise HTTPException(409, "That email already has a SuperPort account.")
    org = db.get(Organization, user.org_id)
    inv, link = make_invitation(db, kind="team", org=org, email=body.email, invited_by=user)
    result = send_invitation(db, inv, link, user, org, None)
    db.commit()
    return {"id": inv.id, "email": inv.email, "dev_link": result.get("dev_link")}


@router.get("/notifications")
def notifications(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.query(Notification).filter_by(user_id=user.id).order_by(Notification.id.desc()).limit(25).all()
    unread = db.query(Notification).filter_by(user_id=user.id, read=False).count()
    return {"unread": unread, "items": [{"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "link": n.link, "read": n.read, "created_at": n.created_at.isoformat(), "shipment_id": n.shipment_id} for n in rows]}


class ReadIn(BaseModel):
    ids: list[int] = Field(default_factory=list)


@router.post("/notifications/read")
def mark_read(body: ReadIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = db.query(Notification).filter_by(user_id=user.id, read=False)
    if body.ids:
        q = q.filter(Notification.id.in_(body.ids))
    q.update({"read": True}, synchronize_session=False)
    db.commit()
    return {"ok": True}
