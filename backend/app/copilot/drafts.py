"""Customer and partner update drafts. The AI writes, a person edits and sends."""
from app.copilot.agents import AGENTS
from app.copilot.core import CopilotContext
from app.core.config import get_settings
from app.intelligence import gemini_client, gemini_ready
from app.intelligence.errors import IntelligenceError
from app.models import AuditEvent, ChecklistItem, Organization, ShipmentParticipant, User
from app.email import service as mail
from app.services import notify
from app.services.access import PARTY_ROLES

LABEL = {"broker": "customs broker", "forwarder": "freight forwarder", "importer": "importer", "exporter": "exporter"}


def _base_facts(c: CopilotContext, audience: str) -> tuple[list[str], list[str]]:
    finding = AGENTS["status"].collect(c, "status")
    facts = [f.text for f in finding.facts if "Workflow stage" not in f.text]
    asks = [f"{i.label}" for i in c.db.query(ChecklistItem).filter_by(shipment_id=c.shipment.id, status="missing", party_role=audience)]
    return facts, asks


def _template(c: CopilotContext, audience: str, facts: list[str], asks: list[str]) -> dict:
    s = c.shipment
    org = c.db.get(Organization, c.user.org_id)
    lines = [f"Dear {LABEL.get(audience, audience)} team,", "", f"This is an update on shipment {s.reference} ({s.product_description}) from {s.origin} to {s.destination} via {s.port}.", ""]
    lines += [f"- {f}" for f in facts[:6]]
    if asks:
        lines += ["", "What we need from you: " + ", ".join(asks) + "."]
    lines += ["", "Dates are estimates and may change. Reply here or in the shipment workspace if anything looks wrong.", "", f"Regards,\n{c.user.name}\n{org.name if org else ''}"]
    return {"subject": f"Update on shipment {s.reference}", "body": "\n".join(lines).strip(), "engine": "template"}


def draft(c: CopilotContext, audience: str) -> dict:
    if audience not in PARTY_ROLES:
        raise ValueError("Choose broker, forwarder, importer or exporter.")
    facts, asks = _base_facts(c, audience)
    out = _template(c, audience, facts, asks)
    if gemini_ready():
        prompt = (f"Write a short, polite shipment update email to the {LABEL[audience]}. Use ONLY these facts. Do not promise dates; call them estimates. Under 130 words, plain language, no jargon.\n"
                  f"Shipment {c.shipment.reference}: {c.shipment.product_description}, {c.shipment.origin} to {c.shipment.destination}.\nFACTS\n" + "\n".join(f"- {f}" for f in facts[:10]) +
                  ("\nACTION NEEDED FROM THEM: " + ", ".join(asks) if asks else "") + f"\nSign as {c.user.name}.\n" + 'Return JSON: {"subject":"...","body":"..."}')
        try:
            parsed, meta = gemini_client.generate_json("draft_update", system="You write concise logistics emails. Reply with one JSON object only.", parts=[{"text": prompt}], kind="fast")
            if parsed.get("subject") and parsed.get("body"):
                out = {"subject": str(parsed["subject"])[:200], "body": str(parsed["body"])[:3000], "engine": f"gemini:{meta['model']}"}
        except IntelligenceError as exc:
            out["warning"] = f"AI drafting was unavailable ({exc}). Using the standard template."
    return {**out, "audience": audience, "based_on": facts[:10]}


def send(c: CopilotContext, to_roles: list[str], subject: str, body: str) -> int:
    s = c.shipment
    org_ids = [p.org_id for p in c.db.query(ShipmentParticipant).filter_by(shipment_id=s.id) if p.party_role in to_roles]
    users = c.db.query(User).filter(User.org_id.in_(org_ids or [0])).all()
    if not users:
        raise LookupError("No one with that role has joined this shipment yet. Invite them first.")
    link = f"{get_settings().app_url}/shipments/{s.id}/workspace"
    for u in users:
        mail.send(c.db, u.email, subject, f"{body}\n\nOpen the shipment workspace: {link}", link)
    notify.notify(c.db, [u.id for u in users], subject, body[:300], kind="update", shipment_id=s.id, link=f"/shipments/{s.id}/workspace")
    c.db.add(AuditEvent(shipment_id=s.id, actor=c.user.name, kind="human", action="update_sent", message=f"{c.user.name} sent a status update to the {', '.join(to_roles)}."))
    c.db.commit()
    return len(users)
