"""Specialist agents. Each one gathers evidence for one area with permission-aware tools and returns cited facts.
They do not write the final answer: the Coordinator does, from the evidence only."""
from app.agents.base import Agent, AgentContext, AgentResult
from app.agents.builtin import registry
from app.copilot.core import CopilotContext, Fact, Finding
from app.models import ChecklistItem, Comment
from app.radar import service as radar
from app.rag import indexer
from app.rag.store import Scope
from app.services import eta as eta_service
from app.services import timeline, tracking_service
from app.services.access import accessible_ids

STATUS_LABEL = {"done": "done", "current": "in progress", "pending": "not started", "delayed": "delayed", "blocked": "on hold"}


class CopilotAgent(Agent):
    phase = 2

    def run(self, ctx: AgentContext) -> AgentResult:  # copilot agents are driven by the Coordinator
        return AgentResult(self.name, "skipped", message="Runs inside the Coordinator.")

    def collect(self, c: CopilotContext, question: str) -> Finding:
        raise NotImplementedError


class StatusAgent(CopilotAgent):
    key, name, title = "status", "status_eta", "Status and ETA Agent"
    description = "Reads the timeline, tracking, checklist and ETA drivers."

    def collect(self, c, question):
        s, f = c.shipment, []
        src = lambda t, label: {"type": t, "label": label}
        f.append(Fact(f"Workflow stage: {s.stage.replace('_', ' ')}.", src("timeline", "Shipment record")))
        steps = timeline.timeline_out(c.db, s, c.access, c.party_role)
        groups: dict[str, list[str]] = {}
        for e in steps:
            groups.setdefault(e["status"], []).append(e["label"])
        parts = [f"{STATUS_LABEL[k]}: {', '.join(groups[k])}" for k in ("done", "current", "delayed", "blocked", "pending") if groups.get(k)]
        f.append(Fact("Timeline: " + "; ".join(parts) + ".", src("timeline", "Timeline")))
        for e in steps:
            if e["status"] in ("delayed", "blocked") and e["note"]:
                f.append(Fact(f"{e['label']} is {STATUS_LABEL[e['status']]}: {e['note']}", src("timeline", f"Timeline: {e['label']}")))
        est = eta_service.estimate(c.db, s)
        if est.get("eta"):
            f.append(Fact(f"Expected arrival {est['eta']} (baseline {est['baseline']}, {est['delay_days']} days of expected delay). Basis: {est['basis']}, confidence {round(est['confidence'] * 100)}%. This is an estimate.", src("eta", "ETA estimate")))
            for d in est["drivers"]:
                f.append(Fact(f"Delay driver: +{d['days']} days. {d['label']} ({d['detail']}).", src("eta", "ETA estimate")))
        else:
            f.append(Fact(est["message"], src("eta", "ETA estimate")))
        t = tracking_service.summary(s)
        if t["status"]:
            f.append(Fact(f"Tracking ({'sample data, not real' if t['sample'] else t['provider']}): {t['status']}, {t['location']}.", src("tracking", "Container tracking")))
        miss = [f"{i.label} ({i.party_role})" for i in c.db.query(ChecklistItem).filter_by(shipment_id=s.id, status="missing", required=True)]
        f.append(Fact("Missing required documents: " + ", ".join(miss) + "." if miss else "All required documents have been received.", src("checklist", "Document checklist")))
        return Finding(self.key, f)


class DocumentAgent(CopilotAgent):
    key, name, title = "document", "document_rag", "Document Agent (RAG)"
    description = "Searches the shipment's documents, discussion and your library, and quotes them with citations."

    def collect(self, c, question):
        scope = Scope("shipment", c.shipment.org_id, c.shipment.id, "owner" if c.is_owner else "partner", c.party_role)
        indexer.ensure_indexed(c.db, c.shipment)
        hits = indexer.search(c.db, scope, question)
        facts = []
        for h in hits:
            lib = h["source_type"] == "knowledge"
            label = ("Library: " if lib else "") + h["title"] + (f", page {h['page']}" if h.get("page") and h["source_type"] in ("text", "knowledge") else "")
            facts.append(Fact(h["text"].strip()[:420], {"type": "library" if lib else ("comment" if h["source_type"] == "comment" else "document"), "label": label, "page": h.get("page"), "score": round(float(h["score"]), 3)}))
        return Finding(self.key, facts, note="" if facts else "No relevant passages were found in the documents.")


class ComplianceAgent(CopilotAgent):
    key, name, title = "compliance", "compliance_risk", "Compliance and Risk Agent"
    description = "Summarises HS code, compliance checks and the internal risk score. Broker only."

    def collect(self, c, question):
        if not c.is_owner:
            return Finding(self.key, [], note="HS code, compliance and risk findings are only visible to the broker handling this shipment.", restricted=True)
        s, f = c.shipment, []
        if s.hs_decision and s.hs_decision.get("code"):
            ai = (s.hs_result or {}).get("code")
            f.append(Fact(f"HS code {s.hs_decision['code']} was {s.hs_decision['status']} by a reviewer" + (f" (the AI suggested {ai} with {round((s.hs_result or {}).get('confidence', 0) * 100)}% confidence)." if ai else "."), {"type": "hs", "label": "HS classification"}))
        elif s.hs_result:
            f.append(Fact(f"The AI suggests HS {s.hs_result['code']} ({round(s.hs_result['confidence'] * 100)}% confidence). A human has not approved it yet.", {"type": "hs", "label": "HS classification"}))
        if s.compliance:
            f.append(Fact(f"Compliance: {s.compliance['review_status']}. {s.compliance['alert_count']} item(s) need attention.", {"type": "compliance", "label": "Compliance checks"}))
            for i in s.compliance["items"]:
                if i["status"] in ("issue", "warn"):
                    f.append(Fact(f"{i['title']}: {i['summary']}", {"type": "compliance", "label": f"Compliance: {i['title']}"}))
        if s.risk:
            f.append(Fact(f"Internal risk score {s.risk['score']}/100 ({s.risk['label']}). Main driver: {s.risk['main_driver']}. This is an internal estimate, not a customs decision.", {"type": "risk", "label": "Risk assessment"}))
            for fac in sorted(s.risk["factors"], key=lambda x: -x["contribution"])[:2]:
                f.append(Fact(f"{fac['label']}: {fac['explanation']}", {"type": "risk", "label": f"Risk: {fac['label']}"}))
        return Finding(self.key, f, note="" if f else "The shipment has not been analysed yet.")


class NewsAgent(CopilotAgent):
    key, name, title = "news", "news_signals", "News and Signals Agent"
    description = "Reads open Radar signals that touch this shipment."

    def collect(self, c, question):
        sigs = radar.list_signals(c.db, "active", c.shipment.id, {c.shipment.id}, c.shipment.org_id)[:4]
        facts = [Fact(f"{s['event_type'].replace('_', ' ').title()}: {s['title']} ({s['severity']} impact, {s['verification']}, {round(s['confidence'] * 100)}% confidence). {s['summary']}".strip(),
                      {"type": "signal", "label": "Radar signal", "url": (s["sources"][0]["url"] if s["sources"] else None)}) for s in sigs]
        return Finding(self.key, facts, note="" if facts else "No open signals touch this shipment.")


class DiscussionAgent(CopilotAgent):
    key, name, title = "discussion", "discussion", "Discussion Agent"
    description = "Reads the shipment's recent conversation."

    def collect(self, c, question):
        rows = c.db.query(Comment).filter_by(shipment_id=c.shipment.id).order_by(Comment.id.desc()).limit(6).all()
        facts = [Fact(f"{r.author} ({r.party_role or 'team'}): {r.body[:240]}", {"type": "comment", "label": f"Comment by {r.author}"}) for r in reversed(rows)]
        return Finding(self.key, facts, note="" if facts else "There are no messages yet.")


class CommunicationAgent(CopilotAgent):
    key, name, title = "communication", "communication", "Communication Agent"
    description = "Drafts customer and partner updates. A person reviews and sends them."


class CoordinatorAgent(CopilotAgent):
    key, name, title = "coordinator", "coordinator", "Coordinator"
    description = "Routes a question to the specialists and answers from their cited evidence only."


AGENTS: dict[str, CopilotAgent] = {a.key: a for a in (StatusAgent(), DocumentAgent(), ComplianceAgent(), NewsAgent(), DiscussionAgent())}
for _a in (*AGENTS.values(), CommunicationAgent(), CoordinatorAgent()):
    registry.register(_a)
