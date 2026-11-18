from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/v1/recommendations/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["result"]["service"] == "boardgame-recommendation"
    assert payload["result"]["status"] == "UP"

