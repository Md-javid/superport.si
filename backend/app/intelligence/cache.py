"""Response cache, usage log and budget counters (stored in the app database)."""
import hashlib
import json
from datetime import timedelta

from sqlalchemy import func

from app.db import SessionLocal
from app.models import ApiCache, ApiUsage, utcnow


def make_key(provider: str, payload: dict) -> str:
    raw = json.dumps({"p": provider, "d": payload}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def cache_get(provider: str, key: str, ttl_hours: int) -> dict | None:
    with SessionLocal() as db:
        row = db.get(ApiCache, key)
        if not row:
            return None
        created = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=utcnow().tzinfo)
        if utcnow() - created > timedelta(hours=ttl_hours):
            return None
        return row.response


def cache_put(provider: str, key: str, request: dict, response: dict) -> None:
    with SessionLocal() as db:
        row = db.get(ApiCache, key)
        if row:
            row.response, row.request, row.created_at = response, request, utcnow()
        else:
            db.add(ApiCache(key=key, provider=provider, request=request, response=response))
        db.commit()


def log_usage(provider: str, kind: str, shipment_id: int | None, *, cached: bool = False, ok: bool = True, tokens_in: int = 0, tokens_out: int = 0, detail: str = "") -> None:
    with SessionLocal() as db:
        db.add(ApiUsage(provider=provider, kind=kind, shipment_id=shipment_id, cached=cached, ok=ok, tokens_in=tokens_in, tokens_out=tokens_out, detail=detail[:500]))
        db.commit()


def billable_calls(provider: str, shipment_id: int) -> int:
    """Live, successful, non-cached calls already made for this shipment."""
    with SessionLocal() as db:
        return db.query(ApiUsage).filter_by(provider=provider, shipment_id=shipment_id, cached=False, ok=True).count()


def usage_summary(days: int = 30) -> dict:
    since = utcnow() - timedelta(days=days)
    out: dict = {}
    with SessionLocal() as db:
        for provider in ("serpapi", "gemini"):
            q = db.query(ApiUsage).filter(ApiUsage.provider == provider, ApiUsage.created_at >= since)
            live = q.filter_by(cached=False, ok=True).count()
            cached = q.filter_by(cached=True).count()
            failed = q.filter_by(ok=False).count()
            tin, tout = db.query(func.coalesce(func.sum(ApiUsage.tokens_in), 0), func.coalesce(func.sum(ApiUsage.tokens_out), 0)).filter(ApiUsage.provider == provider, ApiUsage.created_at >= since).one()
            out[provider] = {"live_calls": live, "cache_hits": cached, "failed": failed, "tokens_in": int(tin), "tokens_out": int(tout)}
    return out


def live_calls_today(provider: str) -> int:
    start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    with SessionLocal() as db:
        return db.query(ApiUsage).filter(ApiUsage.provider == provider, ApiUsage.cached.is_(False), ApiUsage.ok.is_(True), ApiUsage.created_at >= start).count()
