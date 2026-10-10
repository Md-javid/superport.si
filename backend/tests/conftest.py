import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["UPLOAD_DIR"] = "/tmp/superport-test-uploads"
os.environ["SEED_DEMO_DATA"] = "true"
os.environ["INTELLIGENCE_MODE"] = "off"

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth(client):
    token = client.post("/api/auth/demo").json()["token"]
    return {"Authorization": f"Bearer {token}"}
