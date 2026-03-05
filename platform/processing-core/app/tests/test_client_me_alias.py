from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.client_me import router


def test_client_me_redirects_to_portal_me():
    app = FastAPI()
    app.include_router(router, prefix="/api/core")
    client = TestClient(app)

    response = client.get("/api/core/client/me", follow_redirects=False)
    assert response.status_code == 308
    assert response.headers["location"].endswith("/api/core/portal/me")
