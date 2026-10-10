from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(20), default="broker")  # broker | forwarder | importer | exporter
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(60), default="Customs Broker")
    company: Mapped[str] = mapped_column(String(160), default="")
    password_hash: Mapped[str] = mapped_column(String(300))
    org_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    org_role: Mapped[str] = mapped_column(String(10), default="admin")  # admin | member
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    org: Mapped["Organization | None"] = relationship()


class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    importer: Mapped[str] = mapped_column(String(200))
    exporter: Mapped[str] = mapped_column(String(200))
    origin: Mapped[str] = mapped_column(String(100))
    destination: Mapped[str] = mapped_column(String(100))
    port: Mapped[str] = mapped_column(String(160))
    carrier: Mapped[str] = mapped_column(String(120))
    container_number: Mapped[str] = mapped_column(String(40))
    product_description: Mapped[str] = mapped_column(Text)

    # draft -> documents -> extraction_review -> hs_review -> final_review -> ready | rejected
    stage: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    hs_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    hs_decision: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    compliance: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    risk: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    analysis_runs: Mapped[int] = mapped_column(Integer, default=0)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    intel: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # price / company / rules checks
    org_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)  # owning organisation
    tracking: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # last tracking provider result

    created_by: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    documents: Mapped[list["Document"]] = relationship(
        back_populates="shipment", cascade="all, delete-orphan", order_by="Document.id"
    )
    events: Mapped[list["AuditEvent"]] = relationship(
        back_populates="shipment", cascade="all, delete-orphan", order_by="AuditEvent.id"
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id", ondelete="CASCADE"), index=True)
    doc_type: Mapped[str] = mapped_column(String(40))  # commercial_invoice | packing_list | bill_of_lading
    filename: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(400), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="uploaded")  # uploaded | ready
    fields: Mapped[list | None] = mapped_column(JSON, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    shipment: Mapped[Shipment] = relationship(back_populates="documents")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id", ondelete="CASCADE"), index=True)
    actor: Mapped[str] = mapped_column(String(120))  # user name, or "SuperPort AI"
    kind: Mapped[str] = mapped_column(String(40))  # system | human
    action: Mapped[str] = mapped_column(String(60))
    message: Mapped[str] = mapped_column(Text)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    shipment: Mapped[Shipment] = relationship(back_populates="events")


class Evidence(Base):
    """A web source (or other proof) that supports an AI finding. Always has a URL and a retrieval time."""

    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30))  # hs | price | company | rules | signal
    engine: Mapped[str] = mapped_column(String(40))
    query: Mapped[str] = mapped_column(Text, default="")
    title: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text, default="")
    snippet: Mapped[str] = mapped_column(Text, default="")
    trust: Mapped[str] = mapped_column(String(20), default="web")  # official | reference | web
    source_mode: Mapped[str] = mapped_column(String(12), default="live")  # live | fixture
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ApiCache(Base):
    __tablename__ = "api_cache"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(20), index=True)
    request: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # never contains API keys
    response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ApiUsage(Base):
    __tablename__ = "api_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(20), index=True)  # serpapi | gemini
    kind: Mapped[str] = mapped_column(String(60))  # engine name or task name
    shipment_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    cached: Mapped[bool] = mapped_column(Boolean, default=False)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FeedbackEvent(Base):
    """Every human correction or decision. This is the future training data for our own models."""

    __tablename__ = "feedback_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30))  # field_edit | hs_decision | final_decision
    field: Mapped[str] = mapped_column(String(120), default="")
    ai_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    action: Mapped[str] = mapped_column(String(30), default="")
    user: Mapped[str] = mapped_column(String(120), default="")
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Signal(Base):
    """A trade event found in the news. A signal, never a fact: it carries sources, a confidence and a verification label."""

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(10), default="low")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    verification: Mapped[str] = mapped_column(String(20), default="single-source")  # single-source | corroborated | official
    locations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    products: Mapped[list | None] = mapped_column(JSON, nullable=True)
    carriers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    sources: Mapped[list | None] = mapped_column(JSON, nullable=True)
    engine: Mapped[str] = mapped_column(String(40), default="")
    source_mode: Mapped[str] = mapped_column(String(12), default="live")
    status: Mapped[str] = mapped_column(String(14), default="new", index=True)  # new | acknowledged | dismissed
    review_note: Mapped[str] = mapped_column(Text, default="")
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SignalMatch(Base):
    __tablename__ = "signal_matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    signal_id: Mapped[int] = mapped_column(ForeignKey("signals.id", ondelete="CASCADE"), index=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id", ondelete="CASCADE"), index=True)
    reason: Mapped[str] = mapped_column(String(160), default="")


class ShipmentParticipant(Base):
    """An organisation invited into someone else's shipment workspace."""

    __tablename__ = "shipment_participants"

    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id", ondelete="CASCADE"), index=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    party_role: Mapped[str] = mapped_column(String(20))  # broker | forwarder | importer | exporter
    invited_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Invitation(Base):
    __tablename__ = "invitations"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(10))  # shipment | team
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)  # inviting organisation
    shipment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    party_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending | accepted | revoked
    invited_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ChecklistItem(Base):
    __tablename__ = "checklist_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(60))
    label: Mapped[str] = mapped_column(String(160))
    party_role: Mapped[str] = mapped_column(String(20))  # who is responsible for providing it
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    doc_type: Mapped[str | None] = mapped_column(String(40), nullable=True)  # core documents feed the AI pipeline
    status: Mapped[str] = mapped_column(String(10), default="missing")  # missing | uploaded
    filename: Mapped[str] = mapped_column(String(255), default="")
    storage_path: Mapped[str | None] = mapped_column(String(400), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by: Mapped[str] = mapped_column(String(120), default="")
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(Integer)
    author: Mapped[str] = mapped_column(String(120))
    org_name: Mapped[str] = mapped_column(String(200), default="")
    party_role: Mapped[str] = mapped_column(String(20), default="")
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    shipment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kind: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str] = mapped_column(String(300), default="")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EmailOutbox(Base):
    __tablename__ = "email_outbox"

    id: Mapped[int] = mapped_column(primary_key=True)
    to_email: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    link: Mapped[str] = mapped_column(Text, default="")
    provider: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SignalReview(Base):
    """Radar review state is per organisation: one company dismissing a signal must not hide it from another."""

    __tablename__ = "signal_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    signal_id: Mapped[int] = mapped_column(ForeignKey("signals.id", ondelete="CASCADE"), index=True)
    org_id: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(14))  # acknowledged | dismissed
    note: Mapped[str] = mapped_column(Text, default="")
    reviewed_by: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(120))
    position: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending | current | done | delayed | blocked
    planned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String(10), default="system")  # system | manual | tracking
    note: Mapped[str] = mapped_column(Text, default="")
    updated_by: Mapped[str] = mapped_column(String(120), default="")
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
