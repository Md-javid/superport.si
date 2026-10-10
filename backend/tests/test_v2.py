"""v2 intelligence tests. Gemini and SerpApi are replaced by mock HTTP transports that return
responses shaped like the documented APIs. They prove our wiring, validation and cost controls;
they do not prove the live services work (use scripts/smoke_live.py for that)."""
import json

import httpx
import pytest

from app.core.config import get_settings
from app.db import SessionLocal
from app.intelligence import gemini_client, hs_ranker, serpapi_client
from app.intelligence.errors import BudgetExceeded
from app.models import ApiCache, ApiUsage, Evidence, FeedbackEvent, Shipment
from app.services import hs_code

NEW = {
    "importer": "Meridian Power Systems Pvt Ltd", "exporter": "Shenzhen VoltEdge Technologies Co., Ltd",
    "origin": "China", "destination": "India", "port": "Chennai Port (INMAA)", "carrier": "Maersk Line",
    "container_number": "MSKU7294816", "product_description": "Lithium-ion battery packs, 48V 100Ah, for energy storage systems",
}
MODELS = {"models": [
    {"name": "models/gemini-3.5-flash-lite", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-3.8-flash", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-3.8-flash-image", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-3.8-pro", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/text-embedding-9", "supportedGenerationMethods": ["embedContent"]},
]}
DOC_VALUES = {"product": "Lithium-ion battery packs, 48V 100Ah", "quantity": "400 units", "unit_price": "612.50", "total_value": "245,000.00", "currency": "USD", "country_of_origin": "China", "consignee": "Meridian Power Systems Pvt Ltd", "shipper": "Shenzhen VoltEdge Technologies Co., Ltd", "incoterm": "FOB", "invoice_number": "INV-1", "packages": "400", "net_weight": "16,000 kg", "gross_weight": "17,200 kg", "container_number": "MSKU7294816", "bl_number": "BL1", "carrier": "Maersk Line", "vessel": "MV Test / 1", "port_of_loading": "Shenzhen", "port_of_discharge": "Chennai"}
GOOD_SNIPPET = "Subheading 8507.60 covers lithium-ion accumulators."


class Fake:
    def __init__(self):
        self.calls = {"serp": 0, "models": 0, "doc": 0, "hs": 0}
        self.serp_snippet = GOOD_SNIPPET
        self.serp_title = "Tariff heading 8507"
        self.gemini_status = 200
        self.hs_code = "8507.60"

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == "serpapi.com":
            self.calls["serp"] += 1
            assert request.url.params.get("api_key") == "test-serp"
            q = request.url.params.get("q", "")
            return httpx.Response(200, json={"organic_results": [
                {"title": self.serp_title, "link": "https://www.cbic.gov.in/page-" + str(abs(hash(q)) % 999), "snippet": self.serp_snippet},
                {"title": "Battery shipping guide", "link": "https://example.com/guide", "snippet": "General shipping advice."},
            ]})
        assert request.headers["x-goog-api-key"] == "test-gem"
        if request.url.path.endswith("/models"):
            self.calls["models"] += 1
            return httpx.Response(200, json=MODELS)
        if self.gemini_status != 200:
            return httpx.Response(self.gemini_status, json={"error": {"message": "API key not valid" if self.gemini_status == 400 else "quota"}})
        body = json.loads(request.content)
        parts = body["contents"][0]["parts"]
        if any("inline_data" in p for p in parts):
            self.calls["doc"] += 1
            payload = {"fields": {k: {"value": v, "confidence": 0.99} for k, v in DOC_VALUES.items()}}
        else:
            self.calls["hs"] += 1
            payload = {"candidates": [
                {"code": self.hs_code, "label": "Lithium-ion accumulators", "chapter": "Chapter 85: Electrical machinery", "confidence": 0.95, "evidence": [{"text": "Rechargeable lithium-ion packs", "source": 1}, {"text": "bogus citation", "source": 99}]},
                {"code": "8507.80", "label": "Other accumulators", "confidence": 0.3, "why_not": "Not lithium-ion."},
                {"code": "7799.99", "label": "Invalid chapter", "confidence": 0.2},
            ], "rationale": "These are rechargeable lithium-ion packs. Confirm the model before accepting.", "needs_info": ["Exact cell chemistry"]}
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}, "finishReason": "STOP"}], "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 60}})


@pytest.fixture
def live(monkeypatch):
    for k, v in {"INTELLIGENCE_MODE": "live", "GEMINI_API_KEY": "test-gem", "SERPAPI_API_KEY": "test-serp"}.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    with SessionLocal() as db:
        for model in (ApiCache, ApiUsage):
            db.query(model).delete()
        db.commit()
    fake = Fake()
    transport = httpx.MockTransport(fake.handler)
    serpapi_client.set_transport(transport)
    gemini_client.set_transport(transport)
    yield fake
    serpapi_client.set_transport(None)
    gemini_client.set_transport(None)
    monkeypatch.undo()
    get_settings.cache_clear()


def make_shipment(client, auth, ref):
    sid = client.post("/api/shipments", json={**NEW, "reference": ref}, headers=auth).json()["id"]
    for doc_type in ("commercial_invoice", "packing_list", "bill_of_lading"):
        r = client.post(f"/api/shipments/{sid}/documents", data={"doc_type": doc_type}, files={"file": ("scan.png", b"\x89PNG\r\n\x1a\n" + b"0" * 200, "image/png")}, headers=auth)
        assert r.status_code == 200
    return sid


def test_model_discovery_prefers_newest_text_models(live):
    fast, pro = gemini_client.pick_models(MODELS["models"])
    assert fast == "gemini-3.8-flash" and pro == "gemini-3.8-pro"  # not the image model, not 2.5, not embeddings


def test_serpapi_cache_budget_and_key_hidden(live):
    serpapi_client.search("google", {"q": "a"}, shipment_id=501)
    serpapi_client.search("google", {"q": "a"}, shipment_id=501)  # cached
    assert live.calls["serp"] == 1
    with SessionLocal() as db:
        assert all("test-serp" not in json.dumps(row.request) for row in db.query(ApiCache).all())
    get_settings().serpapi_budget_per_shipment = 2
    serpapi_client.search("google", {"q": "b"}, shipment_id=501)
    with pytest.raises(BudgetExceeded):
        serpapi_client.search("google", {"q": "c"}, shipment_id=501)


def test_full_live_flow_reads_scans_and_ranks_hs(client, auth, live):
    sid = make_shipment(client, auth, "SP-V2-0001")
    processed = client.post(f"/api/shipments/{sid}/process", headers=auth).json()
    invoice = next(d for d in processed["documents"] if d["doc_type"] == "commercial_invoice")
    assert invoice["meta"]["mode"] == "gemini-vision"
    total = next(f for f in invoice["fields"] if f["key"] == "total_value")
    assert total["source"] == "gemini-vision" and total["confidence"] <= 0.95

    confirmed = client.post(f"/api/shipments/{sid}/extraction/confirm", headers=auth).json()
    hs = confirmed["hs_result"]
    assert hs["engine"].startswith("gemini:gemini-3.8-pro") and hs["grounded"] == "code"
    assert hs["code"] == "8507.60" and hs["confidence"] <= 0.97
    assert [a["code"] for a in hs["alternatives"]] == ["8507.80"]  # invalid chapter 77 code dropped
    assert hs["sources"] and hs["sources"][0]["trust"] == "official"
    assert any(e.endswith("[1]") for e in hs["evidence"]) and not any("[99]" in e for e in hs["evidence"])
    assert hs["needs_info"] == ["Exact cell chemistry"]
    evidence = client.get(f"/api/shipments/{sid}/evidence", headers=auth).json()
    assert evidence and evidence[0]["kind"] == "hs"

    hs_calls, serp_calls = live.calls["hs"], live.calls["serp"]
    invoice_id = invoice["id"]
    client.patch(f"/api/shipments/{sid}/documents/{invoice_id}/fields/currency", json={"value": "EUR"}, headers=auth)
    client.post(f"/api/shipments/{sid}/hs/review", json={"action": "approve"}, headers=auth)
    assert (live.calls["hs"], live.calls["serp"]) == (hs_calls, serp_calls)  # edits and decisions cost nothing

    client.post(f"/api/shipments/{sid}/decision", json={"action": "reanalyze"}, headers=auth)
    assert live.calls["hs"] == hs_calls + 1  # explicit re-analysis does refresh

    with SessionLocal() as db:
        kinds = {f.kind for f in db.query(FeedbackEvent).filter_by(shipment_id=sid)}
    assert {"field_edit", "hs_decision", "final_decision"} <= kinds


def test_ungrounded_code_is_flagged_and_capped(client, auth, live):
    live.serp_snippet = "Nothing relevant here."
    live.serp_title = "Unrelated page"
    sid = make_shipment(client, auth, "SP-V2-0002")
    with SessionLocal() as db:
        shipment = db.get(Shipment, sid)
        hint = hs_code.recommend_rules(shipment, [])
        result = hs_ranker.rank(shipment, [], hint)
    assert result["grounded"] == "none" and result["confidence"] <= 0.8
    assert any("not found in the retrieved sources" in e for e in result["evidence"])


def test_gemini_outage_falls_back_visibly(client, auth, live):
    live.gemini_status = 429
    sid = make_shipment(client, auth, "SP-V2-0003")
    with SessionLocal() as db:
        shipment = db.get(Shipment, sid)
        result = hs_code.recommend(shipment, [])
    assert result["engine"] == "demo-rules-v0" and "unavailable" in result["fallback_reason"]


def test_unreadable_documents_are_not_fabricated_in_live_mode(client, auth, live):
    live.gemini_status = 400
    sid = make_shipment(client, auth, "SP-V2-0004")
    processed = client.post(f"/api/shipments/{sid}/process", headers=auth).json()
    for doc in processed["documents"]:
        assert doc["meta"]["mode"] == "unreadable" and "API key" in doc["meta"]["error"]
        assert all(f["value"] == "" and f["source"] == "not-found" for f in doc["fields"])


def test_seeded_demo_shipments_never_call_external_apis(client, auth, live):
    with SessionLocal() as db:
        shipment = db.query(Shipment).filter_by(reference="SP-2026-0001").one()
        assert shipment.is_demo
        result = hs_code.recommend(shipment, list(shipment.documents))
    assert result["engine"] == "demo-rules-v0" and sum(live.calls.values()) == 0


def test_status_endpoint_never_returns_keys(client, auth, live):
    body = client.get("/api/intelligence/status", headers=auth).json()
    assert body["mode"] == "live" and body["gemini"]["configured"] and body["serpapi"]["configured"]
    assert "test-gem" not in json.dumps(body) and "test-serp" not in json.dumps(body)
