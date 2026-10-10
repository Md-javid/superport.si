import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import current_user, get_shipment
from app.services import access
from app.core.config import get_settings
from app.db import SessionLocal, get_db
from app.intelligence.errors import IntelligenceError
from app.models import Shipment, Signal, User
from app.radar import service

router = APIRouter(prefix="/radar", tags=["radar"])
shipment_router = APIRouter(tags=["radar"])
log = logging.getLogger("superport.radar")


class ScanIn(BaseModel):
    force: bool = False


class ReviewIn(BaseModel):
    action: str  # acknowledge | dismiss
    note: str = ""


@router.post("/scan")
def scan(body: ScanIn, db: Session = Depends(get_db), _: User = Depends(current_user)):
    try:
        return service.scan(db, body.force)
    except IntelligenceError as exc:
        raise HTTPException(409, str(exc))


@router.get("/signals")
def signals(status: str = "active", db: Session = Depends(get_db), user: User = Depends(current_user)):
    return service.list_signals(db, status, None, access.accessible_ids(db, user), user.org_id)


@router.post("/signals/{signal_id}/review")
def review(signal_id: int, body: ReviewIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    sig = db.get(Signal, signal_id)
    if not sig:
        raise HTTPException(404, "Signal not found.")
    try:
        service.review(db, sig, body.action, body.note, user.name, user.org_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return service.signal_out(db, sig, access.accessible_ids(db, user), user.org_id)


@shipment_router.get("/shipments/{shipment_id}/signals")
def shipment_signals(shipment: Shipment = Depends(get_shipment), db: Session = Depends(get_db), user: User = Depends(current_user)):
    return service.list_signals(db, "active", shipment.id, {shipment.id}, user.org_id)


async def scheduler() -> None:
    """Optional background scans (RADAR_INTERVAL_MINUTES > 0). Failures are logged, never fatal."""
    minutes = get_settings().radar_interval_minutes
    while minutes > 0:
        await asyncio.sleep(minutes * 60)

        def _run():
            with SessionLocal() as db:
                return service.scan(db)

        try:
            log.info("radar scan: %s", await asyncio.to_thread(_run))
        except Exception as exc:  # noqa: BLE001
            log.warning("radar scan failed: %s", exc)
