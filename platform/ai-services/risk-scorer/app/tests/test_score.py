from app.main import create_app
from fastapi.testclient import TestClient


def test_score_basic_flow():
    client = TestClient(create_app())
    payload = {"client_id": "1", "card_id": "card-1", "amount": 1000, "qty": 50}
    response = client.post("/api/v1/score", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "score" in data
    assert data["decision"] in {"allow", "review", "deny"}
    assert data["provider"] == "local_heuristic"
    assert data["score_source"] == "heuristic"
    assert data["degraded"] is False
    assert "heuristic_local_rules" in data["assumptions"]
    assert data["trace"]["formula_version"] == "heuristic_local_rules_v1"
    assert len(data["trace"]["trace_hash"]) == 64
