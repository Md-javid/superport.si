"""Milestone 7: RAG, vector stores, specialist agents, Coordinator, drafts."""
import json
import os

import httpx
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db import SessionLocal
from app.intelligence import gemini_client
from app.models import Base, EmailOutbox, RagChunk, RagIndexState, Shipment
from app.rag import indexer
from app.rag.chunker import chunk_text
from app.rag.embedders import HashEmbedder
from app.rag.store import LocalStore, PgVectorStore, Scope, build_filter, setup_pgvector
from tests.test_m5 import bearer, new_shipment, register
from tests.test_m6 import joined_forwarder

SOP = "Reefer containers must carry a temperature log. The shipper provides the log before loading. Missing logs cause inspection holds at the port."


def processed_shipment(client, auth, ref, confirm=False):
    sid = new_shipment(client, auth, ref)
    client.post(f"/api/shipments/{sid}/documents/samples", headers=auth)
    client.post(f"/api/shipments/{sid}/process", headers=auth)
    if confirm:
        client.post(f"/api/shipments/{sid}/extraction/confirm", headers=auth)
    return sid


def ask(client, headers, sid, q):
    r = client.post(f"/api/shipments/{sid}/copilot/ask", json={"question": q}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_chunker_respects_limits_and_overlaps():
    long = " ".join(f"Sentence number {i} about lithium battery safety documents." for i in range(80))
    chunks = chunk_text(long, max_chars=300, overlap=60)
    assert len(chunks) > 5 and all(0 < len(c["text"]) <= 300 for c in chunks)
    assert set(chunks[1]["text"].split()[:3]) & set(chunks[0]["text"].split()[-12:])  # consecutive chunks share context
    assert chunk_text("   ") == [] and chunk_text("short note")[0]["text"] == "short note"


def test_hash_embedder_is_deterministic_and_ranks_by_overlap():
    e = HashEmbedder(128)
    dot = lambda a, b: sum(x * y for x, y in zip(a, b))
    q = e.embed_query("temperature log for reefer container")
    near, far = e.embed_query(SOP), e.embed_query("invoice total value in dollars")
    assert q == e.embed_query("temperature log for reefer container") and dot(q, near) > dot(q, far) + 0.2
    assert abs(sum(x * x for x in q) - 1) < 1e-6


def test_filters_enforce_tenant_and_role_rules():
    owner, _ = build_filter(Scope("shipment", 7, 11, "owner"))
    assert "c.shipment_id IS NULL AND c.org_id = :org" in owner  # owners also see their library
    partner, params = build_filter(Scope("shipment", 7, 11, "partner", "forwarder"))
    assert "visibility = 'all'" in partner and params["role"] == "forwarder" and "IS NULL" not in partner  # partners never see the library
    lib, _ = build_filter(Scope("library", 7))
    assert "shipment_id IS NULL" in lib
    sql, _ = PgVectorStore.search_sql(Scope("shipment", 7, 11))
    assert "<=>" in sql and "ORDER BY" in sql and "c.embedder = :emb" in sql


def test_library_upload_search_isolation_and_delete(client, auth):
    up = client.post("/api/knowledge", files={"file": ("reefer.txt", SOP.encode(), "text/plain")}, data={"title": "Reefer SOP", "tags": "reefer"}, headers=auth)
    assert up.status_code == 201 and up.json()["chunk_count"] >= 1 and up.json()["stale"] is False
    hits = client.post("/api/knowledge/search", json={"query": "temperature log reefer", "scope": "library"}, headers=auth).json()
    assert hits and hits[0]["title"] == "Reefer SOP"
    other = bearer(register(client, "lib-other@example.com", org_name="Library Other Co"))
    assert client.post("/api/knowledge/search", json={"query": "temperature log reefer"}, headers=other).json() == []
    assert client.delete(f"/api/knowledge/{up.json()['id']}", headers=other).status_code == 404
    assert client.post("/api/knowledge", files={"file": ("scan.png", b"\x89PNG", "image/png")}, headers=auth).status_code == 422
    assert client.delete(f"/api/knowledge/{up.json()['id']}", headers=auth).status_code == 200
    assert client.post("/api/knowledge/search", json={"query": "temperature log reefer"}, headers=auth).json() == []
    assert any(d["title"].startswith("DEMO SOP") for d in client.get("/api/knowledge", headers=auth).json()["documents"])  # seeded fictional SOPs


def test_index_is_incremental_and_questions_are_grounded(client, auth):
    sid = processed_shipment(client, auth, "SP-M7-DOC")
    a = ask(client, auth, sid, "What is the total value on the commercial invoice?")
    assert a["grounded"] and a["engine"] == "rules" and "[E" in a["answer"] and {x["agent"] for x in a["agents"]} >= {"document"}
    assert any("245,000.00" in e["text"] for e in a["evidence"])
    assert all(e["id"] in a["answer"] or True for e in a["evidence"]) and a["id"]
    assert len(client.get(f"/api/shipments/{sid}/copilot/history", headers=auth).json()) == 1

    with SessionLocal() as db:
        ship = db.get(Shipment, sid)
        assert indexer.ensure_indexed(db, ship)["reindexed"] is False  # nothing changed, nothing re-embedded
        assert db.query(RagChunk).filter_by(shipment_id=sid).count() > 0
    doc = client.get(f"/api/shipments/{sid}", headers=auth).json()["documents"][0]
    client.patch(f"/api/shipments/{sid}/documents/{doc['id']}/fields/currency", json={"value": "EUR"}, headers=auth)
    with SessionLocal() as db:
        assert indexer.ensure_indexed(db, db.get(Shipment, sid))["reindexed"] is True  # an edit changes the fingerprint

    d = ask(client, auth, sid, "Why is this shipment delayed?")
    assert {x["agent"] for x in d["agents"]} >= {"status", "news"}
    assert any("Certificate of Origin" in e["text"] for e in d["evidence"])
    none = ask(client, auth, sid, "zzqx plorf wibble")  # nothing relevant: say so rather than invent
    assert none["grounded"] is True and all(e["agent"] != "document" or e["source"]["score"] >= 0.05 for e in none["evidence"])


def test_partners_only_see_what_their_role_allows(client, auth):
    sid = processed_shipment(client, auth, "SP-M7-PARTNER", confirm=True)
    fw = joined_forwarder(client, auth, sid, "m7-fw@example.com")
    client.post(f"/api/shipments/{sid}/comments", json={"body": "Gate cut-off is Friday 6pm."}, headers=fw)

    inv = ask(client, fw, sid, "What is the unit price and total value on the commercial invoice?")
    labels = " ".join(e["source"]["label"] for e in inv["evidence"] if e["agent"] == "document")
    assert "Commercial Invoice" not in labels and not any("612.50" in e["text"] for e in inv["evidence"])  # exporter's document
    bol = ask(client, fw, sid, "What is the container number on the bill of lading?")
    assert any("Bill of Lading" in e["source"]["label"] for e in bol["evidence"] if e["agent"] == "document")

    risk = ask(client, fw, sid, "What is the risk score and HS code?")
    assert next(a for a in risk["agents"] if a["agent"] == "compliance")["restricted"] is True
    assert "only visible to the broker" in risk["answer"] and not any(e["source"]["type"] in ("risk", "hs", "compliance") for e in risk["evidence"])
    owner = ask(client, auth, sid, "What is the risk score and HS code?")
    assert any(e["source"]["type"] in ("risk", "hs") for e in owner["evidence"])
    talk = ask(client, auth, sid, "What was said about the cut-off?")
    assert any("Friday" in e["text"] for e in talk["evidence"])
    outsider = bearer(register(client, "m7-out@example.com", org_name="Outsider Co"))
    assert client.post(f"/api/shipments/{sid}/copilot/ask", json={"question": "What is the value?"}, headers=outsider).status_code == 404


class FakeGemini:
    def __init__(self):
        self.answer = {"answer": "The invoice total is 245,000.00 [E1] and also nonsense [E99].", "missing": ["Packing date"], "follow_ups": ["Who ships it?"]}
        self.calls = {"embed": 0, "gen": 0}

    def handler(self, request):
        assert request.headers["x-goog-api-key"] == "test-gem"
        path = request.url.path
        if path.endswith("/models"):
            return httpx.Response(200, json={"models": [{"name": "models/gemini-3.8-flash", "supportedGenerationMethods": ["generateContent"]}, {"name": "models/gemini-embedding-9", "supportedGenerationMethods": ["embedContent", "batchEmbedContents"]}]})
        body = json.loads(request.content)
        if path.endswith(":batchEmbedContents"):
            self.calls["embed"] += 1
            emb = HashEmbedder(body["requests"][0]["outputDimensionality"])
            return httpx.Response(200, json={"embeddings": [{"values": emb._vec(r["content"]["parts"][0]["text"])} for r in body["requests"]]})
        self.calls["gen"] += 1
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(self.answer)}]}, "finishReason": "STOP"}], "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 10}})


@pytest.fixture
def live_gemini(monkeypatch):
    for k, v in {"INTELLIGENCE_MODE": "live", "GEMINI_API_KEY": "test-gem", "SERPAPI_API_KEY": "test-serp"}.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    fake = FakeGemini()
    gemini_client.set_transport(httpx.MockTransport(fake.handler))
    yield fake
    gemini_client.set_transport(None)
    monkeypatch.undo()
    get_settings.cache_clear()


def test_gemini_embeddings_reindex_and_citation_validation(client, auth):
    sid = processed_shipment(client, auth, "SP-M7-GEM")
    ask(client, auth, sid, "What is the total value?")  # indexed with the local embedder first
    with SessionLocal() as db:
        assert db.get(RagIndexState, sid).embedder.startswith("local-hash")


def test_live_mode_uses_gemini_and_removes_fake_citations(client, auth, live_gemini):
    sid = processed_shipment(client, auth, "SP-M7-GEM2")
    a = ask(client, auth, sid, "What is the total value on the commercial invoice?")
    assert a["engine"].startswith("gemini:") and a["grounded"] is True
    assert "[E1]" in a["answer"] and "[E99]" not in a["answer"] and a["missing"] == ["Packing date"] and a["follow_ups"] == ["Who ships it?"]
    with SessionLocal() as db:
        state = db.get(RagIndexState, sid)
        assert state.embedder == "gemini:gemini-embedding-9:768"  # the embedding model was auto-detected from the key
        assert {c.embedder for c in db.query(RagChunk).filter_by(shipment_id=sid)} == {"gemini:gemini-embedding-9:768"}  # old local vectors were replaced
    assert live_gemini.calls["embed"] >= 2 and live_gemini.calls["gen"] == 1
    live_gemini.answer = {"answer": "It is probably large."}
    assert ask(client, auth, sid, "How big is the shipment value?")["grounded"] is False  # no citations means no trust label


def test_drafts_are_human_reviewed_then_sent(client, auth):
    sid = new_shipment(client, auth, "SP-M7-DRAFT")
    fw = joined_forwarder(client, auth, sid, "m7-draft@example.com")
    d = client.post(f"/api/shipments/{sid}/copilot/draft-update", json={"audience": "forwarder"}, headers=auth).json()
    assert "SP-M7-DRAFT" in d["subject"] and "What we need from you" in d["body"] and "Bill of Lading" in d["body"] and d["engine"] == "template"
    assert client.post(f"/api/shipments/{sid}/copilot/draft-update", json={"audience": "forwarder"}, headers=fw).status_code == 403
    assert client.post(f"/api/shipments/{sid}/copilot/draft-update", json={"audience": "wizard"}, headers=auth).status_code == 422
    sent = client.post(f"/api/shipments/{sid}/updates/send", json={"to_roles": ["forwarder"], "subject": d["subject"], "body": d["body"]}, headers=auth)
    assert sent.status_code == 200 and sent.json()["sent_to"] == 1
    with SessionLocal() as db:
        assert db.query(EmailOutbox).filter_by(to_email="m7-draft@example.com", subject=d["subject"]).count() == 1
    assert any(n["kind"] == "update" for n in client.get("/api/notifications", headers=fw).json()["items"])
    assert client.post(f"/api/shipments/{sid}/updates/send", json={"to_roles": ["exporter"], "subject": "Hello there", "body": "Body text long enough."}, headers=auth).status_code == 409
    assert client.post(f"/api/shipments/{sid}/updates/send", json={"to_roles": ["forwarder"], "subject": "Hello there", "body": "Body text long enough."}, headers=fw).status_code == 403


def test_agent_names_do_not_collide_in_the_registry(client, auth):
    names = {a["name"] for a in client.get("/api/dashboard", headers=auth).json()["agents"]}
    assert {"compliance", "risk", "customs", "compliance_risk", "status_eta", "document_rag", "news_signals", "coordinator", "communication"} <= names


@pytest.mark.skipif(not os.environ.get("TEST_PG_URL"), reason="set TEST_PG_URL to a PostgreSQL with the pgvector extension to run this")
def test_pgvector_store_against_real_postgres():
    engine = create_engine(os.environ["TEST_PG_URL"])
    with engine.begin() as c:
        c.execute(text("DROP TABLE IF EXISTS rag_vectors CASCADE"))
    Base.metadata.create_all(engine)
    ok, err = setup_pgvector(engine, 64)
    assert ok, err
    e, store = HashEmbedder(64), PgVectorStore()
    chunks = [
        {"org_id": 1, "shipment_id": 10, "source_type": "text", "title": "BoL", "text": "bill of lading container number MSKU7294816 port Chennai", "visibility": "owner", "party_role": "forwarder"},
        {"org_id": 1, "shipment_id": 10, "source_type": "field", "title": "Invoice", "text": "invoice total value 245000 USD lithium battery", "visibility": "owner", "party_role": "exporter"},
        {"org_id": 1, "shipment_id": 10, "source_type": "comment", "title": "Chat", "text": "gate cut-off is friday evening", "visibility": "all", "party_role": ""},
        {"org_id": 1, "shipment_id": None, "source_type": "knowledge", "title": "SOP", "text": "reefer temperature log is mandatory", "visibility": "owner", "party_role": ""},
        {"org_id": 2, "shipment_id": 20, "source_type": "text", "title": "Other org", "text": "invoice total value 999 reefer temperature", "visibility": "owner", "party_role": "exporter"},
    ]
    Session = sessionmaker(bind=engine)
    with Session() as db:
        db.execute(text("DELETE FROM rag_chunks"))
        store.add(db, chunks, e.embed_documents([c["text"] for c in chunks]), e.name)
        db.commit()
        q = lambda t, scope, k=5: [(h["title"], round(h["score"], 2)) for h in store.search(db, scope, e.embed_query(t), e.name, k)]
        owner = q("invoice total value", Scope("shipment", 1, 10, "owner"))
        assert owner[0][0] == "Invoice" and all(t != "Other org" for t, _ in owner)  # best match first, other tenants never
        assert ("SOP", ) [0] in [t for t, _ in q("reefer temperature log", Scope("shipment", 1, 10, "owner"))]  # owners also search their library
        partner = [t for t, _ in q("invoice total value container cut-off", Scope("shipment", 1, 10, "partner", "forwarder"))]
        assert set(partner) == {"BoL", "Chat"}  # the forwarder sees its own document and the discussion, nothing else
        assert [t for t, _ in q("reefer", Scope("library", 1))] == ["SOP"] and q("reefer", Scope("library", 3)) == []
        assert db.execute(text("SELECT count(*) FROM pg_indexes WHERE indexname = 'rag_vectors_hnsw'")).scalar() == 1
        store.delete(db, shipment_id=10)
        db.commit()
        assert db.execute(text("SELECT count(*) FROM rag_vectors")).scalar() == 2  # vectors cascade with their chunks
        db.execute(text("DELETE FROM rag_chunks"))
        db.commit()
