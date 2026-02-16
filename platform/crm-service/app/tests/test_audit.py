from __future__ import annotations


def test_audit_row_created_for_comment(client, tenant_headers):
    comment = client.post(
        "/api/v1/crm/comments",
        headers=tenant_headers,
        json={"entity_type": "deal", "entity_id": "deal-42", "body": "added"},
    )
    assert comment.status_code == 200

    audit = client.get("/api/v1/crm/audit", headers=tenant_headers, params={"entity_type": "deal", "entity_id": "deal-42"})
    assert audit.status_code == 200
    assert audit.json()["total"] == 1
    assert audit.json()["items"][0]["action"] == "comment_add"
