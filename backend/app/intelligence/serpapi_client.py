"""SerpApi client: Google (and other engine) results as JSON.

Cached in the database, budgeted per shipment, and the API key is never stored or logged.
"""
import json
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.intelligence import mode
from app.intelligence.cache import billable_calls, cache_get, cache_put, live_calls_today, log_usage, make_key
from app.intelligence.errors import BudgetExceeded, NotConfigured, UpstreamError

BASE = "https://serpapi.com/search.json"
FIXTURES = Path(__file__).parent / "fixtures"
_transport: httpx.BaseTransport | None = None  # tests inject a mock transport here


def set_transport(transport: httpx.BaseTransport | None) -> None:
    global _transport
    _transport = transport


def _fixture(engine: str, params: dict | None = None) -> dict:
    name = engine + ("_news" if (params or {}).get("tbm") == "nws" else "")
    path = FIXTURES / f"{name}.json"
    if not path.exists():
        raise NotConfigured(f"No sample data for engine '{engine}' in fixtures mode.")
    return json.loads(path.read_text())


def search(engine: str, params: dict, *, shipment_id: int | None = None, force: bool = False, fixture: bool = False) -> dict:
    """Run one SerpApi search. Raises IntelligenceError subclasses; callers decide how to degrade."""
    settings = get_settings()
    current = mode()
    if current == "off":
        raise NotConfigured("Intelligence is turned off (INTELLIGENCE_MODE=off).")
    if current == "fixtures" or fixture:
        return _fixture(engine, params)
    if not settings.serpapi_api_key:
        raise NotConfigured("SERPAPI_API_KEY is not set.")

    payload = {"engine": engine, **params}
    kind = "google_news" if params.get("tbm") == "nws" else engine  # news searches are counted separately
    key = make_key("serpapi", payload)
    if not force:
        hit = cache_get("serpapi", key, settings.cache_ttl_hours)
        if hit is not None:
            log_usage("serpapi", kind, shipment_id, cached=True)
            return hit
    if live_calls_today("serpapi") >= settings.serpapi_daily_cap:
        raise BudgetExceeded(f"Daily SerpApi cap reached ({settings.serpapi_daily_cap} searches). Raise SERPAPI_DAILY_CAP if intended.")
    if shipment_id is not None and billable_calls("serpapi", shipment_id) >= settings.serpapi_budget_per_shipment:
        raise BudgetExceeded(f"SerpApi search budget reached for this shipment ({settings.serpapi_budget_per_shipment}).")

    try:
        with httpx.Client(transport=_transport, timeout=25) as client:
            response = client.get(BASE, params={**payload, "api_key": settings.serpapi_api_key})
    except httpx.HTTPError as exc:
        log_usage("serpapi", kind, shipment_id, ok=False, detail=type(exc).__name__)
        raise UpstreamError("Could not reach SerpApi. Check your internet connection.") from exc

    if response.status_code in (401, 403):
        log_usage("serpapi", kind, shipment_id, ok=False, detail=f"http {response.status_code}")
        raise UpstreamError("SerpApi rejected the API key. Check SERPAPI_API_KEY.")
    if response.status_code == 429:
        log_usage("serpapi", kind, shipment_id, ok=False, detail="http 429")
        raise UpstreamError("SerpApi rate or plan limit reached.")
    try:
        data = response.json()
    except ValueError as exc:
        log_usage("serpapi", kind, shipment_id, ok=False, detail=f"non-json http {response.status_code}")
        raise UpstreamError(f"SerpApi returned an unreadable response (HTTP {response.status_code}).") from exc

    error = data.get("error") if isinstance(data, dict) else None
    if error:
        if "hasn't returned any results" in str(error).lower() or "no results" in str(error).lower():
            data = {"organic_results": [], "empty": True}  # a valid, empty answer
        else:
            log_usage("serpapi", kind, shipment_id, ok=False, detail=str(error))
            raise UpstreamError(f"SerpApi error: {error}")
    elif response.status_code >= 400:
        log_usage("serpapi", kind, shipment_id, ok=False, detail=f"http {response.status_code}")
        raise UpstreamError(f"SerpApi returned HTTP {response.status_code}.")

    cache_put("serpapi", key, payload, data)
    log_usage("serpapi", kind, shipment_id)
    return data
