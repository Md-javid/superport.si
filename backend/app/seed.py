"""Demo seed data. Everything here is fictional."""
from datetime import timedelta

from sqlalchemy.orm import Session

from app.api.auth import DEMO_EMAIL, DEMO_PASSWORD
from app.core.security import hash_password
from app.models import AuditEvent, Comment, Organization, Shipment, ShipmentParticipant, User, utcnow
from app.services import workflow

SEEDS = [
    dict(
        reference="SP-2026-0001", importer="Meridian Power Systems Pvt Ltd", exporter="Shenzhen VoltEdge Technologies Co., Ltd",
        origin="China", destination="India", port="Chennai Port (INMAA)", carrier="Maersk Line", container_number="MSKU7294816",
        product_description="Lithium-ion battery packs, 48V 100Ah, for energy storage systems",
        samples=True, until="final_review", age=2,
    ),
    dict(
        reference="SP-2026-0002", importer="Coastline Apparel Retail Pvt Ltd", exporter="Saigon Textile Works Co., Ltd",
        origin="Vietnam", destination="India", port="Nhava Sheva (INNSA)", carrier="CMA CGM", container_number="CMAU5518342",
        product_description="Men's knitted cotton T-shirts, round neck, assorted sizes",
        until="ready", age=9,
    ),
    dict(
        reference="SP-2026-0003", importer="Brightwave Electricals Pvt Ltd", exporter="Guangzhou Lumina Lighting Co., Ltd",
        origin="China", destination="India", port="Mundra (INMUN)", carrier="MSC", container_number="MSCU3381290",
        product_description="LED panel light and downlight luminaires, 18W",
        until="hs_review", age=1,
    ),
    dict(
        reference="SP-2026-0004", importer="Malabar Roasters LLP", exporter="Cooxupe Exportadora Ltda",
        origin="Brazil", destination="India", port="Cochin Port (INCOK)", carrier="Hapag-Lloyd", container_number="HLXU8820145",
        product_description="Green arabica coffee beans, Santos grade, bagged",
        until="extraction_review", age=1,
    ),
    dict(
        reference="SP-2026-0005", importer="Southern Water Utilities Ltd", exporter="Rheinwerk Pumpen GmbH",
        origin="Germany", destination="India", port="Chennai Port (INMAA)", carrier="Hapag-Lloyd", container_number="HLXU4410973",
        product_description="Centrifugal pumps, stainless steel, 15 kW",
        until="documents", docs=["commercial_invoice", "packing_list"], age=0,
    ),
    dict(
        reference="SP-2026-0006", importer="Orbit Mobile Distribution Pvt Ltd", exporter="Gulf Digital Trading FZE",
        origin="United Arab Emirates", destination="India", port="Nhava Sheva (INNSA)", carrier="ONE", container_number="ONEU6073391",
        product_description="Smartphones, 5G, 128GB, retail boxed",
        until="final_review", age=3,
        overrides=[("commercial_invoice", "unit_price", "46.00"), ("commercial_invoice", "total_value", "92,000.00"), ("bill_of_lading", "container_number", "ONEU6073319"), ("commercial_invoice", "shipper", "G. D. Traders Co")],
    ),
    dict(
        reference="SP-2026-0007", importer="Kerala Gourmet Imports Pvt Ltd", exporter="Aceites del Sur S.A.",
        origin="Spain", destination="India", port="Cochin Port (INCOK)", carrier="MSC", container_number="MSCU9120456",
        product_description="Extra virgin olive oil, 1 litre glass bottles",
        until="hs_review", age=1,
    ),
]


def _advance(db: Session, s: Shipment, until: str, actor: str) -> None:
    if until == "documents":
        return
    workflow.process_documents(db, s)
    if until == "extraction_review":
        return
    workflow.confirm_extraction(db, s, actor)
    if until == "hs_review":
        return
    workflow.review_hs(db, s, "approve", None, None, actor)
    if until == "ready":
        workflow.final_decision(db, s, "approve", "Reviewed and approved.", actor)


def seed(db: Session) -> None:
    if db.query(User).count():
        return
    org = Organization(name="Harbor & Co. Customs Advisory", type="broker")
    db.add(org)
    db.flush()
    user = User(email=DEMO_EMAIL, name="Aarav Menon", role="Customs Broker", company=org.name, password_hash=hash_password(DEMO_PASSWORD), org_id=org.id, org_role="admin", email_verified=True)
    db.add(user)
    db.commit()
    actor = user.name
    for spec in SEEDS:
        s = workflow.create_shipment(db, {**{k: spec[k] for k in ("reference", "importer", "exporter", "origin", "destination", "port", "carrier", "container_number", "product_description")}, "is_demo": True}, user)
        if spec.get("samples"):
            workflow.attach_samples(db, s, actor)
        else:
            for doc_type in spec.get("docs", ["commercial_invoice", "packing_list", "bill_of_lading"]):
                workflow.add_document(db, s, doc_type, f"{doc_type}_{s.reference}.pdf", b"", "application/pdf", actor)
        if spec["until"] != "documents":
            workflow.process_documents(db, s)
            for doc_type, key, value in spec.get("overrides", []):
                doc = next(d for d in s.documents if d.doc_type == doc_type)
                workflow.update_field(db, s, doc, key, value, "Seed")
        _advance(db, s, spec["until"], actor)
        stamp = utcnow() - timedelta(days=spec["age"], hours=spec["age"] * 2 + 1)
        s.created_at = stamp - timedelta(hours=5)
        s.updated_at = stamp
        db.commit()


PERSONAS = [
    ("forwarder@superport.ai", "Priya Nair", "Freight Forwarder", "BlueWave Freight Forwarders", "forwarder"),
    ("importer@superport.ai", "Rahul Shah", "Supply Chain Manager", "Meridian Power Systems Pvt Ltd", "importer"),
]


def seed_personas(db: Session) -> None:
    """Forwarder and importer demo accounts sharing the battery shipment, so the ecosystem can be shown in seconds."""
    broker = db.query(User).filter_by(email=DEMO_EMAIL).first()
    ship = db.query(Shipment).filter_by(reference="SP-2026-0001").first()
    if not broker or not ship or db.query(User).filter_by(email=PERSONAS[0][0]).first():
        return
    users = {}
    for email, name, title, company, role in PERSONAS:
        org = Organization(name=company, type=role)
        db.add(org)
        db.flush()
        u = User(email=email, name=name, role=title, company=company, password_hash=hash_password(DEMO_PASSWORD), org_id=org.id, org_role="admin", email_verified=True)
        db.add(u)
        db.flush()
        users[role] = (u, org)
        db.add(ShipmentParticipant(shipment_id=ship.id, org_id=org.id, party_role=role, invited_by=broker.id))
        db.add(AuditEvent(shipment_id=ship.id, actor=name, kind="human", action="participant_joined", message=f"{company} joined as {role}."))
        if role == "forwarder":
            five = db.query(Shipment).filter_by(reference="SP-2026-0005").first()
            if five:
                db.add(ShipmentParticipant(shipment_id=five.id, org_id=org.id, party_role=role, invited_by=broker.id))
    talk = [
        (broker, "broker", "Harbor & Co. Customs Advisory", "Thanks both. The invoice and packing list are in. We still need the Certificate of Origin from the exporter before filing."),
        (users["importer"][0], "importer", "Meridian Power Systems Pvt Ltd", "@Priya can you confirm the container reaches Chennai Port this week? Our plant is waiting on these packs."),
        (users["forwarder"][0], "forwarder", "BlueWave Freight Forwarders", "Vessel is on schedule. I will ask the exporter for the COO today."),
    ]
    for u, role, org_name, body in talk:
        db.add(Comment(shipment_id=ship.id, user_id=u.id, author=u.name, org_name=org_name, party_role=role, body=body))
    db.commit()


TIMELINES = {
    "SP-2026-0001": (4, 6, None), "SP-2026-0002": (7, None, None), "SP-2026-0003": (3, 9, None), "SP-2026-0004": (1, 14, None),
    "SP-2026-0005": (4, 4, None), "SP-2026-0006": (5, None, "Customs asked for supporting invoices to check the declared value."), "SP-2026-0007": (4, 7, None),
}


def seed_timelines(db: Session) -> None:
    """Believable shipment progress for the demo shipments. Safe to run repeatedly."""
    from datetime import timedelta

    from app.models import TimelineEvent
    from app.services import timeline

    now = utcnow()
    for ref, (done, eta_days, hold_note) in TIMELINES.items():
        ship = db.query(Shipment).filter_by(reference=ref).first()
        if not ship:
            continue
        timeline.ensure_timeline(db, ship)
        rows = {e.key: e for e in db.query(TimelineEvent).filter_by(shipment_id=ship.id)}
        if any(e.status != "pending" for e in rows.values()):
            continue
        keys = [k for k, _ in timeline.STEPS]
        for i, key in enumerate(keys[:done]):
            if key == "customs_clearance":
                continue
            timeline.update_event(db, ship, key, status="done", planned_at=None, actual_at=(now - timedelta(days=(done - i) * 2)).isoformat(), note=None, actor="System")
        if done < 5 and done < len(keys):
            timeline.update_event(db, ship, keys[done], status="current", planned_at=None, actual_at=None, note=None, actor="System")
        if eta_days is not None:
            timeline.update_event(db, ship, "arrived_destination", status=None, planned_at=(now + timedelta(days=eta_days)).isoformat(), actual_at=None, note=None, actor="System")
        if hold_note:
            timeline.update_event(db, ship, "customs_clearance", status="delayed", planned_at=None, actual_at=None, note=hold_note, actor="System")
    db.commit()


LIBRARY = [
    ("SOP: Importing lithium-ion batteries", "sop-lithium.txt", """Standard operating procedure: lithium-ion battery imports

Before booking: confirm the cells are rechargeable lithium-ion, note the watt-hour rating, and ask the exporter for the UN 38.3 test summary and the Safety Data Sheet.

Documents we always collect: commercial invoice, packing list, bill of lading, certificate of origin, UN 38.3 test summary, Safety Data Sheet and the dangerous goods declaration.

Carrier rules: lithium-ion batteries ship as dangerous goods class 9 (UN3480 or UN3481). The carrier must accept the booking in writing before loading.

Classification note: rechargeable lithium-ion battery packs are normally classified under heading 8507, subheading 8507.60. Primary lithium cells are different. Always confirm the chemistry on the datasheet.

Escalate to the senior broker if the declared unit price is far below the usual market range or if the certificate of origin is missing at arrival."""),
    ("SOP: Responding to a customs valuation query", "sop-valuation.txt", """Standard operating procedure: valuation queries

When customs questions the declared value, do not argue the point by phone. Collect these before replying: the signed commercial invoice, proof of payment or the letter of credit, the purchase order, and any correspondence that explains an unusually low price.

Reply in writing within two working days. Keep the explanation short and attach evidence. Record the query in the shipment discussion so the importer and forwarder can see it.

If the price is genuinely lower than market because of volume discounts, attach the contract page that states the discount. Never edit an invoice to match a query. Escalate to the senior broker before agreeing to any revised value."""),
]


def seed_library(db: Session) -> None:
    """Two SOPs so the Library and the copilot can be shown without uploading anything."""
    from app.intelligence.errors import IntelligenceError
    from app.models import RagDocument
    from app.rag import indexer

    broker = db.query(User).filter_by(email=DEMO_EMAIL).first()
    if not broker or db.query(RagDocument).filter_by(org_id=broker.org_id).count():
        return
    try:
        for title, filename, text in LIBRARY:
            indexer.add_library_doc(db, broker.org_id, title, filename, text.encode(), "guidelines,sop", "System")
    except Exception as e:
        db.rollback()  # embeddings unavailable or deferred at boot: the library can be filled later
        import logging
        logging.getLogger(__name__).warning("seed_library deferred: %s", e)
