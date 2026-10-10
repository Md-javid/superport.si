from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import WorkspaceCtx, current_user, get_workspace
from app.db import get_db
from app.models import AuditEvent, User
from app.services import control_tower, notify, timeline, tracking_service
from app.services.access import shipment_user_ids
from app.tracking.providers import TrackingNotConfigured

router = APIRouter(tags=["tracking"])


class TimelineIn(BaseModel):
    status: str | None = None
    planned_at: str | None = None
    actual_at: str | None = None
    note: str | None = Field(default=None, max_length=300)


@router.post("/shipments/{shipment_id}/timeline/{key}")
def update_timeline(key: str, body: TimelineIn, ctx: WorkspaceCtx = Depends(get_workspace), db: Session = Depends(get_db)):
    if key not in {k for k, _ in timeline.STEPS}:
        raise HTTPException(404, "Unknown timeline step.")
    if not timeline.can_update(key, ctx.access, ctx.party_role) and not (key == "customs_clearance" and ctx.access == "owner"):
        raise HTTPException(403, "Your role cannot update this step.")
    if key == "customs_clearance" and body.status not in (None, "pending", "delayed", "blocked"):
        raise HTTPException(422, "Customs clearance follows the broker's workflow. You can only record a delay or a hold.")
    if body.status in ("delayed", "blocked") and not (body.note or "").strip():
        raise HTTPException(422, "Add a short note explaining the delay or hold.")
    try:
        e = timeline.update_event(db, ctx.shipment, key, status=body.status, planned_at=body.planned_at, actual_at=body.actual_at, note=body.note, actor=ctx.user.name)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    s = ctx.shipment
    db.add(AuditEvent(shipment_id=s.id, actor=ctx.user.name, kind="human", action="timeline_updated", message=f"{ctx.user.name} updated '{e.label}'" + (f" to {body.status}." if body.status else ".")))
    notify.notify(db, [u for u in shipment_user_ids(db, s) if u != ctx.user.id], f"{s.reference}: {e.label}", f"{ctx.user.name} updated this step." + (f" {e.note}" if e.note else ""), kind="timeline", shipment_id=s.id, link=f"/shipments/{s.id}/workspace")
    db.commit()
    return {"ok": True}


@router.post("/shipments/{shipment_id}/tracking/refresh")
def refresh_tracking(ctx: WorkspaceCtx = Depends(get_workspace), db: Session = Depends(get_db)):
    if not (ctx.access == "owner" or ctx.party_role == "forwarder"):
        raise HTTPException(403, "Only the broker and the forwarder can refresh tracking.")
    try:
        out = tracking_service.refresh(db, ctx.shipment, ctx.user.name)
    except TrackingNotConfigured as exc:
        raise HTTPException(409, str(exc))
    db.commit()
    return out


@router.get("/control-tower")
def tower(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return control_tower.build(db, user)
