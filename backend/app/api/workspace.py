import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.deps import WorkspaceCtx, get_workspace, raise_http
from app.api.orgs import make_invitation, send_invitation
from app.db import get_db
from app.email import service as mail
from app.models import AuditEvent, ChecklistItem, Comment, Invitation, Organization, ShipmentParticipant, User, utcnow
from app.services import checklist, eta, notify, timeline, tracking_service, workflow
from app.services.access import PARTY_ROLES, shipment_user_ids
from app.services.workflow import STAGE_LABELS, WorkflowError, progress

router = APIRouter(prefix="/shipments/{shipment_id}", tags=["workspace"])
PUBLIC_ACTIONS = {"timeline_updated", "tracking_refreshed", "created", "document_uploaded", "approved", "rejected", "participant_joined", "participant_removed", "checklist_uploaded", "checklist_requested", "checklist_reminder"}
CORE_OPEN_STAGES = ("draft", "documents", "extraction_review")
MAX_UPLOAD = 15 * 1024 * 1024


def _can_download(ctx: WorkspaceCtx, item: ChecklistItem) -> bool:
    return ctx.access == "owner" or item.party_role == ctx.party_role


@router.get("/workspace")
def workspace(ctx: WorkspaceCtx = Depends(get_workspace), db: Session = Depends(get_db)):
    s = ctx.shipment
    owner = db.get(Organization, s.org_id)
    parts = db.query(ShipmentParticipant).filter_by(shipment_id=s.id).all()

    def members(org_id):
        return [u.name for u in db.query(User).filter_by(org_id=org_id)]

    participants = [{"org_id": s.org_id, "org_name": owner.name if owner else "", "party_role": owner.type if owner else "broker", "owner": True, "members": members(s.org_id)}]
    for p in parts:
        org = db.get(Organization, p.org_id)
        participants.append({"org_id": p.org_id, "org_name": org.name if org else "", "party_role": p.party_role, "owner": False, "members": members(p.org_id)})
    items = db.query(ChecklistItem).filter_by(shipment_id=s.id).order_by(ChecklistItem.id).all()
    comments = db.query(Comment).filter_by(shipment_id=s.id).order_by(Comment.id).limit(200).all()
    events = [e for e in db.query(AuditEvent).filter_by(shipment_id=s.id).order_by(AuditEvent.id.desc()).limit(60) if e.action in PUBLIC_ACTIONS][:25]
    pending = []
    if ctx.access == "owner":
        pending = [{"id": i.id, "email": i.email, "party_role": i.party_role, "expires_at": i.expires_at.isoformat()} for i in db.query(Invitation).filter_by(shipment_id=s.id, kind="shipment", status="pending")]
    return {
        "shipment": {"id": s.id, "reference": s.reference, "importer": s.importer, "exporter": s.exporter, "origin": s.origin, "destination": s.destination, "port": s.port, "carrier": s.carrier,
                     "container_number": s.container_number, "product_description": s.product_description, "stage_label": STAGE_LABELS.get(s.stage, s.stage), "stage": s.stage, "progress": progress(s)},
        "access": ctx.access, "party_role": ctx.party_role, "owner_org": owner.name if owner else "",
        "participants": participants, "pending_invitations": pending,
        "checklist": [checklist.item_out(i, _can_download(ctx, i)) for i in items],
        "comments": [{"id": c.id, "author": c.author, "org_name": c.org_name, "party_role": c.party_role, "body": c.body, "created_at": c.created_at.isoformat(), "mine": c.user_id == ctx.user.id} for c in comments],
        "activity": [{"id": e.id, "actor": e.actor, "message": e.message, "created_at": e.created_at.isoformat()} for e in events],
        "timeline": timeline.timeline_out(db, s, ctx.access, ctx.party_role),
        "tracking": {**tracking_service.summary(s), "can_refresh": ctx.access == "owner" or ctx.party_role == "forwarder"},
        "eta": eta.estimate(db, s),
        "can_manage": ctx.access == "owner",
        "can_invite": ctx.access == "owner" and bool(ctx.user.email_verified),
    }


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


@router.post("/comments", status_code=201)
def add_comment(body: CommentIn, ctx: WorkspaceCtx = Depends(get_workspace), db: Session = Depends(get_db)):
    s, u = ctx.shipment, ctx.user
    org = db.get(Organization, u.org_id)
    role = org.type if ctx.access == "owner" else ctx.party_role
    db.add(Comment(shipment_id=s.id, user_id=u.id, author=u.name, org_name=org.name if org else "", party_role=role or "", body=body.body.strip()))
    audience = [uid for uid in shipment_user_ids(db, s) if uid != u.id]
    mentioned = set()
    handles = {m.lower() for m in re.findall(r"@([A-Za-z][A-Za-z.\-]{1,30})", body.body)}
    if handles:
        for other in db.query(User).filter(User.id.in_(audience or [0])):
            first, joined = other.name.split()[0].lower(), other.name.replace(" ", "").lower()
            if first in handles or joined in handles:
                mentioned.add(other.id)
    link = f"/shipments/{s.id}/workspace"
    notify.notify(db, mentioned, f"{u.name} mentioned you on {s.reference}", body.body[:200], kind="mention", shipment_id=s.id, link=link)
    notify.notify(db, [x for x in audience if x not in mentioned], f"New comment on {s.reference}", f"{u.name}: {body.body[:200]}", kind="comment", shipment_id=s.id, link=link)
    db.commit()
    return {"ok": True}


class InviteIn(BaseModel):
    email: EmailStr
    party_role: str


@router.post("/invitations", status_code=201)
def invite(body: InviteIn, ctx: WorkspaceCtx = Depends(get_workspace), db: Session = Depends(get_db)):
    if ctx.access != "owner":
        raise HTTPException(403, "Only the organisation that owns the shipment can invite partners.")
    if not ctx.user.email_verified:
        raise HTTPException(403, "Confirm your email address before inviting partners.")
    if body.party_role not in PARTY_ROLES:
        raise HTTPException(422, "Choose broker, forwarder, importer or exporter.")
    existing = db.query(User).filter(User.email == body.email.lower()).first()
    if existing and existing.org_id == ctx.shipment.org_id:
        raise HTTPException(409, "That person is already in your organisation and can see this shipment.")
    org = db.get(Organization, ctx.user.org_id)
    inv, link = make_invitation(db, kind="shipment", org=org, email=body.email, invited_by=ctx.user, shipment=ctx.shipment, party_role=body.party_role)
    result = send_invitation(db, inv, link, ctx.user, org, ctx.shipment)
    db.add(AuditEvent(shipment_id=ctx.shipment.id, actor=ctx.user.name, kind="human", action="checklist_requested", message=f"Invited {body.email.lower()} as {body.party_role}."))
    db.commit()
    return {"id": inv.id, "email": inv.email, "party_role": inv.party_role, "dev_link": result.get("dev_link")}


@router.delete("/participants/{org_id}")
def remove_participant(org_id: int, ctx: WorkspaceCtx = Depends(get_workspace), db: Session = Depends(get_db)):
    if ctx.access != "owner":
        raise HTTPException(403, "Only the owning organisation can remove a participant.")
    row = db.query(ShipmentParticipant).filter_by(shipment_id=ctx.shipment.id, org_id=org_id).first()
    if not row:
        raise HTTPException(404, "Participant not found.")
    org = db.get(Organization, org_id)
    db.delete(row)
    db.add(AuditEvent(shipment_id=ctx.shipment.id, actor=ctx.user.name, kind="human", action="participant_removed", message=f"Removed {org.name if org else 'a participant'} from the shipment."))
    db.commit()
    return {"ok": True}


class ItemIn(BaseModel):
    label: str = Field(min_length=2, max_length=160)
    party_role: str
    required: bool = True


@router.post("/checklist", status_code=201)
def add_item(body: ItemIn, ctx: WorkspaceCtx = Depends(get_workspace), db: Session = Depends(get_db)):
    if ctx.access != "owner":
        raise HTTPException(403, "Only the owning organisation can add requests.")
    if body.party_role not in PARTY_ROLES:
        raise HTTPException(422, "Choose broker, forwarder, importer or exporter.")
    n = db.query(ChecklistItem).filter_by(shipment_id=ctx.shipment.id).count()
    db.add(ChecklistItem(shipment_id=ctx.shipment.id, key=f"custom-{n + 1}", label=body.label.strip(), party_role=body.party_role, required=body.required))
    db.add(AuditEvent(shipment_id=ctx.shipment.id, actor=ctx.user.name, kind="human", action="checklist_requested", message=f"Requested '{body.label.strip()}' from the {body.party_role}."))
    db.commit()
    return {"ok": True}


def _item(db: Session, ctx: WorkspaceCtx, item_id: int) -> ChecklistItem:
    item = db.get(ChecklistItem, item_id)
    if not item or item.shipment_id != ctx.shipment.id:
        raise HTTPException(404, "Checklist item not found.")
    return item


@router.post("/checklist/{item_id}/upload")
async def upload(item_id: int, file: UploadFile = File(...), ctx: WorkspaceCtx = Depends(get_workspace), db: Session = Depends(get_db)):
    item = _item(db, ctx, item_id)
    if ctx.access == "partner" and item.party_role != ctx.party_role:
        raise HTTPException(403, f"This item is for the {item.party_role} to provide.")
    content = await file.read()
    if not content:
        raise HTTPException(422, "The file is empty.")
    if len(content) > MAX_UPLOAD:
        raise HTTPException(413, "File is larger than 15 MB.")
    s, u = ctx.shipment, ctx.user
    name = file.filename or "document"
    if item.doc_type:
        if ctx.access == "partner" and s.stage not in CORE_OPEN_STAGES:
            raise HTTPException(409, "Documents are locked once classification has started. Ask the broker to reopen the shipment.")
        try:
            workflow.add_document(db, s, item.doc_type, name, content, file.content_type, u.name)
        except WorkflowError as e:
            raise_http(e)
        item = db.get(ChecklistItem, item_id)
    else:
        item.status, item.filename, item.size_bytes = "uploaded", name, len(content)
        item.storage_path = workflow._save_file(s, name, content)
        item.uploaded_by, item.uploaded_at = u.name, utcnow()
    db.add(AuditEvent(shipment_id=s.id, actor=u.name, kind="human", action="checklist_uploaded", message=f"{u.name} uploaded {item.label} ({name})."))
    notify.notify(db, [x for x in shipment_user_ids(db, s) if x != u.id], f"{item.label} uploaded on {s.reference}", f"{u.name} provided {name}.", kind="upload", shipment_id=s.id, link=f"/shipments/{s.id}/workspace")
    db.commit()
    return {"ok": True}


@router.get("/checklist/{item_id}/file")
def download(item_id: int, ctx: WorkspaceCtx = Depends(get_workspace), db: Session = Depends(get_db)):
    item = _item(db, ctx, item_id)
    if not _can_download(ctx, item):
        raise HTTPException(403, "You can only download files assigned to your role.")
    if not item.storage_path or not Path(item.storage_path).exists():
        raise HTTPException(404, "No file is stored for this item.")
    return FileResponse(item.storage_path, filename=item.filename or "document")


@router.post("/checklist/{item_id}/remind")
def remind(item_id: int, ctx: WorkspaceCtx = Depends(get_workspace), db: Session = Depends(get_db)):
    if ctx.access != "owner":
        raise HTTPException(403, "Only the owning organisation can send reminders.")
    item = _item(db, ctx, item_id)
    if item.status == "uploaded":
        raise HTTPException(409, "This item has already been provided.")
    if item.last_reminder_at and (utcnow() - item.last_reminder_at.replace(tzinfo=utcnow().tzinfo)).total_seconds() < 3600:
        raise HTTPException(409, "A reminder was already sent in the last hour.")
    org_ids = [p.org_id for p in db.query(ShipmentParticipant).filter_by(shipment_id=ctx.shipment.id, party_role=item.party_role)]
    users = db.query(User).filter(User.org_id.in_(org_ids or [0])).all()
    if not users:
        raise HTTPException(409, f"No {item.party_role} has joined this shipment yet. Invite them first.")
    s = ctx.shipment
    link = f"{__import__('app.core.config', fromlist=['get_settings']).get_settings().app_url}/shipments/{s.id}/workspace"
    notify.notify(db, [u.id for u in users], f"{item.label} needed for {s.reference}", f"{ctx.user.name} is waiting for this document.", kind="reminder", shipment_id=s.id, link=f"/shipments/{s.id}/workspace")
    for u in users:
        mail.send(db, u.email, f"Reminder: {item.label} needed for {s.reference}", f"Hi {u.name},\n\n{ctx.user.name} is waiting for the {item.label} on shipment {s.reference}.\nUpload it here:\n{link}", link)
    item.last_reminder_at = utcnow()
    db.add(AuditEvent(shipment_id=s.id, actor=ctx.user.name, kind="human", action="checklist_reminder", message=f"Reminded the {item.party_role} to provide {item.label}."))
    db.commit()
    return {"notified": len(users)}
