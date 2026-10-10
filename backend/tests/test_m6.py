"""Milestone 6: timeline, tracking, ETA, Control Tower, Radar 2.0."""
from datetime import timedelta

import pytest

from app.db import SessionLocal
from app.models import Shipment, Signal, SignalMatch, utcnow
from app.radar import extract, service as radar
from app.tracking import iso6346
from tests.test_m5 import bearer, new_shipment, register, token_from


def test_iso6346_check_digit():
    assert iso6346.validate("CSQU3054383")["valid"] is True
    assert iso6346.validate("csqu 305438-3")["valid"] is True  # spaces, dashes and case are ignored
    bad = iso6346.validate("CSQU3054384")
    assert bad["valid"] is False and "check digit should be 3" in bad["reason"]
    assert iso6346.validate("ABC123")["valid"] is False


def joined_forwarder(client, auth, sid, email):
    token = token_from(client.post(f"/api/shipments/{sid}/invitations", json={"email": email, "party_role": "forwarder"}, headers=auth).json()["dev_link"])
    return bearer(register(client, email, org_name="Quick Freight " + email[:3], org_type="forwarder", invite=token))


def test_timeline_permissions_and_notifications(client, auth):
    sid = new_shipment(client, auth, "SP-M6-TL")
    ws = client.get(f"/api/shipments/{sid}/workspace", headers=auth).json()
    assert [e["key"] for e in ws["timeline"]][:2] == ["factory_pickup", "port_arrival_origin"] and len(ws["timeline"]) == 7
    fw = joined_forwarder(client, auth, sid, "tl-fw@example.com")

    assert client.post(f"/api/shipments/{sid}/timeline/loaded", json={"status": "done"}, headers=fw).status_code == 200
    assert client.post(f"/api/shipments/{sid}/timeline/customs_clearance", json={"status": "blocked", "note": "x"}, headers=fw).status_code == 403  # only the broker
    assert client.post(f"/api/shipments/{sid}/timeline/warehouse_delivery", json={"status": "done"}, headers=fw).status_code == 200
    assert client.post(f"/api/shipments/{sid}/timeline/factory_pickup", json={"status": "done"}, headers=fw).status_code == 200
    assert client.post(f"/api/shipments/{sid}/timeline/loaded", json={"status": "exploded"}, headers=fw).status_code == 422
    assert client.post(f"/api/shipments/{sid}/timeline/arrived_destination", json={"planned_at": "not a date"}, headers=fw).status_code == 422

    assert client.post(f"/api/shipments/{sid}/timeline/customs_clearance", json={"status": "blocked"}, headers=auth).status_code == 422  # a hold needs a reason
    assert client.post(f"/api/shipments/{sid}/timeline/customs_clearance", json={"status": "done"}, headers=auth).status_code == 422  # clearance is not set by hand
    assert client.post(f"/api/shipments/{sid}/timeline/customs_clearance", json={"status": "blocked", "note": "Customs hold: query on valuation"}, headers=auth).status_code == 200

    ws = client.get(f"/api/shipments/{sid}/workspace", headers=fw).json()
    steps = {e["key"]: e for e in ws["timeline"]}
    assert steps["loaded"]["status"] == "done" and steps["loaded"]["actual_at"] and steps["customs_clearance"]["status"] == "blocked"
    assert steps["loaded"]["can_update"] and not steps["customs_clearance"]["can_update"]
    kinds = [n["kind"] for n in client.get("/api/notifications", headers=auth).json()["items"]]
    assert "timeline" in kinds
    assert any(a["message"].startswith("Test Person updated") for a in ws["activity"])


def test_tracking_sample_provider_and_eta(client, auth):
    sid = new_shipment(client, auth, "SP-M6-TRK")
    fw = joined_forwarder(client, auth, sid, "trk-fw@example.com")
    imp = bearer(register(client, "trk-imp@example.com", org_name="Imp Co", org_type="importer"))
    assert client.get(f"/api/shipments/{sid}/workspace", headers=auth).json()["eta"]["eta"] is None  # no data, no invented ETA

    assert client.post(f"/api/shipments/{sid}/tracking/refresh", headers=imp).status_code == 404  # not on the shipment
    out = client.post(f"/api/shipments/{sid}/tracking/refresh", headers=fw)
    assert out.status_code == 200 and out.json()["sample"] is True and out.json()["provider"] == "sample" and out.json()["events"]
    ws = client.get(f"/api/shipments/{sid}/workspace", headers=auth).json()
    steps = {e["key"]: e for e in ws["timeline"]}
    assert steps["loaded"]["status"] == "done" and steps["loaded"]["source"] == "tracking"
    assert ws["eta"]["basis"] == "sample tracking" and ws["eta"]["confidence"] <= 0.5
    assert any(d["kind"] == "documents" for d in ws["eta"]["drivers"])  # the missing Certificate of Origin is a driver

    # something a person set by hand is never overwritten by tracking
    client.post(f"/api/shipments/{sid}/timeline/loaded", json={"status": "delayed", "note": "Cut-off missed"}, headers=fw)
    client.post(f"/api/shipments/{sid}/tracking/refresh", headers=auth)
    assert {e["key"]: e for e in client.get(f"/api/shipments/{sid}/workspace", headers=auth).json()["timeline"]}["loaded"]["status"] == "delayed"


def test_eta_uses_signals_by_confidence(client, auth):
    sid = new_shipment(client, auth, "SP-M6-ETA")
    client.post(f"/api/shipments/{sid}/timeline/arrived_destination", json={"planned_at": (utcnow() + timedelta(days=10)).date().isoformat()}, headers=auth)
    base = client.get(f"/api/shipments/{sid}/workspace", headers=auth).json()["eta"]
    assert base["basis"] == "planned arrival date" and base["confidence"] <= 0.6
    with SessionLocal() as db:
        sig = Signal(fingerprint="m6-eta-signal", event_type="congestion", title="Port congestion test", severity="high", confidence=0.8, verification="corroborated", sources=[], locations=[])
        db.add(sig)
        db.flush()
        db.add(SignalMatch(signal_id=sig.id, shipment_id=sid, reason="Discharge port"))
        db.commit()
    hit = client.get(f"/api/shipments/{sid}/workspace", headers=auth).json()["eta"]
    assert hit["delay_days"] >= base["delay_days"] + 2 and any(d["kind"] == "signal" for d in hit["drivers"])
    assert hit["eta"] > base["eta"] and hit["latest"] >= hit["eta"]


def test_control_tower_groups_exceptions_and_respects_access(client, auth):
    sid = new_shipment(client, auth, "SP-M6-CT")
    client.post(f"/api/shipments/{sid}/timeline/customs_clearance", json={"status": "blocked", "note": "Customs hold: valuation query"}, headers=auth)
    tower = client.get("/api/control-tower", headers=auth).json()
    mine = next(r for r in tower["shipments"] if r["reference"] == "SP-M6-CT")
    cats = {e["category"] for e in mine["exceptions"]}
    assert {"customs_hold", "missing_document"} <= cats and mine["severity"] == "red"
    assert tower["counts"]["customs_hold"] >= 1 and tower["counts"]["cleared"] >= 1  # SP-2026-0002 is cleared
    assert any(r["reference"] == "SP-2026-0006" and "customs_hold" in {e["category"] for e in r["exceptions"]} for r in tower["shipments"])  # seeded clearance delay

    other = bearer(register(client, "ct-other@example.com", org_name="Other CT Co"))
    assert client.get("/api/control-tower", headers=other).json()["total"] == 0


def test_radar_carrier_events_match_by_carrier():
    watch = {"ports": ["Chennai Port"], "countries": {"India"}, "products": [], "product_words": set(), "carriers": {"maersk"}}
    arts = [{"title": "Maersk announces blank sailings on Asia to India service", "snippet": "Several sailings are cancelled next month.", "url": "https://n.example/1", "source": "Shipping Times", "date": "1 day ago"}]
    events, engine = extract.heuristic_events(arts, watch)
    assert engine == "keyword-heuristic" and events[0]["event_type"] == "carrier" and events[0]["carriers"] == ["Maersk"]
    mine = Shipment(reference="X1", importer="a", exporter="b", origin="China", destination="India", port="Chennai Port (INMAA)", carrier="Maersk Line", container_number="C", product_description="p", stage="documents")
    other = Shipment(reference="X2", importer="a", exporter="b", origin="China", destination="India", port="Mundra", carrier="MSC", container_number="C", product_description="p", stage="documents")
    matched = radar.match_shipments(events[0], [mine, other])
    assert [s.reference for s, _ in matched] == ["X1"] and matched[0][1] == "Carrier: Maersk Line"
    queries = radar.build_queries({**watch, "shipments": [mine]}, 8)
    assert any("Maersk" in q and "blank sailing" in q for q in queries) and any("weather warning" in q for q in queries)
