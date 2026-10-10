"""Compliance engine: document completeness, restrictions, certificates, cross-checks."""
from app.catalog import CATALOG, DOC_LABELS, REQUIRED_DOCS, match_item
from app.services.common import doc_value, norm_id, similarity, to_number


def _issue(field, severity, message, values):
    return {"field": field, "severity": severity, "message": message, "values": values}


def cross_check(shipment, docs) -> list[dict]:
    out: list[dict] = []
    ci = lambda k: doc_value(docs, "commercial_invoice", k)
    pl = lambda k: doc_value(docs, "packing_list", k)
    bl = lambda k: doc_value(docs, "bill_of_lading", k)

    # Container number
    containers = {"Shipment": shipment.container_number, "Packing List": pl("container_number"), "Bill of Lading": bl("container_number")}
    present = {k: norm_id(v) for k, v in containers.items() if v}
    if len(set(present.values())) > 1:
        out.append(_issue("Container number", "issue", "Container numbers differ between documents.", {k: v for k, v in containers.items() if v}))

    # Gross weight packing list vs bill of lading
    w_pl, w_bl = to_number(pl("gross_weight")), to_number(bl("gross_weight"))
    if w_pl and w_bl:
        diff = abs(w_pl - w_bl) / max(w_pl, w_bl)
        if diff > 0.02:
            sev = "issue" if diff > 0.05 else "warn"
            out.append(_issue("Gross weight", sev, f"Packing list and bill of lading weights differ by {diff * 100:.1f}%.", {"Packing List": pl("gross_weight"), "Bill of Lading": bl("gross_weight")}))

    # Quantity invoice vs packing list
    q_ci, q_pl = to_number(ci("quantity")), to_number(pl("quantity"))
    if q_ci and q_pl and abs(q_ci - q_pl) / max(q_ci, q_pl) > 0.001:
        out.append(_issue("Quantity", "issue", "Invoice and packing list quantities do not match.", {"Commercial Invoice": ci("quantity"), "Packing List": pl("quantity")}))

    # Invoice arithmetic
    qty, price, total = to_number(ci("quantity")), to_number(ci("unit_price")), to_number(ci("total_value"))
    if qty and price and total and abs(qty * price - total) / total > 0.005:
        out.append(_issue("Total value", "issue", "Quantity multiplied by unit price does not equal the invoice total.", {"Calculated": f"{qty * price:,.2f}", "Invoice total": ci("total_value")}))

    # Parties
    for label, ship_val, doc_pairs in (
        ("Consignee", shipment.importer, [("Commercial Invoice", ci("consignee")), ("Packing List", pl("consignee")), ("Bill of Lading", bl("consignee"))]),
        ("Shipper", shipment.exporter, [("Commercial Invoice", ci("shipper")), ("Packing List", pl("shipper")), ("Bill of Lading", bl("shipper"))]),
    ):
        for doc_name, value in doc_pairs:
            if not value:
                continue
            ratio = similarity(ship_val, value)
            if ratio < 0.6:
                out.append(_issue(label, "issue", f"{label} on the {doc_name} does not match the shipment record.", {"Shipment": ship_val, doc_name: value}))
            elif ratio < 0.88:
                out.append(_issue(label, "warn", f"{label} name on the {doc_name} is spelled differently from the shipment record.", {"Shipment": ship_val, doc_name: value}))

    # Origin
    origin = ci("country_of_origin")
    if origin and similarity(origin, shipment.origin) < 0.8:
        out.append(_issue("Country of origin", "issue", "Invoice country of origin differs from the shipment origin.", {"Shipment": shipment.origin, "Commercial Invoice": origin}))
    return out


def run(shipment, docs, hs_result, hs_decision) -> dict:
    present = {d.doc_type for d in docs}
    missing = [DOC_LABELS[t] for t in REQUIRED_DOCS if t not in present]
    unprocessed = [DOC_LABELS[d.doc_type] for d in docs if d.status != "ready"]
    inconsistencies = cross_check(shipment, docs)
    item, _ = match_item(" ".join([shipment.product_description, (hs_result or {}).get("product_description", "")]))
    if hs_result and hs_result.get("item_key") != "generic":
        item = next((i for i in CATALOG if i["key"] == hs_result["item_key"]), item)

    decision = (hs_decision or {}).get("status", "pending")
    conf = (hs_result or {}).get("confidence", 0)
    if decision in ("approved", "edited"):
        hs_status, hs_state = "Confirmed by reviewer", "ok"
    elif decision == "rejected":
        hs_status, hs_state = "Rejected by reviewer; choose a code or re-run analysis", "issue"
    elif conf >= 0.85:
        hs_status, hs_state = "AI suggestion ready; awaiting human review", "info"
    else:
        hs_status, hs_state = "Low confidence; human classification needed", "warn"

    intel = getattr(shipment, "intel", None) or {}
    rules = intel.get("rules") or {}
    web_rules = rules.get("status") == "ok" and bool(rules.get("restrictions") or rules.get("certificates"))
    if web_rules:
        restrictions = [f"{r['text']} [{r['source']}]" for r in rules["restrictions"]] + [f"Duty: {d['text']} [{d['source']}]" for d in rules.get("duty_notes", [])]
        level_label = {"required": "Required", "likely": "Likely required", "unsure": "Check"}
        certificates = [{"name": c["name"], "status": level_label[c["level"]], "source": c["source"]} for c in rules["certificates"]]
        basis = "web sources, verify before filing"
    else:
        restrictions = item["restrictions"]
        certificates = [{"name": n, "status": "To be attached"} for n in item["certificates"]]
        basis = "demo catalog, illustrative only"
    cert_names = [c["name"] + (f" [{c['source']}]" if c.get("source") else "") for c in certificates]
    company = intel.get("company") or {}
    if company.get("status") == "ok":
        lvl = company["overall_level"]
        company_item = {"id": "counterparties", "title": "Counterparty check", "status": {"high": "issue", "medium": "warn", "unknown": "info", "low": "ok"}[lvl],
                        "summary": {"high": "Adverse news appears to mention a party. Review before approving.", "medium": "A similar company name appears in risk-related news. Identity unclear.", "unknown": "No public business listing found for a party (weak signal).", "low": "Business listings found and no adverse news."}[lvl],
                        "details": [f"{p['role']} {p['name']}: {p['summary']}" for p in company["parties"]]}
    else:
        company_item = {"id": "counterparties", "title": "Counterparty check", "status": "info", "summary": "Not checked yet. Run the market checks to verify importer and exporter.", "details": []}
    items = [
        {"id": "hs", "title": "HS classification", "status": hs_state, "summary": hs_status, "details": []},
        {
            "id": "documents",
            "title": "Missing documents",
            "status": "issue" if missing else "ok",
            "summary": ("Missing: " + ", ".join(missing)) if missing else "All three required documents are on file.",
            "details": [f"{n} has not been processed yet." for n in unprocessed],
        },
        {
            "id": "restrictions",
            "title": "Potential restrictions",
            "status": "warn" if restrictions else "ok",
            "summary": f"{len(restrictions)} to check for this product type (basis: {basis}).",
            "details": restrictions,
        },
        {
            "id": "certificates",
            "title": "Required certificates",
            "status": "warn",
            "summary": f"{len(cert_names)} certificates usually required (basis: {basis}). Attach evidence before submission.",
            "details": cert_names,
        },
        {
            "id": "inconsistencies",
            "title": "Data inconsistencies",
            "status": "issue" if any(i["severity"] == "issue" for i in inconsistencies) else ("warn" if inconsistencies else "ok"),
            "summary": f"{len(inconsistencies)} found across documents." if inconsistencies else "Documents agree with each other and the shipment record.",
            "details": [i["message"] for i in inconsistencies],
        },
        company_item,
    ]
    blocking = [i for i in items if i["status"] == "issue"]
    attention = [i for i in items if i["status"] == "warn"]
    overall = "action_required" if blocking else ("needs_review" if attention or hs_state in ("info",) else "clear")
    review_status = {
        "action_required": "Action required before approval",
        "needs_review": "Ready for human review",
        "clear": "Clear for human approval",
    }[overall]

    return {
        "overall": overall,
        "review_status": review_status,
        "items": items,
        "missing_documents": missing,
        "restrictions": restrictions,
        "certificates": certificates,
        "rules_basis": basis,
        "inconsistencies": inconsistencies,
        "alert_count": len(blocking) + len(attention),
        "rules": "demo-rules-v0 (illustrative, not an official rule set)",
    }
