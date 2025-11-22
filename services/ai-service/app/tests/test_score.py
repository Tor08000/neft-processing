from fastapi.testclient import TestClient
from app.main import create_app

client = TestClient(create_app())

def test_score_basic():
    r = client.post("/api/v1/score", json={"tenant_id":1,"card_token":"x","qty":50,"amount":1000})
    assert r.status_code == 200
    d = r.json()
    assert "score" in d

def test_score_tx_basic():
    r = client.post("/api/v1/score/tx", json={"tenant_id":1,"card_token":"x","qty":20,"amount":100})
    assert r.status_code == 200
    d = r.json()
    assert "score" in d