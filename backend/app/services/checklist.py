"""Document collection checklist: who must provide what, and whether it has arrived."""
from sqlalchemy.orm import Session

from app.models import ChecklistItem, Document, Shipment, utcnow

DEFAULTS = [
    ("commercial_invoice", "Commercial Invoice", "exporter", True, "commercial_invoice"),
    ("packing_list", "Packing List", "exporter", True, "packing_list"),
    ("bill_of_lading", "Bill of Lading", "forwarder", True, "bill_of_lading"),
    ("certificate_of_origin", "Certificate of Origin", "exporter", True, None),
    ("insurance", "Insurance Certificate", "importer", False, None),
]


def ensure_checklist(db: Session, shipment: Shipment) -> None:
    have = {i.key for i in db.query(ChecklistItem).filter_by(shipment_id=shipment.id)}
    for key, label, role, required, doc_type in DEFAULTS:
        if key not in have:
            db.add(ChecklistItem(shipment_id=shipment.id, key=key, label=label, party_role=role, required=required, doc_type=doc_type))
    db.flush()
    sync_from_documents(db, shipment)


def sync_from_documents(db: Session, shipment: Shipment, uploader: str = "") -> None:
    docs = {d.doc_type: d for d in db.query(Document).filter_by(shipment_id=shipment.id)}
    for item in db.query(ChecklistItem).filter_by(shipment_id=shipment.id):
        if not item.doc_type:
            continue
        doc = docs.get(item.doc_type)
        if doc and item.status != "uploaded":
            item.status, item.filename, item.size_bytes, item.storage_path = "uploaded", doc.filename, doc.size_bytes, doc.storage_path
            item.uploaded_by, item.uploaded_at = uploader or item.uploaded_by or "Broker", utcnow()
        elif doc:
            item.filename, item.size_bytes, item.storage_path = doc.filename, doc.size_bytes, doc.storage_path
            if uploader:
                item.uploaded_by, item.uploaded_at = uploader, utcnow()
        elif not doc and item.status == "uploaded":
            item.status, item.filename, item.storage_path = "missing", "", None


def item_out(i: ChecklistItem, can_download: bool) -> dict:
    return {"id": i.id, "key": i.key, "label": i.label, "party_role": i.party_role, "required": i.required, "status": i.status, "filename": i.filename,
            "size_bytes": i.size_bytes, "uploaded_by": i.uploaded_by, "uploaded_at": i.uploaded_at.isoformat() if i.uploaded_at else None,
            "last_reminder_at": i.last_reminder_at.isoformat() if i.last_reminder_at else None, "core": bool(i.doc_type), "can_download": can_download and bool(i.storage_path)}
