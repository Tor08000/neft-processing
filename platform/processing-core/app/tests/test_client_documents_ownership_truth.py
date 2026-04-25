from fastapi.routing import APIRoute

from app.routers.client_documents import router as legacy_router
from app.routers.client_documents_v1 import router as canonical_router


def _route_paths(router) -> set[str]:
    return {route.path for route in router.routes if isinstance(route, APIRoute)}


def test_canonical_router_owns_general_client_docflow_surface_and_additive_ack() -> None:
    assert canonical_router.prefix == "/api/core/client/documents"
    paths = _route_paths(canonical_router)

    assert "/api/core/client/documents" in paths
    assert "/api/core/client/documents/{document_id}" in paths
    assert "/api/core/client/documents/{document_id}/upload" in paths
    assert "/api/core/client/documents/{document_id}/submit" in paths
    assert "/api/core/client/documents/{document_id}/sign" in paths
    assert "/api/core/client/documents/{document_id}/signatures" in paths
    assert "/api/core/client/documents/{document_id}/timeline" in paths
    assert "/api/core/client/documents/{document_id}/files" in paths
    assert "/api/core/client/documents/files/{file_id}/download" in paths
    assert "/api/core/client/documents/{document_id}/send" in paths
    assert "/api/core/client/documents/{document_id}/edo" in paths
    assert "/api/core/client/documents/{document_id}/ack" in paths



def test_legacy_router_keeps_closing_docs_and_ack_compatibility_surface() -> None:
    assert legacy_router.prefix == "/api/v1/client"
    paths = _route_paths(legacy_router)

    assert "/api/v1/client/documents" in paths
    assert "/api/v1/client/documents/{document_id}" in paths
    assert "/api/v1/client/documents/{document_id}/download" in paths
    assert "/api/v1/client/documents/{document_id}/ack" in paths
    assert "/api/v1/client/closing-packages/{package_id}/ack" in paths



def test_documents_routers_keep_narrow_split_outside_additive_ack() -> None:
    canonical_paths = _route_paths(canonical_router)
    legacy_paths = _route_paths(legacy_router)

    assert "/api/core/client/documents/{document_id}/ack" in canonical_paths
    assert "/api/core/client/closing-packages/{package_id}/ack" not in canonical_paths

    assert "/api/v1/client/documents/{document_id}/upload" not in legacy_paths
    assert "/api/v1/client/documents/{document_id}/submit" not in legacy_paths
    assert "/api/v1/client/documents/{document_id}/sign" not in legacy_paths
    assert "/api/v1/client/documents/{document_id}/signatures" not in legacy_paths
    assert "/api/v1/client/documents/{document_id}/timeline" not in legacy_paths
    assert "/api/v1/client/documents/{document_id}/files" not in legacy_paths
    assert "/api/v1/client/documents/files/{file_id}/download" not in legacy_paths
    assert "/api/v1/client/documents/{document_id}/send" not in legacy_paths
    assert "/api/v1/client/documents/{document_id}/edo" not in legacy_paths
