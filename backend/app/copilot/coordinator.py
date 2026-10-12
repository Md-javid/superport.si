"""The Coordinator: plan which specialists to consult, merge their evidence, answer ONLY from it, and prove it."""
import re

from app.copilot.agents import AGENTS
from app.copilot.core import CopilotContext, Finding
from app.core.config import get_settings
from app.intelligence import gemini_client, gemini_ready
from app.intelligence.errors import IntelligenceError
from app.models import CopilotMessage

KEYS = {
    "status": ["delay", "late", "eta", "arriv", "where", "location", "track", "status", "timeline", "when", "stuck", "held", "progress", "vessel", "container", "cleared", "clearance"],
    "compliance": ["hs ", "hs-", "code", "classif", "complian", "restrict", "risk", "duty", "tariff", "approv", "permit", "licen"],
    "news": ["news", "strike", "congestion", "port", "weather", "cyclone", "storm", "signal", "disruption", "carrier", "blank sailing"],
    "discussion": ["said", "comment", "discuss", "told", "asked", "conversation", "message", "thread", "who "],
}
SYSTEM = ("You are SuperPort's shipment coordinator, helping a logistics professional. Answer ONLY from the numbered evidence. Cite the evidence for every claim like [E2]. "
          "If the evidence does not answer the question, say exactly what is missing. Never invent dates, numbers, documents or people. Be brief (under 120 words) and plain. "
          "Estimates are estimates. Risk scores are internal and are not customs decisions. Reply with one JSON object only.")
ORDER = ["status", "news", "compliance", "discussion", "document"]
LIMITS = {"status": 6, "news": 3, "compliance": 5, "discussion": 3, "document": 4}


def plan(question: str) -> list[str]:
    q = " " + question.lower() + " "
    chosen = {name for name, words in KEYS.items() if any(w in q for w in words)}
    if re.search(r"delay|late|stuck|held|hold", q):
        chosen |= {"status", "news"}
    if not chosen:
        chosen = {"status", "discussion"}
    chosen.add("document")  # documents are always consulted: it is the cheapest way to stay grounded
    return [a for a in ORDER if a in chosen]


def _pack(findings: list[Finding]) -> list[dict]:
    pack, n = [], 0
    for f in findings:
        for fact in f.facts[: LIMITS.get(f.agent, 4)]:
            n += 1
            pack.append({"id": f"E{n}", "agent": f.agent, "text": fact.text, "source": fact.source})
    return pack


def _deterministic(shipment_ref: str, findings: list[Finding], pack: list[dict]) -> str:
    lines = [f"Note: {f.note}" for f in findings if f.restricted]  # say what is off limits first
    lines += [f"Here is what the records show for {shipment_ref}:"]
    lines += [f"- {e['text']} [{e['id']}]" for e in pack[:9]]
    return "\n".join(lines)


def clean_citations(answer: str, valid: set[str]) -> tuple[str, list[str]]:
    used = []

    def keep(m: re.Match) -> str:
        cid = f"E{m.group(1)}"
        if cid in valid:
            used.append(cid)
            return f"[{cid}]"
        return ""  # a citation that points at nothing is removed

    cleaned = re.sub(r"\s*\[E(\d+)\]", lambda m: " " + keep(m) if f"E{m.group(1)}" in valid else "", answer)
    return cleaned.strip(), sorted(set(used), key=lambda x: int(x[1:]))


def ask(c: CopilotContext, question: str) -> dict:
    names = plan(question)
    findings: list[Finding] = []
    for n in names:
        try:
            findings.append(AGENTS[n].collect(c, question))
        except IntelligenceError as exc:
            findings.append(Finding(n, [], note=f"{AGENTS[n].title} was unavailable: {exc}"))
    pack = _pack(findings)
    restricted = [f for f in findings if f.restricted]
    engine, grounded, missing, follow_ups, warning = "rules", False, [], [], None
    if not pack:
        answer = "I could not find that in this shipment's documents or data."
        if restricted:
            answer = restricted[0].note
    elif gemini_ready():
        evidence = "\n".join(f"{e['id']} [{e['source']['label']}]: {e['text']}" for e in pack)
        prompt = (f"Shipment {c.shipment.reference}: {c.shipment.product_description}, {c.shipment.origin} to {c.shipment.destination}.\n\nEVIDENCE\n{evidence}\n\nQUESTION\n{question}\n\n"
                  'Return JSON: {"answer":"...","missing":["facts you could not find"],"follow_ups":["up to 3 useful next questions"]}')
        try:
            parsed, meta = gemini_client.generate_json("copilot_answer", system=SYSTEM, parts=[{"text": prompt}], kind=get_settings().copilot_model_kind if get_settings().copilot_model_kind in ("fast", "pro") else "fast")
            answer, used = clean_citations(str(parsed.get("answer", "")), {e["id"] for e in pack})
            missing = [str(x)[:160] for x in parsed.get("missing", [])][:4]
            follow_ups = [str(x)[:140] for x in parsed.get("follow_ups", [])][:3]
            engine, grounded = f"gemini:{meta['model']}", bool(used)
            if not answer:
                raise IntelligenceError("empty answer")
            for f in restricted:
                answer = f"Note: {f.note}\n\n" + answer
        except IntelligenceError as exc:
            answer, warning = _deterministic(c.shipment.reference, findings, pack), f"The AI summariser was unavailable ({exc}). Showing the raw findings."
            grounded = True
    else:
        answer, grounded = _deterministic(c.shipment.reference, findings, pack), True
    out = {"answer": answer, "grounded": grounded, "engine": engine, "warning": warning, "missing": missing, "follow_ups": follow_ups,
           "agents": [{"agent": f.agent, "title": AGENTS[f.agent].title, "facts": len(f.facts), "note": f.note, "restricted": f.restricted} for f in findings], "evidence": pack}
    row = CopilotMessage(shipment_id=c.shipment.id, user_id=c.user.id, question=question, answer=answer, evidence=pack, agents=out["agents"], engine=engine, grounded=grounded)
    c.db.add(row)
    c.db.commit()
    out["id"] = row.id
    return out
