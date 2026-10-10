"""Milestone 3 (price / company / rules checks) and 4 (Trade Signal Radar) tests.
Mock HTTP transports return responses shaped like the documented SerpApi and Gemini APIs."""
import json

import httpx
import pytest

from app.core.config import get_settings
from app.db import SessionLocal
from app.intelligence import gemini_client, serpapi_client
from app.intelligence.errors import BudgetExceeded
from app.models import ApiCache, ApiUsage, AuditEvent, FeedbackEvent, Signal, SignalMatch, SignalReview
from tests.test_v2 import Fake, make_shipment

ARTICLES = [
    {"title": "Chennai Port congestion builds as yard fills", "link": "https://news.example/a1", "source": "Maritime Daily", "date": "2 hours ago", "snippet": "Container dwell times rise at Chennai Port."},
    {"title": "Shipping lines warn of Chennai Port delays", "link": "https://news.example/a2", "source": "Shipping Times", "date": "5 hours ago", "snippet": "Carriers warn of delays."},
    {"title": "Local football results", "link": "https://news.example/a3", "source": "Sports Page", "date": "1 day ago", "snippet": "Unrelated."},
]


class Fake2(Fake):
    def __init__(self):
        super().__init__()
        self.calls.update({"gem": 0})
        self.log = []

    def handler(self, request):
        if request.url.host == "serpapi.com":
            self.calls["serp"] += 1
            self.log.append((request.url.params.get("engine"), request.url.params.get("tbm"), request.url.params.get("q", "")[:60]))
            p = request.url.params
            engine, q = p.get("engine"), p.get("q", "")
            if engine == "google_shopping":
                prices = [600, 650, 700, 720, 5, 690]
                return httpx.Response(200, json={"shopping_results": [{"title": f"48V 100Ah battery {i}", "price": f"${v}", "extracted_price": v, "source": f"Store {i}", "product_link": f"https://shop.example/{i}"} for i, v in enumerate(prices, 1)]})
            if engine == "google_maps":
                if "VoltEdge" in q:
                    return httpx.Response(200, json={"error": "Google Maps hasn't returned any results for this query."})
                return httpx.Response(200, json={"local_results": [{"title": "Meridian Power Systems Pvt Ltd", "address": "Chennai, India", "rating": 4.4, "reviews": 31, "website": "https://meridian.example"}]})
            if engine == "google" and p.get("tbm") == "nws":
                if "VoltEdge" in q:
                    return httpx.Response(200, json={"news_results": [{"title": "VoltEdge Technologies accused in customs fraud case", "link": "https://news.example/voltedge", "source": "Example News", "date": "1 day ago", "snippet": "Prosecutors allege under-invoicing."}]})
                if "congestion OR strike" in q:
                    return httpx.Response(200, json={"news_results": ARTICLES})
                return httpx.Response(200, json={"news_results": []})
            self.calls["serp"] -= 1  # the base class counts organic searches itself
            return super().handler(request)
        if not request.url.path.endswith("/models") and self.gemini_status == 200:
            body = json.loads(request.content)
            text = "".join(part.get("text", "") for part in body["contents"][0]["parts"])
            payload = None
            if '"comparable"' in text:
                payload = {"comparable": [1, 2, 3, 4, 6], "notes": "Excluded a board accessory."}
            elif '"verdicts"' in text:
                payload = {"verdicts": [{"party": 1, "index": 1, "verdict": "adverse", "reason": "Names the same company in a customs fraud case."}]}
            elif '"duty_notes"' in text:
                payload = {"restrictions": [{"text": "Rechargeable lithium batteries need BIS registration.", "source": 1}, {"text": "Uncited claim", "source": 99}, {"text": "No source at all"}],
                           "certificates": [{"name": "BIS registration", "level": "required", "source": 2}], "duty_notes": [{"text": "Basic customs duty applies.", "source": 1}]}
            elif '"events"' in text:
                payload = {"events": [{"title": "Chennai Port congestion", "event_type": "congestion", "summary": "Yard congestion is lengthening dwell times.", "severity": "high", "ports": ["Chennai Port"], "countries": ["India"], "products": [], "articles": [1, 2]},
                                      {"title": "Ghost event", "event_type": "strike", "articles": [99]}]}
            if payload is not None:
                self.calls["gem"] += 1
                return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}, "finishReason": "STOP"}], "usageMetadata": {"promptTokenCount": 50, "candidatesTokenCount": 30}})
        return super().handler(request)


def _reset_db():
    with SessionLocal() as db:
        for model in (ApiCache, ApiUsage, SignalReview, SignalMatch, Signal):
            db.query(model).delete()
        db.commit()


@pytest.fixture
def live2(monkeypatch):
    for k, v in {"INTELLIGENCE_MODE": "live", "GEMINI_API_KEY": "test-gem", "SERPAPI_API_KEY": "test-serp"}.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    _reset_db()
    fake = Fake2()
    transport = httpx.MockTransport(fake.handler)
    serpapi_client.set_transport(transport)
    gemini_client.set_transport(transport)
    yield fake
    serpapi_client.set_transport(None)
    gemini_client.set_transport(None)
    monkeypatch.undo()
    get_settings.cache_clear()


@pytest.fixture
def fixtures_mode(monkeypatch):
    monkeypatch.setenv("INTELLIGENCE_MODE", "fixtures")
    get_settings.cache_clear()
    _reset_db()
    yield
    monkeypatch.undo()
    get_settings.cache_clear()


def seeded_id(client, auth, ref):
    return next(s["id"] for s in client.get("/api/shipments", headers=auth).json() if s["reference"] == ref)


def test_daily_cap_protects_the_wallet(client, live2, monkeypatch):
    monkeypatch.setenv("SERPAPI_DAILY_CAP", "1")
    get_settings.cache_clear()
    serpapi_client.search("google", {"q": "one"})
    with pytest.raises(BudgetExceeded):
        serpapi_client.search("google", {"q": "two"})


def test_market_checks_full_flow(client, auth, live2):
    early = make_shipment(client, auth, "SP-M3-0000")
    assert client.post(f"/api/shipments/{early}/verify", json={}, headers=auth).status_code == 409  # needs HS first

    sid = make_shipment(client, auth, "SP-M3-0001")
    client.post(f"/api/shipments/{sid}/process", headers=auth)
    client.post(f"/api/shipments/{sid}/extraction/confirm", headers=auth)
    serp_before = live2.calls["serp"]
    d = client.post(f"/api/shipments/{sid}/verify", json={}, headers=auth)
    assert d.status_code == 200
    intel = d.json()["intel"]

    price = intel["price"]
    assert price["status"] == "ok" and price["level"] == "low" and price["filtered_by_ai"] and price["source_mode"] == "live"
    assert price["market"]["median"] == 690 and price["ratio"] == 0.89

    company = intel["company"]
    importer, exporter = company["parties"]
    assert importer["level"] == "low" and importer["place"]["title"].startswith("Meridian")
    assert exporter["level"] == "high" and exporter["articles"][0]["verdict"] == "adverse" and company["screened_by_ai"]

    rules = intel["rules"]
    assert rules["status"] == "ok" and len(rules["restrictions"]) == 1 and rules["dropped_uncited"] >= 2
    assert rules["certificates"][0]["name"] == "BIS registration"

    comp = d.json()["compliance"]
    assert comp["restrictions"][0].endswith("[1]") and comp["rules_basis"].startswith("web sources")
    assert next(i for i in comp["items"] if i["id"] == "counterparties")["status"] == "issue"
    assert comp["overall"] == "action_required"
    factors = {f["key"]: f for f in d.json()["risk"]["factors"]}
    assert "counterparty" in factors and factors["value_anomaly"]["basis"] == "live market prices"
    assert abs(sum(f["weight"] for f in factors.values()) - 1.0) < 0.01

    kinds = {e["kind"] for e in client.get(f"/api/shipments/{sid}/evidence", headers=auth).json()}
    assert {"hs", "price", "company", "rules"} <= kinds

    spent = live2.calls["serp"] - serp_before
    assert spent == 7  # 1 shopping + 4 company + 2 rules
    client.post(f"/api/shipments/{sid}/verify", json={}, headers=auth)
    assert live2.calls["serp"] - serp_before == spent  # second click is served from cache
    client.post(f"/api/shipments/{sid}/verify", json={"force": True, "parts": ["price"]}, headers=auth)
    assert live2.calls["serp"] - serp_before == spent + 1

    client.post(f"/api/shipments/{sid}/hs/review", json={"action": "approve"}, headers=auth)
    assert client.post(f"/api/shipments/{sid}/decision", json={"action": "approve"}, headers=auth).status_code == 422  # adverse news needs a justification
    ok = client.post(f"/api/shipments/{sid}/decision", json={"action": "approve", "note": "Reviewed the article; different entity."}, headers=auth)
    assert ok.status_code == 200 and ok.json()["stage"] == "ready"


def test_demo_shipments_use_labelled_samples_and_cost_nothing(client, auth, live2):
    sid = seeded_id(client, auth, "SP-2026-0001")
    intel = client.post(f"/api/shipments/{sid}/verify", json={}, headers=auth).json()["intel"]
    assert intel["price"]["status"] == "ok" and intel["price"]["source_mode"] == "fixture"
    assert intel["rules"]["status"] == "sources_only" and intel["company"]["source_mode"] == "fixture"
    assert live2.calls["serp"] == 0 and live2.calls["gem"] == 0


def test_verify_is_disabled_when_intelligence_is_off(client, auth):
    sid = seeded_id(client, auth, "SP-2026-0001")
    r = client.post(f"/api/shipments/{sid}/verify", json={}, headers=auth)
    assert r.status_code == 409 and "INTELLIGENCE_MODE" in r.json()["detail"]


def test_radar_live_scan_verifies_dedupes_and_matches(client, auth, live2):
    sid = make_shipment(client, auth, "SP-M4-0001")
    summary = client.post("/api/radar/scan", json={}, headers=auth).json()
    assert summary["engine"].startswith("gemini:") and summary["new"] == 1 and summary["events"] == 1  # the ghost event had no real article

    signals = client.get("/api/radar/signals", headers=auth).json()
    sig = next(s for s in signals if s["title"] == "Chennai Port congestion")
    assert sig["verification"] == "corroborated" and sig["confidence"] == 0.6 and len(sig["sources"]) == 2 and sig["severity"] == "high"
    refs = {a["reference"] for a in sig["affected"]}
    assert {"SP-M4-0001", "SP-2026-0001"} <= refs
    assert any(s["id"] for s in client.get(f"/api/shipments/{sid}/signals", headers=auth).json())

    again = client.post("/api/radar/scan", json={}, headers=auth).json()
    assert again["new"] == 0 and again["updated"] == 1  # same event is not duplicated

    r = client.post(f"/api/radar/signals/{sig['id']}/review", json={"action": "acknowledge", "note": "Informed the importer."}, headers=auth)
    assert r.status_code == 200 and r.json()["status"] == "acknowledged"
    assert all(s["id"] != sig["id"] for s in client.get("/api/radar/signals", headers=auth).json())
    with SessionLocal() as db:
        assert db.query(AuditEvent).filter_by(shipment_id=sid, action="signal_acknowledge").count() == 1
        assert db.query(FeedbackEvent).filter_by(shipment_id=sid, kind="signal_review").count() == 1
    assert client.post(f"/api/radar/signals/{sig['id']}/review", json={"action": "explode"}, headers=auth).status_code == 422


def test_radar_works_without_keys_in_fixtures_mode(client, auth, fixtures_mode):
    summary = client.post("/api/radar/scan", json={}, headers=auth).json()
    assert summary["engine"] == "keyword-heuristic" and summary["sample"] is True
    signals = client.get("/api/radar/signals", headers=auth).json()
    types = {s["event_type"] for s in signals}
    assert {"congestion", "tariff_change"} <= types
    congestion = next(s for s in signals if s["event_type"] == "congestion")
    assert congestion["source_mode"] == "fixture" and congestion["verification"] == "corroborated"
    duty = next(s for s in signals if s["event_type"] == "tariff_change")
    assert any("lithium" in a["reason"] for a in duty["affected"])  # only battery shipments are affected by a battery duty change


def test_radar_off_mode_is_refused(client, auth):
    assert client.post("/api/radar/scan", json={}, headers=auth).status_code == 409
