from unittest.mock import patch, MagicMock


def test_google_login_missing_credential(client):
    res = client.post("/api/auth/google", json={"credential": "   "})
    assert res.status_code == 400


def test_google_login_invalid_token(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"error_description": "Invalid Value"}

    with patch("httpx.Client.get", return_value=mock_resp):
        res = client.post("/api/auth/google", json={"credential": "fake_bad_token"})
        assert res.status_code == 401
        assert "invalid or expired" in res.json()["detail"]


def test_google_login_success_new_user(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "email": "newgoogleuser@superport.ai",
        "email_verified": "true",
        "name": "Jane Google",
        "aud": "my-client-id.apps.googleusercontent.com",
    }

    with patch("httpx.Client.get", return_value=mock_resp):
        res = client.post("/api/auth/google", json={"credential": "valid_token_123"})
        assert res.status_code == 200
        data = res.json()
        assert "token" in data
        assert data["user"]["email"] == "newgoogleuser@superport.ai"
        assert data["user"]["name"] == "Jane Google"
        assert data["user"]["email_verified"] is True


def test_google_login_existing_user(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "email": "newgoogleuser@superport.ai",
        "email_verified": "true",
        "name": "Jane Google",
        "aud": "my-client-id.apps.googleusercontent.com",
    }

    with patch("httpx.Client.get", return_value=mock_resp):
        res = client.post("/api/auth/google", json={"credential": "valid_token_123"})
        assert res.status_code == 200
        data = res.json()
        assert data["user"]["email"] == "newgoogleuser@superport.ai"
