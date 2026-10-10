from app.db import SessionLocal
from app.models import Evidence, utcnow


def replace_evidence(shipment_id: int, kind: str, rows: list[dict]) -> None:
    """Replace this shipment's evidence of one kind with fresh rows."""
    with SessionLocal() as db:
        db.query(Evidence).filter_by(shipment_id=shipment_id, kind=kind).delete()
        for r in rows:
            db.add(Evidence(shipment_id=shipment_id, kind=kind, engine=r.get("engine", "google"), query=r.get("query", ""), title=r.get("title", ""), url=r.get("url", ""), snippet=r.get("snippet", ""), trust=r.get("trust", "web"), source_mode=r.get("source_mode", "live"), extra=r.get("extra"), retrieved_at=utcnow()))
        db.commit()


def list_evidence(shipment_id: int) -> list[dict]:
    with SessionLocal() as db:
        rows = db.query(Evidence).filter_by(shipment_id=shipment_id).order_by(Evidence.id).all()
        return [{"id": r.id, "kind": r.kind, "engine": r.engine, "query": r.query, "title": r.title, "url": r.url, "snippet": r.snippet, "trust": r.trust, "source_mode": r.source_mode, "retrieved_at": r.retrieved_at.isoformat()} for r in rows]
