import pytest
from app.db import SessionLocal
from app.models import Shipment
from app.services import workflow


def test_inconsistency_resolution_and_risk_reduction(client, auth):
    # Create shipment with deliberate container and consignee mismatch
    r = client.post(
        "/api/shipments",
        json={
            "reference": "SP-TEST-RESOLVE-1",
            "importer": "BlueWave Electronics Pvt Ltd",
            "exporter": "Shenzhen Solar Co",
            "origin": "China",
            "destination": "India",
            "port": "Chennai",
            "carrier": "Maersk",
            "container_number": "CSNU1234567",
            "product_description": "Lithium-ion batteries 48V",
        },
        headers=auth,
    )
    assert r.status_code == 201
    sid = r.json()["id"]

    # Attach sample docs and process
    client.post(f"/api/shipments/{sid}/documents/samples", headers=auth)
    client.post(f"/api/shipments/{sid}/process", headers=auth)
    client.post(f"/api/shipments/{sid}/extraction/confirm", headers=auth)

    detail = client.get(f"/api/shipments/{sid}", headers=auth).json()
    initial_risk = detail["risk_score"]
    incs = detail["compliance"]["inconsistencies"]
    assert len(incs) > 0

    # 1. Test single apply action: sync container number from Bill of Lading
    r_apply = client.post(
        f"/api/shipments/{sid}/inconsistencies/resolve",
        json={"action": "apply", "field": "Container number", "chosen_value": "MSKU7294816"},
        headers=auth,
    )
    assert r_apply.status_code == 200
    updated = r_apply.json()
    assert updated["container_number"] == "MSKU7294816"
    cnt_issues = [i for i in updated["compliance"]["inconsistencies"] if i["field"] == "Container number" and not i.get("resolved")]
    assert len(cnt_issues) == 0

    # 2. Test dismiss action: accept Consignee trade name variation
    r_dismiss = client.post(
        f"/api/shipments/{sid}/inconsistencies/resolve",
        json={"action": "dismiss", "field": "Consignee", "note": "Verified trade alias"},
        headers=auth,
    )
    assert r_dismiss.status_code == 200
    dismissed = r_dismiss.json()
    open_consignee = [i for i in dismissed["compliance"]["inconsistencies"] if i["field"] == "Consignee" and not i.get("resolved")]
    assert len(open_consignee) == 0

    # 3. Test reconcile all action
    r_all = client.post(f"/api/shipments/{sid}/reconcile", headers=auth)
    assert r_all.status_code == 200
    all_res = r_all.json()
    open_incs = [i for i in all_res["compliance"]["inconsistencies"] if not i.get("resolved")]
    assert len(open_incs) == 0
    assert all_res["risk_score"] < initial_risk
    doc_consistency_factor = next(f for f in all_res["risk"]["factors"] if f["key"] == "document_consistency")
    assert doc_consistency_factor["score"] == 0
