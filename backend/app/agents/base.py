"""Agent layer contracts.

Phase 1 ships thin agents that delegate to the existing services. Future agents
(autonomous exception handling, broker messaging, customs filing) plug in by
subclassing Agent and registering with the AgentRegistry. No code elsewhere
needs to change.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class AgentContext:
    shipment: object
    documents: list
    state: dict = field(default_factory=dict)  # shared results between agents in one run


@dataclass
class AgentResult:
    agent: str
    status: str  # ok | skipped | not_implemented
    data: dict = field(default_factory=dict)
    message: str = ""


class Agent(ABC):
    name: str = "agent"
    title: str = "Agent"
    description: str = ""
    phase: int = 1
    implemented: bool = True

    @abstractmethod
    def run(self, ctx: AgentContext) -> AgentResult: ...

    def describe(self) -> dict:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "phase": self.phase,
            "status": "active" if self.implemented else "planned",
        }
