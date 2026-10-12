"""Internal shipment risk score.

This is an INTERNAL estimate to help a broker prioritise review. It is not, and
must never be presented as, a customs authority's channel or risk decision.
"""
from app.catalog import DEFAULT_ORIGIN, ORIGIN_LANES, REQUIRED_DOCS, match_item
from app.services.common import doc_value, to_number

WEIGHTS = {"document_consistency": 0.30, "classification": 0.25, "value_anomaly": 0.20, "origin": 0.10, "missing_info": 0.15}


def _level(score: float) -> str:
    return "low" if score < 30 else ("medium" if score < 50 else "high")


def _value_anomaly(docs, item) -> tuple[float, str]:
    price = to_number(doc_value(docs, "commercial_invoice", "unit_price"))
    if price is None:
        return 50.0, "No unit price available to compare against the reference range."
    lo, hi = item["price_band"]
    if lo <= price <= hi:
        return 6.0, f"Unit price {price:,.2f} is within the typical range ({lo:,.0f} to {hi:,.0f}) for this product type."
    if price < lo:
        gap = (lo - price) / lo
        return min(100.0, 45 + gap * 80), f"Unit price {price:,.2f} is {gap * 100:.0f}% below the typical range. Check for under-valuation."
    gap = (price - hi) / hi
    return min(100.0, 35 + gap * 60), f"Unit price {price:,.2f} is {gap * 100:.0f}% above the typical range. Check the invoice."


def run(shipment, docs, hs_result, hs_decision, compliance) -> dict:
    item, _ = match_item(shipment.product_description)
    if hs_result and hs_result.get("item_key"):
        from app.catalog import CATALOG, GENERIC_ITEM

        item = next((i for i in CATALOG if i["key"] == hs_result["item_key"]), GENERIC_ITEM)

    # Document consistency
    incs = compliance["inconsistencies"]
    doc_score = min(100.0, sum(38 if i["severity"] == "issue" else 16 for i in incs))
    doc_note = "No conflicts between documents." if not incs else f"{len(incs)} inconsistenc{'y' if len(incs) == 1 else 'ies'} across documents."

    # Classification confidence
    conf = (hs_result or {}).get("confidence", 0.0)
    cls_score = (1 - conf) * 100
    status = (hs_decision or {}).get("status", "pending")
    if status in ("approved", "edited"):
        cls_score *= 0.4
        cls_note = f"AI confidence {conf * 100:.0f}%, confirmed by a human reviewer."
    else:
        cls_note = f"AI confidence {conf * 100:.0f}%; not yet confirmed by a reviewer."

    intel = getattr(shipment, "intel", None) or {}
    price = intel.get("price") or {}
    if price.get("status") == "ok":
        val_score, val_note, val_basis = float(price["score"]), price["summary"], "live market prices" if price.get("source_mode") == "live" else "sample market prices"
    else:
        val_score, val_note = _value_anomaly(docs, item)
        val_basis = "market baseline price band"

    lane_score, lane_note = ORIGIN_LANES.get((shipment.origin or "").strip().lower(), DEFAULT_ORIGIN)

    missing_docs = [t for t in REQUIRED_DOCS if t not in {d.doc_type for d in docs}]
    blank = sum(1 for d in docs for f in (d.fields or []) if not str(f.get("value", "")).strip())
    miss_score = min(100.0, len(missing_docs) * 35 + blank * 9)
    miss_note = "Nothing missing." if not miss_score else f"{len(missing_docs)} document(s) and {blank} field(s) missing."

    raw = {
        "document_consistency": (doc_score, doc_note, "Document consistency"),
        "classification": (cls_score, cls_note, "Product classification confidence"),
        "value_anomaly": (val_score, val_note, "Value anomaly"),
        "origin": (lane_score, lane_note, "Origin and lane familiarity"),
        "missing_info": (miss_score, miss_note, "Missing information"),
    }
    weights = dict(WEIGHTS)
    company = intel.get("company") or {}
    if company.get("status") == "ok":  # a sixth factor appears only when real counterparty data exists
        level = company["overall_level"]
        raw["counterparty"] = ({"high": 85.0, "medium": 45.0, "unknown": 25.0, "low": 6.0}[level], "; ".join(f"{p['role']}: {p['summary']}" for p in company["parties"]), "Counterparty check")
        weights = {**{k: v * 0.9 for k, v in WEIGHTS.items()}, "counterparty": 0.10}
    bases = {"value_anomaly": val_basis, "counterparty": "public web signals"}
    factors = []
    total = 0.0
    for key, (score, note, label) in raw.items():
        contribution = score * weights[key]
        total += contribution
        factors.append({"key": key, "label": label, "score": round(score), "weight": round(weights[key], 3), "contribution": round(contribution, 1), "level": _level(score), "explanation": note, "basis": bases.get(key, "document data")})

    score = round(total)
    level = _level(score)
    top = max(factors, key=lambda f: f["contribution"])
    headline = {
        "low": "Low internal risk. Standard review is enough.",
        "medium": "Medium internal risk. Review the flagged factors before approving.",
        "high": "High internal risk. A senior review and written justification are recommended.",
    }[level]
    return {
        "score": score,
        "level": level,
        "label": {"low": "Low Risk", "medium": "Medium Risk", "high": "High Risk"}[level],
        "headline": headline,
        "main_driver": top["label"],
        "factors": factors,
        "disclaimer": "Internal SuperPort estimate for review prioritisation. It is not a customs authority decision and does not predict one.",
    }
