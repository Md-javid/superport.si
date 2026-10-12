"""HS code recommendation service (AI recommendation, human review required)."""
from app.ai.registry import get_llm_provider
from app.catalog import match_item
from app.services.common import doc_value, to_number


def recommend_rules(shipment, docs) -> dict:
    invoice_product = doc_value(docs, "commercial_invoice", "product") or ""
    packing_product = doc_value(docs, "packing_list", "product") or ""
    text = " ".join([shipment.product_description, invoice_product, packing_product])
    item, hits = match_item(text)

    total_kw = max(1, min(len(item["keywords"]), 5)) if item["keywords"] else 1
    coverage = min(1.0, len(hits) / total_kw)
    confidence = round(min(0.97, 0.56 + 0.4 * coverage), 2) if hits else 0.41

    evidence: list[str] = []
    if hits:
        evidence.append("Product description mentions: " + ", ".join(sorted(set(hits))[:6]) + ".")
    if invoice_product:
        evidence.append("Commercial invoice describes the goods as: " + invoice_product + ".")
    if packing_product and packing_product.strip().lower() == invoice_product.strip().lower():
        evidence.append("Invoice and packing list descriptions match.")
    elif packing_product and invoice_product:
        evidence.append("Packing list wording differs slightly from the invoice; check they describe the same goods.")

    qty = to_number(doc_value(docs, "commercial_invoice", "quantity"))
    net = to_number(doc_value(docs, "packing_list", "net_weight"))
    if hits and qty and net and item["unit_weight_kg"]:
        expected = qty * item["unit_weight_kg"]
        if 0.6 <= net / expected <= 1.6:
            evidence.append("Weight per unit is in the range expected for this product type.")
        else:
            evidence.append("Weight per unit is unusual for this product type; confirm the quantity and net weight.")
            confidence = round(max(0.35, confidence - 0.08), 2)
    evidence.append(item["chapter"] + ".")
    if not hits:
        evidence = ["No strong product keywords matched. This is a low-confidence fallback."] + evidence[-1:]

    alternatives = []
    for idx, (code, label, why) in enumerate(item["alternatives"]):
        alternatives.append({"code": code, "label": label, "why_not": why, "confidence": round(max(0.05, confidence - 0.28 - idx * 0.12), 2)})

    rationale = None
    llm = get_llm_provider()
    if llm.configured:
        try:
            rationale = llm.complete(
                "You are a customs classification assistant. Reply in two plain sentences.",
                f"Goods: {text}. Suggested HS code {item['hs_code']} ({item['hs_label']}). Explain why, and what to verify.",
            ).strip() or None
        except Exception:
            rationale = None
    if not rationale:
        rationale = (
            f"The goods look like {item['name'].lower()}, which usually falls under {item['hs_code']}. "
            "Confirm the material, function and any stated model before accepting."
            if hits
            else "The description is too generic to classify confidently. Add material, function and intended use."
        )

    return {
        "product_description": shipment.product_description,
        "code": item["hs_code"],
        "label": item["hs_label"],
        "chapter": item["chapter"],
        "confidence": confidence,
        "evidence": evidence,
        "alternatives": alternatives,
        "rationale": rationale,
        "item_key": item["key"],
        "engine": "rules-v1" if not llm.configured else f"{llm.name}+rules",
        "sources": [],
        "sources_mode": "none",
        "grounded": "none",
        "needs_info": [],
        "source_notes": [],
        "fallback_reason": None,
    }


def recommend(shipment, docs, force: bool = False) -> dict:
    """Evidence-backed Gemini + SerpApi classification when live, otherwise the rule-based demo."""
    from app.intelligence import enabled_for, mode
    from app.intelligence import hs_ranker
    from app.intelligence.errors import IntelligenceError

    rules = recommend_rules(shipment, docs)
    if hs_ranker.available(shipment):
        try:
            return hs_ranker.rank(shipment, docs, rules, force=force)
        except IntelligenceError as exc:
            rules["fallback_reason"] = f"AI classification unavailable: {exc}"
            return rules
    if mode() == "fixtures" and enabled_for(shipment):
        sources, source_mode, notes = hs_ranker.fetch_sources(shipment, shipment.product_description)
        rules.update({"sources": sources, "sources_mode": source_mode, "source_notes": notes, "engine": "rules-v1+sample-evidence"})
    return rules
