from app.catalog import DOC_LABELS, REQUIRED_DOCS
from app.services import brief
from app.services.workflow import STAGE_LABELS, progress


def iso(dt):
    return dt.isoformat() if dt else None


def shipment_summary(s) -> dict:
    have = {d.doc_type for d in s.documents}
    return {
        "id": s.id,
        "reference": s.reference,
        "importer": s.importer,
        "exporter": s.exporter,
        "origin": s.origin,
        "destination": s.destination,
        "port": s.port,
        "carrier": s.carrier,
        "container_number": s.container_number,
        "product_description": s.product_description,
        "stage": s.stage,
        "stage_label": STAGE_LABELS.get(s.stage, s.stage),
        "progress": progress(s),
        "documents_count": len(have),
        "risk_score": s.risk["score"] if s.risk else None,
        "risk_level": s.risk["level"] if s.risk else None,
        "alerts": s.compliance["alert_count"] if s.compliance else 0,
        "hs_code": ((s.hs_decision or {}).get("code") or (s.hs_result or {}).get("code")),
        "is_demo": bool(s.is_demo),
        "access": "owner",
        "party_role": None,
        "shared_by": None,
        "open_requests": 0,
        "created_at": iso(s.created_at),
        "updated_at": iso(s.updated_at),
    }


def partner_summary(db, s, party_role: str) -> dict:
    """What a partner organisation may see in lists: no risk, HS or compliance data."""
    from app.models import ChecklistItem, Organization

    owner = db.get(Organization, s.org_id)
    open_items = db.query(ChecklistItem).filter_by(shipment_id=s.id, party_role=party_role, status="missing").count()
    out = shipment_summary(s)
    out.update({"risk_score": None, "risk_level": None, "alerts": 0, "hs_code": None, "access": "partner", "party_role": party_role, "shared_by": owner.name if owner else "", "open_requests": open_items})
    return out


def document_out(d) -> dict:
    return {
        "id": d.id,
        "doc_type": d.doc_type,
        "label": DOC_LABELS.get(d.doc_type, d.doc_type),
        "filename": d.filename,
        "size_bytes": d.size_bytes,
        "status": d.status,
        "fields": d.fields or [],
        "meta": d.meta or {},
        "created_at": iso(d.created_at),
    }


def event_out(e) -> dict:
    return {"id": e.id, "actor": e.actor, "kind": e.kind, "action": e.action, "message": e.message, "detail": e.detail, "created_at": iso(e.created_at)}


def eta_for(s) -> dict:
    from sqlalchemy.orm import object_session

    from app.services import eta

    db = object_session(s)
    return eta.estimate(db, s) if db is not None else {}


def verification_state(s) -> dict:
    from app.market.verify import availability

    return availability(s)


def shipment_detail(s) -> dict:
    return {
        **shipment_summary(s),
        "documents": [document_out(d) for d in s.documents],
        "missing_documents": [t for t in REQUIRED_DOCS if t not in {d.doc_type for d in s.documents}],
        "eta": eta_for(s),
        "intel": s.intel,
        "verification": verification_state(s),
        "hs_result": s.hs_result,
        "hs_decision": s.hs_decision,
        "compliance": s.compliance,
        "risk": s.risk,
        "brief": brief.build(s),
        "events": [event_out(e) for e in s.events],
        "analysis_runs": s.analysis_runs,
    }


def clearance_summary(s) -> dict:
    inv = {f["key"]: f["value"] for d in s.documents if d.doc_type == "commercial_invoice" for f in (d.fields or [])}
    pl = {f["key"]: f["value"] for d in s.documents if d.doc_type == "packing_list" for f in (d.fields or [])}
    bl = {f["key"]: f["value"] for d in s.documents if d.doc_type == "bill_of_lading" for f in (d.fields or [])}
    hs = s.hs_decision or {}
    approvals = [event_out(e) for e in s.events if e.kind == "human" and e.action in ("approved", "hs_approve", "hs_edit", "extraction_confirmed")]
    return {
        "reference": s.reference,
        "status": s.stage,
        "status_label": STAGE_LABELS.get(s.stage),
        "parties": {"importer": s.importer, "exporter": s.exporter},
        "route": {"origin": s.origin, "destination": s.destination, "port": s.port, "carrier": s.carrier, "container": s.container_number, "vessel": bl.get("vessel")},
        "goods": {
            "description": s.product_description,
            "quantity": inv.get("quantity") or pl.get("quantity"),
            "unit_price": inv.get("unit_price"),
            "total_value": inv.get("total_value"),
            "currency": inv.get("currency"),
            "gross_weight": pl.get("gross_weight") or bl.get("gross_weight"),
            "net_weight": pl.get("net_weight"),
            "country_of_origin": inv.get("country_of_origin") or s.origin,
        },
        "hs": {"code": hs.get("code"), "decision": hs.get("status"), "ai_code": (s.hs_result or {}).get("code"), "confidence": (s.hs_result or {}).get("confidence")},
        "compliance": {"review_status": (s.compliance or {}).get("review_status"), "open_items": [i["title"] + ": " + i["summary"] for i in (s.compliance or {}).get("items", []) if i["status"] in ("issue", "warn")], "certificates": (s.compliance or {}).get("certificates", [])},
        "risk": {"score": (s.risk or {}).get("score"), "label": (s.risk or {}).get("label")},
        "approvals": approvals,
        "disclaimer": "Prepared for internal clearance review. This summary has not been submitted to any customs authority, and the risk score is not a customs decision.",
    }
