"""API smoke tests (no Ollama)."""

from fastapi.testclient import TestClient

from main import app


def test_health():
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}


def test_create_and_get_message():
    with TestClient(app) as client:
        created = client.post(
            "/messages",
            json={"email": {"subject": "Test subject", "body": "Test body"}},
        )
        assert created.status_code == 201
        message_id = created.json()["id"]

        detail = client.get(f"/messages/{message_id}")
        assert detail.status_code == 200
        assert detail.json()["email"]["subject"] == "Test subject"


def test_get_guide():
    with TestClient(app) as client:
        r = client.get("/guide")
        assert r.status_code == 200
        assert "label_schema" in r.json()["config"]
