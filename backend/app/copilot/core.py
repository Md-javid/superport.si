from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models import Shipment, User


@dataclass
class CopilotContext:
    db: Session
    user: User
    shipment: Shipment
    access: str  # owner | partner
    party_role: str | None = None

    @property
    def is_owner(self) -> bool:
        return self.access == "owner"


@dataclass
class Fact:
    text: str
    source: dict  # {"type", "label", optional "url", "page", "score"}


@dataclass
class Finding:
    agent: str
    facts: list[Fact] = field(default_factory=list)
    note: str = ""
    restricted: bool = False
