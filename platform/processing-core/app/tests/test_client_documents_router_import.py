from app.routers.client_documents_v1 import router


def test_client_documents_router_imports() -> None:
    assert router is not None
