from dataclasses import dataclass

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db import get_db
from app.models import Shipment, User
from app.services.access import access_for
from app.services.workflow import WorkflowError

bearer = HTTPBearer(auto_error=False)


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not creds:
        raise HTTPException(401, "Sign in to continue.")
    user_id = decode_access_token(creds.credentials)
    user = db.get(User, user_id) if user_id else None
    if not user:
        raise HTTPException(401, "Your session has expired. Sign in again.")
    return user


def get_shipment(shipment_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)) -> Shipment:
    """Owner-only: full workflow, AI findings, risk. Partners use the workspace endpoints instead."""
    shipment = db.get(Shipment, shipment_id)
    kind, _ = access_for(db, user, shipment) if shipment else (None, None)
    if kind is None:
        raise HTTPException(404, "Shipment not found.")
    if kind == "partner":
        raise HTTPException(403, "This shipment is shared with you. Open its workspace instead.")
    return shipment


@dataclass
class WorkspaceCtx:
    shipment: Shipment
    user: User
    access: str  # owner | partner
    party_role: str | None


def get_workspace(shipment_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)) -> WorkspaceCtx:
    shipment = db.get(Shipment, shipment_id)
    kind, role = access_for(db, user, shipment) if shipment else (None, None)
    if kind is None:
        raise HTTPException(404, "Shipment not found.")
    return WorkspaceCtx(shipment, user, kind, role)


def raise_http(err: WorkflowError):
    raise HTTPException(err.status_code, err.message)
