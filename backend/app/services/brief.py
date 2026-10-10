"""Copilot brief: what happened, why, what the AI recommends, what needs approval, what's next."""
from app.catalog import DOC_LABELS, REQUIRED_DOCS


def build(shipment) -> dict:
    stage = shipment.stage
    docs = shipment.documents
    risk = shipment.risk
    comp = shipment.compliance
    hs = shipment.hs_result
    have = {d.doc_type for d in docs}
    missing = [DOC_LABELS[t] for t in REQUIRED_DOCS if t not in have]

    if stage in ("draft", "documents"):
        return {
            "happened": f"Shipment {shipment.reference} was created. {len(have)} of 3 documents uploaded.",
            "why": "SuperPort needs the invoice, packing list and bill of lading to cross-check the shipment.",
            "recommendation": ("Upload " + ", ".join(missing) + ".") if missing else "All documents are in. Start the analysis.",
            "approval": "Nothing to approve yet.",
            "next": "AI reads each document and fills in the shipment data for your review.",
        }
    if stage == "extraction_review":
        low = sum(1 for d in docs for f in (d.fields or []) if f["value"] and f["confidence"] < 0.85)
        blank = sum(1 for d in docs for f in (d.fields or []) if not f["value"])
        return {
            "happened": f"AI extracted fields from {sum(1 for d in docs if d.status == 'ready')} document(s).",
            "why": "Every value is shown with its confidence so you can spot what to check first.",
            "recommendation": (f"Check {low} lower-confidence and {blank} empty field(s), then confirm." if (low or blank) else "Values look consistent. Confirm to continue."),
            "approval": "Confirm the extracted data before AI classifies the goods.",
            "next": "AI suggests an HS code, runs compliance checks and scores risk.",
        }
    if stage == "hs_review" and hs:
        decision = (shipment.hs_decision or {}).get("status")
        rejected = decision == "rejected"
        return {
            "happened": f"AI suggested HS {hs['code']} with {hs['confidence'] * 100:.0f}% confidence." + (" You rejected it." if rejected else ""),
            "why": hs["evidence"][0] if hs["evidence"] else hs["rationale"],
            "recommendation": "Choose another code or ask for re-analysis." if rejected else ("Approve if the description matches." if hs["confidence"] >= 0.85 else "Confidence is lower than usual. Review the alternatives before approving."),
            "approval": "You decide the final HS code. AI only recommends.",
            "next": "Compliance and risk results are refreshed with your decision.",
        }
    if stage == "final_review" and risk and comp:
        hold = risk["level"] == "high" or comp["overall"] == "action_required"
        return {
            "happened": f"Checks complete. Risk {risk['score']}/100 ({risk['label']}). {comp['alert_count']} compliance item(s) to look at.",
            "why": f"Biggest driver: {risk['main_driver'].lower()}.",
            "recommendation": "Resolve open issues or document a justification before approving." if hold else "Findings look manageable. Approve when you are satisfied.",
            "approval": "Final approval is yours. A justification is required if risk is high or issues are open." if hold else "Approve, edit, reject or ask for re-analysis.",
            "next": "Approval creates the clearance-ready summary for handover.",
        }
    if stage == "ready":
        return {
            "happened": "Approved by a human reviewer. The clearance-ready summary is prepared.",
            "why": "All required review gates were completed.",
            "recommendation": "Share the summary with your submission team.",
            "approval": "No further approvals pending.",
            "next": "Phase 1 does not submit to any customs authority. Use the summary for your usual filing.",
        }
    return {
        "happened": "This shipment was rejected for clearance.",
        "why": "A reviewer decided it should not proceed.",
        "recommendation": "Create a corrected shipment if the issue can be fixed.",
        "approval": "Closed.",
        "next": "No further action.",
    }
