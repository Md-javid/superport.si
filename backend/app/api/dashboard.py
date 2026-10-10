from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.builtin import registry
from app.ai.registry import ai_status
from app.api.deps import current_user
from app.catalog import REQUIRED_DOCS
from app.db import get_db
from app.services import access
from app.intelligence.status import status as intelligence_status
from app.models import Shipment, User
from app.services import serializers

router = APIRouter(tags=["dashboard"])

ACTIONS = {
    "documents": "Upload documents",
    "extraction_review": "Review extracted data",
    "hs_review": "Review HS code",
    "final_review": "Approve or reject",
}


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = access.owned_shipments(db, user)
    shared = [serializers.partner_summary(db, s, role) for s, role in access.shared_shipments(db, user)]
    active = [s for s in rows if s.stage not in ("ready", "rejected")]
    pending_docs = sum(len([t for t in REQUIRED_DOCS if t not in {d.doc_type for d in s.documents}]) for s in active)
    docs_shipments = sum(1 for s in active if len({d.doc_type for d in s.documents}) < 3)
    alerts = sum((s.compliance or {}).get("alert_count", 0) for s in active)
    high = [s for s in rows if s.risk and s.risk["level"] == "high" and s.stage != "rejected"]
    avg = round(sum(serializers.shipment_summary(s)["progress"] for s in active) / len(active)) if active else 0
    stage_counts = {k: 0 for k in ("documents", "extraction_review", "hs_review", "final_review", "ready")}
    for s in rows:
        key = "documents" if s.stage == "draft" else s.stage
        if key in stage_counts:
            stage_counts[key] += 1
    attention = []
    for s in active:
        item = serializers.shipment_summary(s)
        item["action"] = ACTIONS.get(s.stage, "Open")
        attention.append(item)
    attention.sort(key=lambda x: (-(x["risk_score"] or 0), x["reference"]))
    return {
        "kpis": {
            "active_shipments": len(active),
            "pending_documents": pending_docs,
            "pending_documents_shipments": docs_shipments,
            "compliance_alerts": alerts,
            "high_risk": len(high),
            "clearance_progress": avg,
        },
        "stage_counts": stage_counts,
        "recent": [serializers.shipment_summary(s) for s in rows[:6]],
        "shared": shared,
        "attention": attention[:4],
        "agents": registry.describe(),
        "ai": ai_status(),
        "intelligence": intelligence_status(),
    }
