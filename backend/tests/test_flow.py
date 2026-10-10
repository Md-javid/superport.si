from pathlib import Path

SAMPLES = Path(__file__).resolve().parent.parent / "app" / "sample_data"

NEW = {
    "importer": "Meridian Power Systems Pvt Ltd",
    "exporter": "Shenzhen VoltEdge Technologies Co., Ltd",
    "origin": "China",
    "destination": "India",
    "port": "Chennai Port (INMAA)",
    "carrier": "Maersk Line",
    "container_number": "MSKU7294816",
    "product_description": "Lithium-ion battery packs, 48V 100Ah, for energy storage systems",
}


def test_requires_auth(client):
    assert client.get("/api/shipments").status_code == 401


def test_login_and_bad_password(client):
    ok = client.post("/api/auth/login", json={"email": "demo@superport.ai", "password": "superport-demo"})
    assert ok.status_code == 200 and ok.json()["token"]
    bad = client.post("/api/auth/login", json={"email": "demo@superport.ai", "password": "nope"})
    assert bad.status_code == 401


def test_dashboard_kpis(client, auth):
    data = client.get("/api/dashboard", headers=auth).json()
    assert data["kpis"]["active_shipments"] >= 1
    assert any(a["status"] == "planned" for a in data["agents"])


def test_end_to_end_with_real_pdfs(client, auth):
    created = client.post("/api/shipments", json=NEW, headers=auth)
    assert created.status_code == 201
    sid = created.json()["id"]
    assert created.json()["stage"] == "documents"

    for doc_type, name in (("commercial_invoice", "commercial_invoice.pdf"), ("packing_list", "packing_list.pdf"), ("bill_of_lading", "bill_of_lading.pdf")):
        with open(SAMPLES / name, "rb") as fh:
            r = client.post(f"/api/shipments/{sid}/documents", data={"doc_type": doc_type}, files={"file": (name, fh, "application/pdf")}, headers=auth)
        assert r.status_code == 200

    processed = client.post(f"/api/shipments/{sid}/process", headers=auth).json()
    assert processed["stage"] == "extraction_review"
    invoice = next(d for d in processed["documents"] if d["doc_type"] == "commercial_invoice")
    assert invoice["meta"]["mode"] == "extracted-from-file"
    assert next(f for f in invoice["fields"] if f["key"] == "total_value")["value"] == "245,000.00"

    # Human edit is recorded and flagged
    field = client.patch(f"/api/shipments/{sid}/documents/{invoice['id']}/fields/currency", json={"value": "EUR"}, headers=auth)
    assert field.status_code == 200
    edited = next(f for d in field.json()["documents"] for f in d["fields"] if f["key"] == "currency" and d["doc_type"] == "commercial_invoice")
    assert edited["edited"] is True

    confirmed = client.post(f"/api/shipments/{sid}/extraction/confirm", headers=auth).json()
    assert confirmed["stage"] == "hs_review"
    assert confirmed["hs_result"]["code"] == "8507.60"
    assert confirmed["hs_decision"] is None
    assert any(i["field"] == "Gross weight" for i in confirmed["compliance"]["inconsistencies"])
    assert "not a customs authority decision" in confirmed["risk"]["disclaimer"]

    # Cannot approve before the HS gate
    early = client.post(f"/api/shipments/{sid}/decision", json={"action": "approve"}, headers=auth)
    assert early.status_code == 409

    reviewed = client.post(f"/api/shipments/{sid}/hs/review", json={"action": "approve"}, headers=auth).json()
    assert reviewed["stage"] == "final_review"
    assert reviewed["hs_decision"]["status"] == "approved"

    approved = client.post(f"/api/shipments/{sid}/decision", json={"action": "approve"}, headers=auth).json()
    assert approved["stage"] == "ready"

    summary = client.get(f"/api/shipments/{sid}/summary", headers=auth).json()
    assert summary["hs"]["code"] == "8507.60"
    assert "not been submitted" in summary["disclaimer"]


def test_high_risk_requires_justification(client, auth):
    shipments = client.get("/api/shipments", headers=auth).json()
    risky = next(s for s in shipments if s["reference"] == "SP-2026-0006")
    assert risky["risk_level"] == "high"
    no_note = client.post(f"/api/shipments/{risky['id']}/decision", json={"action": "approve"}, headers=auth)
    assert no_note.status_code == 422


def test_hs_edit_validates_format(client, auth):
    shipments = client.get("/api/shipments", headers=auth).json()
    target = next(s for s in shipments if s["stage"] == "hs_review")
    bad = client.post(f"/api/shipments/{target['id']}/hs/review", json={"action": "edit", "hs_code": "abc"}, headers=auth)
    assert bad.status_code == 422


def test_demo_synthesis_is_labelled(client, auth):
    shipments = client.get("/api/shipments", headers=auth).json()
    sid = next(s for s in shipments if s["reference"] == "SP-2026-0004")["id"]
    detail = client.get(f"/api/shipments/{sid}", headers=auth).json()
    sources = {f["source"] for d in detail["documents"] for f in d["fields"]}
    assert sources == {"demo-synthesized"}


def test_duplicate_shipment_id_rejected(client, auth):
    r = client.post("/api/shipments", json={**NEW, "reference": "SP-2026-0001"}, headers=auth)
    assert r.status_code == 409
