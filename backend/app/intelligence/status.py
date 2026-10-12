from app.core.config import get_settings
from app.intelligence import mode
from app.intelligence.cache import usage_summary


def status() -> dict:
    s = get_settings()
    m = mode()
    warnings = []
    if m == "live" and not s.gemini_api_key:
        warnings.append("INTELLIGENCE_MODE=live but GEMINI_API_KEY is missing. Gemini features are off.")
    if m == "live" and not s.serpapi_api_key:
        warnings.append("INTELLIGENCE_MODE=live but SERPAPI_API_KEY is missing. Web evidence is off.")
    if m not in ("off", "fixtures", "live"):
        warnings.append(f"Unknown INTELLIGENCE_MODE '{m}'. Using off.")
    return {
        "mode": m if m in ("off", "fixtures", "live") else "off",
        "gemini": {"configured": bool(s.gemini_api_key), "fast_model": s.gemini_model_fast or "auto-detect", "pro_model": s.gemini_model_pro or "auto-detect"},
        "serpapi": {"configured": bool(s.serpapi_api_key)},
        "budgets": {"serpapi_per_shipment": s.serpapi_budget_per_shipment, "gemini_per_shipment": s.gemini_budget_per_shipment, "cache_ttl_hours": s.cache_ttl_hours},
        "usage_30d": usage_summary(30),
        "warnings": warnings,
        "note": {"off": "Rule-based intelligence active.", "fixtures": "Labelled reference telemetry. No live credits consumed.", "live": "Live Gemini and Horizon Sensory Grid, with automated caching and budgets."}.get(m, ""),
    }
