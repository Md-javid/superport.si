"""Milestone 5: accounts, organisations, isolation, invitations, checklist, comments, notifications."""
import asyncio
import json

import httpx
import pytest

from app.core import ratelimit
from app.core.config import get_settings
from app.db import SessionLocal
from app.email import service as mail
from app.models import EmailOutbox
from tests.test_v2 import NEW

PW = "Passw0rd1"


@pytest.fixture(autouse=True)
def _limits():
    ratelimit.reset()
    yield
    ratelimit.reset()


def register(client, email, org_name="Acme Trading", org_type="broker", invite=None, name="Test Person"):
    return client.post("/api/auth/register", json={"org_name": org_name, "org_type": org_type, "name": name, "email": email, "password": PW, "invite_token": invite})


def bearer(res):
    return {"Authorization": f"Bearer {res.json()['token']}"}


def new_shipment(client, auth, ref):
    r = client.post("/api/shipments", json={**NEW, "reference": ref}, headers=auth)
    assert r.status_code == 201
    return r.json()["id"]


def token_from(link):
    return link.split("token=")[1] if "token=" in link else link.rsplit("/", 1)[1]


def test_register_verify_and_session_rules(client):
    assert register(client, "w1@example.com").status_code == 201
    weak = client.post("/api/auth/register", json={"org_name": "Weak Co", "name": "Weak", "email": "w2@example.com", "password": "short"})
    assert weak.status_code == 422
    assert register(client, "w1@example.com").status_code == 409

    r = register(client, "w3@example.com", org_name="Verify Co")
    assert r.json()["user"]["email_verified"] is False and r.json()["user"]["org_name"] == "Verify Co"
    token = token_from(r.json()["dev_link"])
    assert client.get("/api/shipments", headers={"Authorization": f"Bearer {token}"}).status_code == 401  # an email token is never a session
    assert client.post("/api/auth/verify-email", json={"token": token}).json()["email_verified"] is True
    assert client.post("/api/auth/verify-email", json={"token": "garbage"}).status_code == 400
    assert client.get("/api/auth/me", headers=bearer(r)).json()["email_verified"] is True


def test_password_reset_is_single_use_and_does_not_leak(client):
    register(client, "reset@example.com", org_name="Reset Co")
    unknown = client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"}).json()
    known = client.post("/api/auth/forgot-password", json={"email": "reset@example.com"}).json()
    assert unknown["message"] == known["message"] and unknown["dev_link"] is None and known["dev_link"]
    token = token_from(known["dev_link"])
    assert client.post("/api/auth/reset-password", json={"token": token, "password": "NewPassw0rd"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "reset@example.com", "password": "NewPassw0rd"}).status_code == 200
    assert client.post("/api/auth/reset-password", json={"token": token, "password": "Another1234"}).status_code == 400


def test_login_is_rate_limited(client):
    codes = [client.post("/api/auth/login", json={"email": "x@example.com", "password": "nope"}).status_code for _ in range(11)]
    assert codes[:10] == [401] * 10 and codes[10] == 429


def test_organisations_cannot_see_each_others_data(client, auth):
    sid = new_shipment(client, auth, "SP-M5-ISO")
    other = register(client, "iso@example.com", org_name="Other Brokers")
    h = bearer(other)
    assert client.get("/api/shipments", headers=h).json() == []
    for path in (f"/api/shipments/{sid}", f"/api/shipments/{sid}/workspace", f"/api/shipments/{sid}/evidence"):
        assert client.get(path, headers=h).status_code == 404
    assert client.post(f"/api/shipments/{sid}/comments", json={"body": "hi"}, headers=h).status_code == 404
    assert client.get("/api/dashboard", headers=h).json()["kpis"]["active_shipments"] == 0
    assert client.get("/api/radar/signals", headers=h).json() == []


def test_invite_partner_and_collaborate(client, auth):
    sid = new_shipment(client, auth, "SP-M5-COLLAB")
    bad_role = client.post(f"/api/shipments/{sid}/invitations", json={"email": "fw@example.com", "party_role": "wizard"}, headers=auth)
    assert bad_role.status_code == 422
    inv = client.post(f"/api/shipments/{sid}/invitations", json={"email": "fw@example.com", "party_role": "forwarder"}, headers=auth)
    assert inv.status_code == 201
    token = token_from(inv.json()["dev_link"])
    info = client.get(f"/api/invitations/{token}").json()
    assert info["shipment_reference"] == "SP-M5-COLLAB" and info["party_role"] == "forwarder"
    assert register(client, "someone-else@example.com", invite=token).status_code == 403  # wrong email

    joined = register(client, "fw@example.com", org_name="Fast Freight", org_type="importer", invite=token)  # org_type is ignored: the invite decides
    assert joined.status_code == 201 and joined.json()["joined_shipment_id"] == sid and joined.json()["user"]["org_type"] == "forwarder"
    assert client.get(f"/api/invitations/{token}").status_code == 410  # single use
    fw = bearer(joined)

    mine = client.get("/api/shipments", headers=fw).json()
    assert len(mine) == 1 and mine[0]["access"] == "partner" and mine[0]["party_role"] == "forwarder"
    assert mine[0]["risk_level"] is None and mine[0]["hs_code"] is None and mine[0]["shared_by"]
    assert client.get(f"/api/shipments/{sid}", headers=fw).status_code == 403  # no AI findings for partners
    ws = client.get(f"/api/shipments/{sid}/workspace", headers=fw).json()
    assert ws["access"] == "partner" and ws["can_manage"] is False and len(ws["participants"]) == 2
    assert "risk" not in json.dumps(ws).lower()

    # forwarder provides the bill of lading, but not the exporter's invoice
    items = {i["key"]: i for i in ws["checklist"]}
    pdf = {"file": ("bol.pdf", b"%PDF-1.4 test", "application/pdf")}
    assert client.post(f"/api/shipments/{sid}/checklist/{items['commercial_invoice']['id']}/upload", files=pdf, headers=fw).status_code == 403
    assert client.post(f"/api/shipments/{sid}/checklist/{items['bill_of_lading']['id']}/upload", files=pdf, headers=fw).status_code == 200
    detail = client.get(f"/api/shipments/{sid}", headers=auth).json()
    assert any(d["doc_type"] == "bill_of_lading" for d in detail["documents"])  # it feeds the AI pipeline
    after = {i["key"]: i for i in client.get(f"/api/shipments/{sid}/workspace", headers=auth).json()["checklist"]}
    assert after["bill_of_lading"]["status"] == "uploaded" and after["bill_of_lading"]["uploaded_by"] == "Test Person"
    assert client.get(f"/api/shipments/{sid}/checklist/{after['bill_of_lading']['id']}/file", headers=fw).status_code == 200

    # discussion and notifications
    assert client.post(f"/api/shipments/{sid}/comments", json={"body": "Container arrives Friday."}, headers=fw).status_code == 201
    broker_notes = client.get("/api/notifications", headers=auth).json()
    assert broker_notes["unread"] >= 1 and any(n["kind"] == "comment" for n in broker_notes["items"])
    client.post(f"/api/shipments/{sid}/comments", json={"body": "@Test please confirm the cut-off time"}, headers=auth)
    assert any(n["kind"] == "mention" for n in client.get("/api/notifications", headers=fw).json()["items"])
    client.post("/api/notifications/read", json={}, headers=fw)
    assert client.get("/api/notifications", headers=fw).json()["unread"] == 0

    # reminders
    exporter_item = after["certificate_of_origin"]["id"]
    assert client.post(f"/api/shipments/{sid}/checklist/{exporter_item}/remind", headers=auth).status_code == 409  # no exporter yet
    client.post(f"/api/shipments/{sid}/checklist", json={"label": "Delivery order", "party_role": "forwarder"}, headers=auth)
    new_item = next(i for i in client.get(f"/api/shipments/{sid}/workspace", headers=auth).json()["checklist"] if i["label"] == "Delivery order")
    assert client.post(f"/api/shipments/{sid}/checklist/{new_item['id']}/remind", headers=auth).json()["notified"] == 1
    assert client.post(f"/api/shipments/{sid}/checklist/{new_item['id']}/remind", headers=auth).status_code == 409  # not more than hourly
    assert client.post(f"/api/shipments/{sid}/checklist/{new_item['id']}/remind", headers=fw).status_code == 403  # partners cannot nag

    # documents lock once classification starts
    client.post(f"/api/shipments/{sid}/documents/samples", headers=auth)
    client.post(f"/api/shipments/{sid}/process", headers=auth)
    client.post(f"/api/shipments/{sid}/extraction/confirm", headers=auth)
    locked = client.post(f"/api/shipments/{sid}/checklist/{items['bill_of_lading']['id']}/upload", files=pdf, headers=fw)
    assert locked.status_code == 409

    # partners cannot invite and the owner can remove them
    assert client.post(f"/api/shipments/{sid}/invitations", json={"email": "z@example.com", "party_role": "exporter"}, headers=fw).status_code == 403
    org_id = next(p["org_id"] for p in client.get(f"/api/shipments/{sid}/workspace", headers=auth).json()["participants"] if not p["owner"])
    assert client.delete(f"/api/shipments/{sid}/participants/{org_id}", headers=auth).status_code == 200
    assert client.get(f"/api/shipments/{sid}/workspace", headers=fw).status_code == 404


def test_existing_account_accepts_an_invitation(client, auth):
    sid = new_shipment(client, auth, "SP-M5-EXISTING")
    importer = register(client, "imp@example.com", org_name="Imports Ltd", org_type="importer")
    token = token_from(client.post(f"/api/shipments/{sid}/invitations", json={"email": "imp@example.com", "party_role": "importer"}, headers=auth).json()["dev_link"])
    stranger = register(client, "stranger@example.com", org_name="Stranger Co")
    assert client.post(f"/api/invitations/{token}/accept", headers=bearer(stranger)).status_code == 403
    assert client.post(f"/api/invitations/{token}/accept", headers=bearer(importer)).json()["shipment_id"] == sid
    assert client.get(f"/api/shipments/{sid}/workspace", headers=bearer(importer)).json()["party_role"] == "importer"


def test_team_invitations_join_the_same_organisation(client, auth):
    invite = client.post("/api/team/invitations", json={"email": "colleague@example.com"}, headers=auth)
    assert invite.status_code == 201
    joined = register(client, "colleague@example.com", name="Colleague One", invite=token_from(invite.json()["dev_link"]))
    assert joined.json()["user"]["org_role"] == "member" and joined.json()["user"]["org_name"] == "Harbor & Co. Customs Advisory"
    assert len(client.get("/api/shipments", headers=bearer(joined)).json()) >= 7  # sees the team's shipments
    assert client.post("/api/team/invitations", json={"email": "more@example.com"}, headers=bearer(joined)).status_code == 403
    assert any(m["email"] == "colleague@example.com" for m in client.get("/api/team", headers=auth).json()["members"])


def test_demo_personas_show_the_ecosystem(client, auth):
    fw = client.post("/api/auth/demo?persona=forwarder").json()
    h = {"Authorization": f"Bearer {fw['token']}"}
    shared = client.get("/api/shipments", headers=h).json()
    battery = next(s for s in shared if s["reference"] == "SP-2026-0001")
    assert battery["access"] == "partner"
    ws = client.get(f"/api/shipments/{battery['id']}/workspace", headers=h).json()
    assert len(ws["comments"]) == 3 and {p["party_role"] for p in ws["participants"]} == {"broker", "forwarder", "importer"}
    coo = next(i for i in ws["checklist"] if i["key"] == "certificate_of_origin")
    assert coo["status"] == "missing" and coo["party_role"] == "exporter"
    assert client.get("/api/dashboard", headers=h).json()["shared"]
    assert client.post("/api/auth/demo?persona=importer").status_code == 200


def test_resend_provider_request_shape(client, monkeypatch):
    seen = {}

    def handler(request):
        seen["auth"], seen["body"] = request.headers["authorization"], json.loads(request.content)
        return httpx.Response(200, json={"id": "abc"})

    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("EMAIL_FROM", "SuperPort <no-reply@example.com>")
    get_settings.cache_clear()
    mail.set_transport(httpx.MockTransport(handler))
    try:
        with SessionLocal() as db:
            out = mail.send(db, "a@example.com", "Hello", "Body", "https://x/y")
            db.commit()
            assert db.query(EmailOutbox).filter_by(to_email="a@example.com", provider="resend", status="sent").count() == 1
    finally:
        mail.set_transport(None)
        monkeypatch.undo()
        get_settings.cache_clear()
    assert out["sent"] and out["dev_link"] is None and seen["auth"] == "Bearer re_test" and seen["body"]["to"] == ["a@example.com"]


def test_production_refuses_unsafe_defaults(client, monkeypatch):
    from app.main import app, lifespan

    monkeypatch.setenv("ENVIRONMENT", "production")
    get_settings.cache_clear()

    async def boot():
        async with lifespan(app):
            pass

    try:
        with pytest.raises(RuntimeError):
            asyncio.run(boot())
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
