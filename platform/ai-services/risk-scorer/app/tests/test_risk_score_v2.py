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
    replay = client.post("/api/v1/risk-score", json=payload)
    assert replay.status_code == 200
    replay_data = replay.json()
    assert 0 <= data["risk_score"] <= 100
    assert data["risk_category"] in {"LOW", "MEDIUM", "HIGH"}
    assert data["decision"] in {"ALLOW", "MANUAL_REVIEW", "DECLINE"}
    assert data["explain"]["features"]
    assert data["model_source"] == "heuristic_rules"
    assert data["degraded"] is False
    assert data["explain"]["source"] == "heuristic_rules"
    assert data["explain"]["score_breakdown"]
    assert data["explain"]["trace"]["formula_version"] == "heuristic_ruleset_v1"
    assert data["explain"]["trace"]["model_source"] == "heuristic_rules"
    assert len(data["explain"]["trace_hash"]) == 64
    assert data["explain"]["trace_hash"] == replay_data["explain"]["trace_hash"]
    assert "heuristic_ruleset_v1" in data["assumptions"]


def test_risk_score_accepts_shadow_payment_subject():
    client = TestClient(create_app())
    payload = {
        "amount": 12000,
        "document_type": "payment",
        "client_status": "active",
        "history": {"operations_count_30d": 5, "chargebacks": 0, "avg_amount_30d": 9000},
        "metadata": {
            "subject_type": "PAYMENT",
            "subject_id": "payment-op-1",
            "model_selector": "risk_v5_payment",
        },
    }

    response = client.post("/api/v1/risk-score", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["model_source"] == "heuristic_rules"
    assert data["explain"]["trace"]["feature_values"]["document_type"] == "payment"
    assert "model_selector" in data["explain"]["trace"]["metadata_keys"]
    assert len(data["explain"]["trace_hash"]) == 64


def test_train_and_update_model():
    client = TestClient(create_app())
    payload = {"model_type": "risk_score", "metrics": {"accuracy": 0.72}}
    train_response = client.post("/admin/ai/train-model", json=payload)
    assert train_response.status_code == 200
    train_data = train_response.json()
    assert train_data["status"] == "trained"
    assert train_data["simulated"] is True
    assert train_data["provider_mode"] == "registry_only"

    update_response = client.post("/admin/ai/update-model", json=payload)
    assert update_response.status_code == 200
    update_data = update_response.json()
    assert update_data["status"] == "updated"
    assert update_data["metrics"] == {"accuracy": 0.72}
