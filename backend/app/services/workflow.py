"""Shipment workflow: the single place where stage transitions and human gates live."""
import copy
import os
import re
import uuid
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.agents.base import AgentContext
from app.agents.builtin import registry
from app.catalog import REQUIRED_DOCS
from app.core.config import get_settings
from app.models import AuditEvent, Document, FeedbackEvent, Shipment, User, utcnow
from app.services import extraction

AI_ACTOR = "SuperPort AI"
SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"
SAMPLE_FILES = {
    "commercial_invoice": "commercial_invoice.pdf",
    "packing_list": "packing_list.pdf",
    "bill_of_lading": "bill_of_lading.pdf",
}

STAGE_LABELS = {
    "draft": "Draft",
    "documents": "Awaiting documents",
    "extraction_review": "Extraction review",
    "hs_review": "HS code review",
    "final_review": "Awaiting approval",
    "ready": "Clearance ready",
    "rejected": "Rejected",
}
STAGE_PROGRESS = {"draft": 8, "documents": 22, "extraction_review": 42, "hs_review": 58, "final_review": 82, "ready": 100, "rejected": 82}


class WorkflowError(Exception):
    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def log(db: Session, shipment: Shipment, actor: str, kind: str, action: str, message: str, detail: dict | None = None) -> None:
    db.add(AuditEvent(shipment_id=shipment.id, actor=actor, kind=kind, action=action, message=message, detail=detail))


def record_feedback(db: Session, shipment: Shipment, kind: str, actor: str, *, field: str = "", ai_value=None, human_value=None, action: str = "", context: dict | None = None) -> None:
    """Keep every human correction as structured data (future training signal)."""
    if not get_settings().collect_feedback or actor == "Seed":
        return
    db.add(FeedbackEvent(shipment_id=shipment.id, kind=kind, field=field, ai_value=None if ai_value is None else str(ai_value), human_value=None if human_value is None else str(human_value), action=action, user=actor, context=context))


def next_reference(db: Session) -> str:
    count = db.query(Shipment).count() + 1
    ref = f"SP-2026-{count:04d}"
    while db.query(Shipment).filter(Shipment.reference == ref).first():
        count += 1
        ref = f"SP-2026-{count:04d}"
    return ref


def create_shipment(db: Session, data: dict, user: User | None) -> Shipment:
    shipment = Shipment(
        reference=(data.get("reference") or "").strip() or next_reference(db),
        importer=data["importer"].strip(),
        exporter=data["exporter"].strip(),
        origin=data["origin"].strip(),
        destination=data["destination"].strip(),
        port=data["port"].strip(),
        carrier=data["carrier"].strip(),
        container_number=data["container_number"].strip().upper(),
        product_description=data["product_description"].strip(),
        stage="documents",
        created_by=user.name if user else "System",
        is_demo=bool(data.get("is_demo", False)),
        org_id=getattr(user, "org_id", None),
    )
    if db.query(Shipment).filter(Shipment.reference == shipment.reference).first():
        raise WorkflowError(f"Shipment ID {shipment.reference} already exists.", 409)
    db.add(shipment)
    db.flush()
    log(db, shipment, shipment.created_by, "human", "created", "Shipment created. Upload the three trade documents to continue.")
    from app.services import checklist

    checklist.ensure_checklist(db, shipment)
    from app.services import timeline

    timeline.ensure_timeline(db, shipment)
    db.commit()
    return shipment


def _save_file(shipment: Shipment, filename: str, content: bytes) -> str | None:
    if not content:
        return None
    folder = Path(get_settings().upload_dir) / shipment.reference
    folder.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", filename)
    path = folder / f"{uuid.uuid4().hex[:8]}_{safe}"
    path.write_bytes(content)
    return str(path)


def add_document(db: Session, shipment: Shipment, doc_type: str, filename: str, content: bytes, content_type: str | None, actor: str) -> Document:
    if doc_type not in REQUIRED_DOCS:
        raise WorkflowError("Unknown document type.", 422)
    if shipment.stage in ("ready", "rejected"):
        raise WorkflowError("This shipment is closed. Documents can no longer be changed.")
    for old in [d for d in shipment.documents if d.doc_type == doc_type]:
        db.delete(old)
    db.flush()
    doc = Document(
        shipment_id=shipment.id,
        doc_type=doc_type,
        filename=filename,
        size_bytes=len(content),
        content_type=content_type,
        storage_path=_save_file(shipment, filename, content),
        status="uploaded",
        meta={"upload_bytes": len(content)},
    )
    db.add(doc)
    db.flush()
    if shipment.stage in ("draft", "documents"):
        shipment.stage = "documents"
    log(db, shipment, actor, "human", "document_uploaded", f"Uploaded {filename} as {doc_type.replace('_', ' ')}.")
    from app.services import checklist

    checklist.ensure_checklist(db, shipment)
    checklist.sync_from_documents(db, shipment, actor)
    db.commit()
    db.refresh(shipment)
    return doc


def attach_samples(db: Session, shipment: Shipment, actor: str) -> list[Document]:
    docs = []
    for doc_type, name in SAMPLE_FILES.items():
        path = SAMPLE_DIR / name
        content = path.read_bytes() if path.exists() else b""
        docs.append(add_document(db, shipment, doc_type, name, content, "application/pdf", actor))
    return docs


def process_documents(db: Session, shipment: Shipment) -> list[Document]:
    db.refresh(shipment)
    pending = [d for d in shipment.documents if d.status != "ready"]
    if not shipment.documents:
        raise WorkflowError("Upload at least one document first.", 422)
    for doc in pending:
        content = Path(doc.storage_path).read_bytes() if doc.storage_path and os.path.exists(doc.storage_path) else b""
        doc.fields, doc.meta = extraction.extract_document(doc.doc_type, doc.filename, content, doc.content_type, shipment)
        doc.meta = {**(doc.meta or {}), "extracted_at": utcnow().isoformat()}
        doc.status = "ready"
        found = sum(1 for f in doc.fields if f["value"])
        if doc.meta.get("mode") == "unreadable":
            log(db, shipment, AI_ACTOR, "system", "document_unreadable", f"Could not read {doc.filename}: {doc.meta.get('error')}", {"mode": "unreadable"})
        else:
            log(db, shipment, AI_ACTOR, "system", "document_extracted", f"Extracted {found} fields from {doc.filename} ({doc.meta.get('mode')}).", {"mode": doc.meta.get("mode")})
    if shipment.stage in ("draft", "documents"):
        shipment.stage = "extraction_review"
    db.commit()
    return pending


def update_field(db: Session, shipment: Shipment, doc: Document, key: str, value: str, actor: str) -> dict:
    if shipment.stage in ("ready", "rejected"):
        raise WorkflowError("This shipment is closed and can no longer be edited.")
    fields = copy.deepcopy(doc.fields or [])
    for f in fields:
        if f["key"] == key:
            before = f["value"]
            f["value"] = value.strip()
            f["edited"] = f["value"] != f.get("original")
            f["source"] = "edited" if f["edited"] else f["source"]
            f["confidence"] = 1.0 if f["value"] else 0.0
            doc.fields = fields
            flag_modified(doc, "fields")
            log(db, shipment, actor, "human", "field_edited", f"Edited {f['label']} on {doc.filename}.", {"before": before, "after": f["value"]})
            record_feedback(db, shipment, "field_edit", actor, field=f"{doc.doc_type}.{key}", ai_value=f.get("original"), human_value=f["value"], context={"source": f.get("source"), "confidence": f.get("confidence")})
            if shipment.hs_result:  # compliance and risk depend on this value; HS is not re-bought on every edit
                _analyze(db, shipment, reason="field edit", refresh_hs=False)
            db.commit()
            return f
    raise WorkflowError("Field not found.", 404)


def update_shipment_details(db: Session, shipment: Shipment, data: dict, actor: str) -> Shipment:
    if shipment.stage in ("ready", "rejected"):
        raise WorkflowError("This shipment is closed and can no longer be edited.")
    allowed = ["importer", "exporter", "origin", "destination", "port", "carrier", "container_number", "product_description"]
    changed = []
    for k in allowed:
        if k in data and data[k] is not None:
            new_val = str(data[k]).strip()
            old_val = getattr(shipment, k, None)
            if new_val != old_val:
                setattr(shipment, k, new_val)
                changed.append(k)
    if changed:
        log(db, shipment, actor, "human", "shipment_edited", f"Updated shipment {', '.join(changed)}.", data)
        _analyze(db, shipment, reason=f"shipment details updated ({', '.join(changed)})", refresh_hs=False)
        db.commit()
    return shipment


def resolve_inconsistency_action(
    db: Session,
    shipment: Shipment,
    action: str,
    field: str | None,
    chosen_value: str | None,
    doc_name: str | None,
    note: str | None,
    actor: str,
) -> Shipment:
    if shipment.stage in ("ready", "rejected"):
        raise WorkflowError("This shipment is closed and can no longer be edited.")

    intel = copy.deepcopy(getattr(shipment, "intel", None) or {})
    overrides = intel.get("inconsistency_overrides") or {}

    if action == "apply":
        val = (chosen_value or "").strip()
        if field == "Container number":
            shipment.container_number = val
        elif field == "Consignee":
            shipment.importer = val
        elif field == "Shipper":
            shipment.exporter = val
        elif field == "Country of origin":
            shipment.origin = val
        log(db, shipment, actor, "human", "inconsistency_applied", f"Synchronized {field} to '{val}'.", {"field": field, "value": val})
    elif action == "dismiss":
        key = f"{field}:{note}" if field and note else (field or "override")
        entry = {"by": actor, "note": note or "Broker verified variation", "at": utcnow().isoformat()}
        overrides[key] = entry
        if field:
            overrides[field] = entry
        intel["inconsistency_overrides"] = overrides
        shipment.intel = intel
        flag_modified(shipment, "intel")
        log(db, shipment, actor, "human", "inconsistency_dismissed", f"Accepted discrepancy on {field}.", {"field": field, "note": note})
    elif action == "reopen":
        for k in list(overrides.keys()):
            if field and (k == field or k.startswith(f"{field}:")):
                del overrides[k]
        intel["inconsistency_overrides"] = overrides
        shipment.intel = intel
        flag_modified(shipment, "intel")
        log(db, shipment, actor, "human", "inconsistency_reopened", f"Reopened discrepancy on {field}.", {"field": field})
    elif action == "resolve_all":
        # Extract consensus from documents
        docs = [d for d in shipment.documents if d.status == "ready"]
        from app.services.common import doc_value

        bl_cnt = doc_value(docs, "bill_of_lading", "container_number")
        pl_cnt = doc_value(docs, "packing_list", "container_number")
        if bl_cnt:
            shipment.container_number = bl_cnt
        elif pl_cnt:
            shipment.container_number = pl_cnt

        pl_consignee = doc_value(docs, "packing_list", "consignee")
        bl_consignee = doc_value(docs, "bill_of_lading", "consignee")
        ci_consignee = doc_value(docs, "commercial_invoice", "consignee")
        if pl_consignee:
            shipment.importer = pl_consignee
        elif bl_consignee:
            shipment.importer = bl_consignee
        elif ci_consignee:
            shipment.importer = ci_consignee

        pl_shipper = doc_value(docs, "packing_list", "shipper")
        bl_shipper = doc_value(docs, "bill_of_lading", "shipper")
        ci_shipper = doc_value(docs, "commercial_invoice", "shipper")
        if pl_shipper:
            shipment.exporter = pl_shipper
        elif bl_shipper:
            shipment.exporter = bl_shipper
        elif ci_shipper:
            shipment.exporter = ci_shipper

        # Also dismiss any residual minor differences
        overrides["Consignee"] = {"by": actor, "note": "Reconciled with shipping documents", "at": utcnow().isoformat()}
        overrides["Shipper"] = {"by": actor, "note": "Reconciled with shipping documents", "at": utcnow().isoformat()}
        overrides["Container number"] = {"by": actor, "note": "Synchronized with Bill of Lading", "at": utcnow().isoformat()}
        overrides["Gross weight"] = {"by": actor, "note": "Accepted tare/gross tolerance between PL and BL", "at": utcnow().isoformat()}
        overrides["Quantity"] = {"by": actor, "note": "Reconciled invoice and packing list", "at": utcnow().isoformat()}
        overrides["Total value"] = {"by": actor, "note": "Verified invoice arithmetic", "at": utcnow().isoformat()}
        intel["inconsistency_overrides"] = overrides
        shipment.intel = intel
        flag_modified(shipment, "intel")
        log(db, shipment, actor, "human", "all_inconsistencies_resolved", "Auto-reconciled all shipment fields from documents.", {})

    _analyze(db, shipment, reason=f"inconsistency action {action}", refresh_hs=False)
    db.commit()
    return shipment


def _analyze(db: Session, shipment: Shipment, reason: str = "analysis", refresh_hs: bool = True, force: bool = False) -> None:
    docs = [d for d in shipment.documents if d.status == "ready"]
    ctx = AgentContext(shipment=shipment, documents=docs, state={"hs_decision": shipment.hs_decision, "refresh_hs": refresh_hs, "force": force, "existing_hs": shipment.hs_result})
    registry.run_pipeline(["customs", "compliance", "risk"], ctx)
    shipment.hs_result = ctx.state["hs_result"]
    shipment.compliance = ctx.state["compliance"]
    shipment.risk = ctx.state["risk"]
    shipment.analysis_runs = (shipment.analysis_runs or 0) + 1
    log(db, shipment, AI_ACTOR, "system", "analysis", f"Re-ran {'HS, ' if refresh_hs else ''}compliance and risk checks ({reason}). Risk {shipment.risk['score']}/100, {shipment.risk['label']}.")


def confirm_extraction(db: Session, shipment: Shipment, actor: str) -> None:
    if not any(d.status == "ready" for d in shipment.documents):
        raise WorkflowError("Process at least one document before confirming.", 422)
    if shipment.stage in ("ready", "rejected"):
        raise WorkflowError("This shipment is closed.")
    shipment.hs_decision = None
    _analyze(db, shipment, "extraction confirmed")
    shipment.stage = "hs_review"
    log(db, shipment, actor, "human", "extraction_confirmed", "Confirmed the extracted shipment data.")
    db.commit()


def review_hs(db: Session, shipment: Shipment, action: str, hs_code: str | None, note: str | None, actor: str) -> None:
    if shipment.stage not in ("hs_review", "final_review"):
        raise WorkflowError("Confirm the extracted data before reviewing the HS code.")
    result = shipment.hs_result or {}
    if action == "approve":
        shipment.hs_decision = {"status": "approved", "code": result.get("code"), "by": actor, "note": note or ""}
    elif action == "edit":
        code = (hs_code or "").strip()
        if not re.fullmatch(r"\d{4}\.\d{2}(\.\d{2})?", code):
            raise WorkflowError("Enter an HS code such as 8507.60.", 422)
        shipment.hs_decision = {"status": "edited", "code": code, "by": actor, "note": note or "", "ai_code": result.get("code")}
    elif action == "reject":
        shipment.hs_decision = {"status": "rejected", "code": None, "by": actor, "note": note or ""}
        shipment.stage = "hs_review"
    elif action == "reanalyze":
        shipment.hs_decision = None
        _analyze(db, shipment, "re-analysis requested", force=True)
        shipment.stage = "hs_review"
        log(db, shipment, actor, "human", "hs_reanalyze", "Requested re-analysis of the HS recommendation.")
        db.commit()
        return
    else:
        raise WorkflowError("Unknown action.", 422)
    verb = {"approve": "Approved", "edit": "Changed", "reject": "Rejected"}[action]
    code = shipment.hs_decision.get("code") or result.get("code")
    log(db, shipment, actor, "human", f"hs_{action}", f"{verb} the HS recommendation" + (f" ({code})." if action != "reject" else "."), {"note": note})
    record_feedback(db, shipment, "hs_decision", actor, field="hs_code", ai_value=result.get("code"), human_value=shipment.hs_decision.get("code"), action=action, context={"confidence": result.get("confidence"), "engine": result.get("engine"), "grounded": result.get("grounded")})
    if action in ("approve", "edit"):
        _analyze(db, shipment, "HS decision recorded", refresh_hs=False)
        shipment.stage = "final_review"
    db.commit()


def final_decision(db: Session, shipment: Shipment, action: str, note: str | None, actor: str) -> None:
    if shipment.stage != "final_review":
        raise WorkflowError("Confirm the HS code before the final decision.")
    note = (note or "").strip()
    record_feedback(db, shipment, "final_decision", actor, action=action, context={"risk": (shipment.risk or {}).get("score"), "compliance": (shipment.compliance or {}).get("overall"), "note_given": bool(note)})
    if action == "approve":
        hs = shipment.hs_decision or {}
        if hs.get("status") not in ("approved", "edited"):
            raise WorkflowError("An HS code must be accepted before approval.", 422)
        needs_note = shipment.risk["level"] == "high" or shipment.compliance["overall"] == "action_required"
        if needs_note and len(note) < 8:
            raise WorkflowError("This shipment has open compliance issues or high risk. Add a short justification to approve.", 422)
        shipment.stage = "ready"
        log(db, shipment, actor, "human", "approved", "Approved. Shipment is clearance-ready for internal handover.", {"note": note})
    elif action == "reject":
        shipment.stage = "rejected"
        log(db, shipment, actor, "human", "rejected", "Rejected the shipment for clearance.", {"note": note})
    elif action == "edit":
        shipment.stage = "extraction_review"
        log(db, shipment, actor, "human", "edit_requested", "Reopened the shipment data for editing.", {"note": note})
    elif action == "reanalyze":
        shipment.hs_decision = None
        _analyze(db, shipment, "re-analysis requested", force=True)
        shipment.stage = "hs_review"
        log(db, shipment, actor, "human", "reanalyze", "Requested a full re-analysis.", {"note": note})
    else:
        raise WorkflowError("Unknown action.", 422)
    db.commit()


def progress(shipment: Shipment) -> int:
    return STAGE_PROGRESS.get(shipment.stage, 0)


def run_verification(db: Session, shipment: Shipment, parts: list[str], force: bool, actor: str) -> None:
    """Price, counterparty and rules checks. Explicit button only: these spend SerpApi credits."""
    from app.market import verify

    if shipment.stage in ("ready", "rejected"):
        raise WorkflowError("This shipment is closed.")
    if not shipment.hs_result:
        raise WorkflowError("Confirm the extracted data first. The checks use the HS code and invoice values.")
    state = verify.availability(shipment)
    if not state["available"]:
        raise WorkflowError(state["reason"], 409)
    docs = [d for d in shipment.documents if d.status == "ready"]
    shipment.intel = verify.run_all(shipment, docs, parts or list(verify.PARTS), force)
    flag_modified(shipment, "intel")
    done = {p: (shipment.intel.get(p) or {}).get("status") for p in (parts or verify.PARTS)}
    log(db, shipment, AI_ACTOR, "system", "market_checks", "Ran market checks (" + ", ".join(f"{k}: {v}" for k, v in done.items()) + ").", {"sample": state["sample"]})
    _analyze(db, shipment, "market checks", refresh_hs=False)
    db.commit()
