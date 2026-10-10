from app.agents.base import Agent, AgentContext, AgentResult
from app.agents.registry import AgentRegistry
from app.services import compliance, hs_code, risk


class DocumentAgent(Agent):
    name = "document"
    title = "Document Agent"
    description = "Reads invoices, packing lists and bills of lading and extracts fields."

    def run(self, ctx: AgentContext) -> AgentResult:
        # Extraction runs per upload in services.workflow.process_documents.
        return AgentResult(self.name, "skipped", message="Extraction is triggered on upload in Phase 1.")


class CustomsAgent(Agent):
    name = "customs"
    title = "Customs Agent"
    description = "Recommends HS classifications with evidence and alternatives."

    def run(self, ctx: AgentContext) -> AgentResult:
        existing = ctx.state.get("existing_hs")
        if not ctx.state.get("refresh_hs", True) and existing:
            result = existing  # edits and decisions never trigger paid AI calls
        else:
            result = hs_code.recommend(ctx.shipment, ctx.documents, force=ctx.state.get("force", False))
        ctx.state["hs_result"] = result
        return AgentResult(self.name, "ok", {"hs_result": result})


class ComplianceAgent(Agent):
    name = "compliance"
    title = "Compliance Agent"
    description = "Checks documents, restrictions, certificates and cross-document consistency."

    def run(self, ctx: AgentContext) -> AgentResult:
        result = compliance.run(ctx.shipment, ctx.documents, ctx.state.get("hs_result"), ctx.state.get("hs_decision"))
        ctx.state["compliance"] = result
        return AgentResult(self.name, "ok", {"compliance": result})


class RiskAgent(Agent):
    name = "risk"
    title = "Risk Agent"
    description = "Scores internal shipment risk and explains the factors."

    def run(self, ctx: AgentContext) -> AgentResult:
        result = risk.run(ctx.shipment, ctx.documents, ctx.state.get("hs_result"), ctx.state.get("hs_decision"), ctx.state["compliance"])
        ctx.state["risk"] = result
        return AgentResult(self.name, "ok", {"risk": result})


class ExceptionAgent(Agent):
    name = "exception"
    title = "Exception Agent"
    description = "Will triage holds, queries and re-submissions and draft responses."
    phase = 2
    implemented = False

    def run(self, ctx: AgentContext) -> AgentResult:
        return AgentResult(self.name, "not_implemented", message="Planned for a later phase.")


registry = AgentRegistry()
for _agent in (DocumentAgent(), CustomsAgent(), ComplianceAgent(), RiskAgent(), ExceptionAgent()):
    registry.register(_agent)
