from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import current_user, get_shipment, raise_http
from app.db import get_db
from app.models import Document, Shipment, User
from app.schemas import DecisionIn, FieldEdit, HsReviewIn, InconsistencyActionIn, ShipmentIn, ShipmentUpdateIn
from app.services import serializers, workflow
from app.services.workflow import WorkflowError

router = APIRouter(prefix="/shipments", tags=["shipments"])
MAX_UPLOAD = 15 * 1024 * 1024


def _detail(db: Session, shipment: Shipment) -> dict:
    db.refresh(shipment)
    return serializers.shipment_detail(shipment)


@router.get("")
def list_shipments(db: Session = Depends(get_db), user: User = Depends(current_user)):
    from app.services import access

    owned = [serializers.shipment_summary(s) for s in access.owned_shipments(db, user)]
    shared = [serializers.partner_summary(db, s, role) for s, role in access.shared_shipments(db, user)]
    return sorted(owned + shared, key=lambda x: x["updated_at"], reverse=True)


@router.post("", status_code=201)
def create(body: ShipmentIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    try:
        shipment = workflow.create_shipment(db, body.model_dump(), user)
    except WorkflowError as e:
        raise_http(e)
    return _detail(db, shipment)


@router.get("/{shipment_id}")
def detail(shipment: Shipment = Depends(get_shipment), db: Session = Depends(get_db)):
    return _detail(db, shipment)


@router.patch("/{shipment_id}")
def update_shipment(body: ShipmentUpdateIn, shipment: Shipment = Depends(get_shipment), db: Session = Depends(get_db), user: User = Depends(current_user)):
    try:
        workflow.update_shipment_details(db, shipment, body.model_dump(exclude_unset=True), user.name)
    except WorkflowError as e:
        raise_http(e)
    return _detail(db, shipment)


@router.post("/{shipment_id}/inconsistencies/resolve")
def resolve_inconsistency(body: InconsistencyActionIn, shipment: Shipment = Depends(get_shipment), db: Session = Depends(get_db), user: User = Depends(current_user)):
    try:
        workflow.resolve_inconsistency_action(db, shipment, body.action, body.field, body.chosen_value, body.doc_name, body.note, user.name)
    except WorkflowError as e:
        raise_http(e)
    return _detail(db, shipment)


@router.post("/{shipment_id}/reconcile")
def reconcile(shipment: Shipment = Depends(get_shipment), db: Session = Depends(get_db), user: User = Depends(current_user)):
    try:
        workflow.resolve_inconsistency_action(db, shipment, "resolve_all", None, None, None, None, user.name)
    except WorkflowError as e:
        raise_http(e)
    return _detail(db, shipment)


@router.post("/{shipment_id}/documents")
async def upload_document(
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    shipment: Shipment = Depends(get_shipment),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    content = await file.read()
    if len(content) > MAX_UPLOAD:
        raise HTTPException(413, "File is larger than 15 MB.")
    try:
        workflow.add_document(db, shipment, doc_type, file.filename or "document", content, file.content_type, user.name)
    except WorkflowError as e:
        raise_http(e)
    return _detail(db, shipment)


@router.post("/{shipment_id}/documents/samples")
def use_samples(shipment: Shipment = Depends(get_shipment), db: Session = Depends(get_db), user: User = Depends(current_user)):
    try:
        workflow.attach_samples(db, shipment, user.name)
    except WorkflowError as e:
        raise_http(e)
    return _detail(db, shipment)


@router.post("/{shipment_id}/process")
def process(shipment: Shipment = Depends(get_shipment), db: Session = Depends(get_db)):
    try:
        workflow.process_documents(db, shipment)
    except WorkflowError as e:
        raise_http(e)
    return _detail(db, shipment)


@router.patch("/{shipment_id}/documents/{doc_id}/fields/{key}")
def edit_field(doc_id: int, key: str, body: FieldEdit, shipment: Shipment = Depends(get_shipment), db: Session = Depends(get_db), user: User = Depends(current_user)):
    doc = db.get(Document, doc_id)
    if not doc or doc.shipment_id != shipment.id:
        raise HTTPException(404, "Document not found.")
    try:
        workflow.update_field(db, shipment, doc, key, body.value, user.name)
    except WorkflowError as e:
        raise_http(e)
    return _detail(db, shipment)


@router.post("/{shipment_id}/extraction/confirm")
def confirm(shipment: Shipment = Depends(get_shipment), db: Session = Depends(get_db), user: User = Depends(current_user)):
    try:
        workflow.confirm_extraction(db, shipment, user.name)
    except WorkflowError as e:
        raise_http(e)
    return _detail(db, shipment)


@router.post("/{shipment_id}/hs/review")
def hs_review(body: HsReviewIn, shipment: Shipment = Depends(get_shipment), db: Session = Depends(get_db), user: User = Depends(current_user)):
    try:
        workflow.review_hs(db, shipment, body.action, body.hs_code, body.note, user.name)
    except WorkflowError as e:
        raise_http(e)
    return _detail(db, shipment)


@router.post("/{shipment_id}/decision")
def decision(body: DecisionIn, shipment: Shipment = Depends(get_shipment), db: Session = Depends(get_db), user: User = Depends(current_user)):
    try:
        workflow.final_decision(db, shipment, body.action, body.note, user.name)
    except WorkflowError as e:
        raise_http(e)
    return _detail(db, shipment)


@router.get("/{shipment_id}/summary")
def summary(shipment: Shipment = Depends(get_shipment)):
    return serializers.clearance_summary(shipment)
