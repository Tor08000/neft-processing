from __future__ import annotations


def test_task_create_complete(client, tenant_headers):
    created = client.post("/api/v1/crm/tasks", headers=tenant_headers, json={"title": "Call client"})
    assert created.status_code == 200
    task_id = created.json()["id"]

    completed = client.post(f"/api/v1/crm/tasks/{task_id}/complete", headers=tenant_headers)
    assert completed.status_code == 200
    assert completed.json()["status"] == "done"
