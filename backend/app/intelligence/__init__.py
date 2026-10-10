"""v2 intelligence layer: Gemini (reasoning + vision) and SerpApi (live web evidence).

Modes (INTELLIGENCE_MODE):
  off      v1 behaviour. No external calls.
  fixtures sample SerpApi data so the evidence UI can be shown without keys. Gemini stays off.
  live     real Gemini and SerpApi calls, with caching and per-shipment budgets.
Seeded demo shipments (is_demo) never trigger external calls.
"""
from app.core.config import get_settings


def mode() -> str:
    return (get_settings().intelligence_mode or "off").strip().lower()


def gemini_ready() -> bool:
    return mode() == "live" and bool(get_settings().gemini_api_key)


def serpapi_ready() -> bool:
    return mode() == "fixtures" or (mode() == "live" and bool(get_settings().serpapi_api_key))


def enabled_for(shipment) -> bool:
    return not bool(getattr(shipment, "is_demo", False))


def synthetic_allowed(shipment) -> bool:
    """May we fabricate (clearly labelled) demo values for unreadable documents?"""
    if getattr(shipment, "is_demo", False):
        return True
    explicit = get_settings().allow_synthetic_extraction
    if explicit is not None:
        return explicit
    return mode() != "live"
