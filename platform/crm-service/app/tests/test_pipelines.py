from __future__ import annotations


def test_pipeline_create_and_stage_create(client, tenant_headers):
    create_pipeline = client.post("/api/v1/crm/pipelines", headers=tenant_headers, json={"name": "Sales"})
    assert create_pipeline.status_code == 200
    pipeline_id = create_pipeline.json()["id"]

    create_stage = client.post(
        f"/api/v1/crm/pipelines/{pipeline_id}/stages",
        headers=tenant_headers,
        json={"name": "Lead", "position": 1},
    )
    assert create_stage.status_code == 200
    assert create_stage.json()["pipeline_id"] == pipeline_id
