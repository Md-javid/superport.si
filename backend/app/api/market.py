from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import current_user, get_shipment, raise_http
from app.api.shipments import _detail
from app.db import get_db
from app.models import Shipment, User
from app.services import workflow
from app.services.workflow import WorkflowError

router = APIRouter(tags=["market"])


class VerifyIn(BaseModel):
    parts: list[str] = ["price", "company", "rules"]
    force: bool = False


@router.post("/shipments/{shipment_id}/verify")
def verify(body: VerifyIn, shipment: Shipment = Depends(get_shipment), db: Session = Depends(get_db), user: User = Depends(current_user)):
    try:
        workflow.run_verification(db, shipment, body.parts, body.force, user.name)
    except WorkflowError as e:
        raise_http(e)
    return _detail(db, shipment)
