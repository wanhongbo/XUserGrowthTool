from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_api_requires_auth():
    response = client.get("/api/overview")
    assert response.status_code == 401


def test_allowed_email_can_login_and_access_api():
    login = client.post("/api/auth/login", json={"email": "wanhongbo137@gmail.com"})
    assert login.status_code == 200
    token = login.json()["token"]

    response = client.get("/api/overview", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


def test_other_email_is_rejected():
    response = client.post("/api/auth/login", json={"email": "someone@example.com"})
    assert response.status_code == 403

