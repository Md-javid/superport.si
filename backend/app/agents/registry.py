from app.agents.base import Agent, AgentContext, AgentResult


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        self._agents[agent.name] = agent

    def get(self, name: str) -> Agent:
        return self._agents[name]

    def describe(self) -> list[dict]:
        return [a.describe() for a in self._agents.values()]

    def run_pipeline(self, names: list[str], ctx: AgentContext) -> list[AgentResult]:
        results = []
        for name in names:
            results.append(self.get(name).run(ctx))
        return results
