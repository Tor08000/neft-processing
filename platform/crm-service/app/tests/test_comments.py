from __future__ import annotations


def test_comment_add(client, tenant_headers):
    created = client.post(
        "/api/v1/crm/comments",
        headers=tenant_headers,
        json={"entity_type": "deal", "entity_id": "deal-1", "body": "hello"},
    )
    assert created.status_code == 200

    listed = client.get("/api/v1/crm/comments", headers=tenant_headers, params={"entity_type": "deal", "entity_id": "deal-1"})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
