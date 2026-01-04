from __future__ import annotations

from collections import Counter

from app.main import app


def test_openapi_operation_ids_unique() -> None:
    schema = app.openapi()
    operation_ids: list[str] = []
    for path_item in schema.get("paths", {}).values():
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            operation_id = operation.get("operationId")
            if operation_id:
                operation_ids.append(operation_id)

    duplicates = sorted([op_id for op_id, count in Counter(operation_ids).items() if count > 1])
    assert not duplicates, f"Duplicate operation IDs found: {', '.join(duplicates)}"
