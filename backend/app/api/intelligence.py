from fastapi import APIRouter, Depends

from app.api.deps import current_user, get_shipment
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.intelligence.evidence import list_evidence
from sqlalchemy import Integer

from app.models import ApiUsage, Evidence, Signal, utcnow
from app.services import access
from app.intelligence.status import status
from app.models import Shipment, User

router = APIRouter(tags=["intelligence"])


@router.get("/intelligence/status")
def intelligence_status(_: User = Depends(current_user)):
    return status()


@router.get("/shipments/{shipment_id}/evidence")
def shipment_evidence(shipment: Shipment = Depends(get_shipment)):
    return list_evidence(shipment.id)


FEATURES = [
    ("google", "Google Search", "HS code evidence, import rules lookup, tariff pages", "HS step, Compliance step"),
    ("google_shopping", "Google Shopping", "Live market prices for the invoice price check", "Risk factor: value anomaly"),
    ("google_maps", "Google Maps", "Does the importer and exporter have a real business listing?", "Counterparty check"),
    ("google_news", "Google News (Search with news mode)", "Adverse news on companies, and the Trade Signal Radar", "Radar, Counterparty check, ETA drivers"),
]


@router.get("/intelligence/serpapi")
def serpapi_showcase(db: Session = Depends(get_db), user: User = Depends(current_user)):
    from datetime import timedelta

    since = utcnow() - timedelta(days=30)
    usage = {k: (live, cached) for k, live, cached in ((r[0], r[1], r[2]) for r in db.query(ApiUsage.kind, func.sum((~ApiUsage.cached).cast(Integer)), func.sum(ApiUsage.cached.cast(Integer))).filter(ApiUsage.provider == "serpapi", ApiUsage.created_at >= since, ApiUsage.ok.is_(True)).group_by(ApiUsage.kind))}
    ids = access.accessible_ids(db, user)
    ev = dict(db.query(Evidence.kind, func.count(Evidence.id)).filter(Evidence.shipment_id.in_(ids or {0})).group_by(Evidence.kind).all())
    sources = db.query(Evidence).filter(Evidence.shipment_id.in_(ids or {0})).count()
    return {"features": [{"engine": e, "name": n, "what": w, "where": where, "searches": int((usage.get(e) or (0, 0))[0] or 0), "cached": int((usage.get(e) or (0, 0))[1] or 0)} for e, n, w, where in FEATURES],
            "evidence_by_kind": ev, "evidence_total": sources, "signals": db.query(Signal).count()}
