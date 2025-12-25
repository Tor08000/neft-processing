from app.main import create_app
from fastapi.testclient import TestClient


def test_risk_score_returns_explainability():
    client = TestClient(create_app())
    payload = {
        "amount": 12000,
        "client_score": 0.6,
        "document_type": "invoice",
        "client_status": "active",
        "history": {"operations_count_30d": 5, "chargebacks": 0, "avg_amount_30d": 9000},
    }
    response = client.post("/api/v1/risk-score", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert 0 <= data["risk_score"] <= 100
    assert data["risk_category"] in {"LOW", "MEDIUM", "HIGH"}
    assert data["decision"] in {"ALLOW", "MANUAL_REVIEW", "DECLINE"}
    assert data["explain"]["features"]


def test_train_and_update_model():
    client = TestClient(create_app())
    payload = {"model_type": "risk_score", "metrics": {"accuracy": 0.72}}
    train_response = client.post("/admin/ai/train-model", json=payload)
    assert train_response.status_code == 200
    train_data = train_response.json()
    assert train_data["status"] == "trained"

    update_response = client.post("/admin/ai/update-model", json=payload)
    assert update_response.status_code == 200
    update_data = update_response.json()
    assert update_data["status"] == "updated"
