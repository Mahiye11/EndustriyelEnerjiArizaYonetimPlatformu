import os
from datetime import datetime, timezone
from uuid import uuid4

os.environ["DATABASE_PATH"] = "/tmp/factorypulse-test.db"

from fastapi.testclient import TestClient
from app.main import app, DB_PATH


def login(client):
    response = client.post("/api/v1/auth/login", json={"email": "admin@factorypulse.local", "password": "factorypulse"})
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def test_ingest_is_idempotent_and_opens_one_alarm():
    DB_PATH.unlink(missing_ok=True)
    with TestClient(app) as client:
        headers = {"X-Device-Key": "demo-device-key"}
        payload = {"measurementId": str(uuid4()), "deviceId": "machine-42", "recordedAt": datetime.now(timezone.utc).isoformat(), "powerKw": 25, "temperatureC": 80, "running": True}
        first = client.post("/api/v1/measurements", json=payload, headers=headers)
        second = client.post("/api/v1/measurements", json=payload, headers=headers)
        assert first.status_code == 202 and first.json()["alarmsCreated"] == 2
        assert second.status_code == 202 and second.json()["duplicate"] is True
        assert len(client.get("/api/v1/alarms", headers=login(client)).json()) == 2

