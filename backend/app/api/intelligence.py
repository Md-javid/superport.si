from fastapi import APIRouter, Depends

from app.api.deps import current_user, get_shipment
from app.intelligence.evidence import list_evidence
from app.intelligence.status import status
from app.models import Shipment, User

router = APIRouter(tags=["intelligence"])


@router.get("/intelligence/status")
def intelligence_status(_: User = Depends(current_user)):
    return status()


@router.get("/shipments/{shipment_id}/evidence")
def shipment_evidence(shipment: Shipment = Depends(get_shipment)):
    return list_evidence(shipment.id)
