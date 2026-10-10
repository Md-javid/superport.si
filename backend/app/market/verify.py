"""Run the market checks (price, company, rules) and keep a per-part result, even if one part fails."""
from app.intelligence import mode
from app.intelligence.errors import IntelligenceError
from app.market import company_check, price_check, rules_lookup
from app.models import utcnow

PARTS = ("price", "company", "rules")


def use_fixtures(shipment) -> bool:
    """Sample data for fixtures mode, and for fictional demo shipments in live mode (never spend credits on them)."""
    m = mode()
    return m == "fixtures" or (m == "live" and bool(getattr(shipment, "is_demo", False)))


def availability(shipment) -> dict:
    m = mode()
    if m == "off":
        return {"available": False, "reason": "Turn on INTELLIGENCE_MODE=fixtures or live to run market checks.", "sample": False}
    return {"available": True, "reason": None, "sample": use_fixtures(shipment)}


def run_all(shipment, docs, parts, force: bool = False) -> dict:
    fixture = use_fixtures(shipment)
    intel = dict(shipment.intel or {})
    for part in parts:
        if part not in PARTS:
            continue
        try:
            if part == "price":
                result = price_check.run(shipment, docs, fixture=fixture, force=force)
            elif part == "company":
                result = company_check.run(shipment, fixture=fixture, force=force)
            else:
                result = rules_lookup.run(shipment, shipment.hs_result, shipment.hs_decision, fixture=fixture, force=force)
        except IntelligenceError as exc:
            result = {"kind": part, "status": "unavailable", "summary": str(exc), "source_mode": "fixture" if fixture else "live"}
        intel[part] = result
    intel["updated_at"] = utcnow().isoformat()
    return intel
