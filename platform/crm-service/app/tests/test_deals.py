from __future__ import annotations


def _prepare_pipeline(client, headers):
    pipeline_id = client.post("/api/v1/crm/pipelines", headers=headers, json={"name": "Sales"}).json()["id"]
    stage1 = client.post(
        f"/api/v1/crm/pipelines/{pipeline_id}/stages",
        headers=headers,
        json={"name": "Lead", "position": 1},
    ).json()["id"]
    stage2 = client.post(
        f"/api/v1/crm/pipelines/{pipeline_id}/stages",
        headers=headers,
        json={"name": "Won", "position": 2, "is_won": True},
    ).json()["id"]
    return pipeline_id, stage1, stage2


def test_deal_create_move_stage_mark_won(client, tenant_headers):
    pipeline_id, stage1, stage2 = _prepare_pipeline(client, tenant_headers)
    deal = client.post(
        "/api/v1/crm/deals",
        headers=tenant_headers,
        json={"pipeline_id": pipeline_id, "stage_id": stage1, "title": "Deal 1", "amount": 1000},
    )
    assert deal.status_code == 200
    deal_id = deal.json()["id"]

    moved = client.post(f"/api/v1/crm/deals/{deal_id}/move-stage", headers=tenant_headers, json={"stage_id": stage2})
    assert moved.status_code == 200
    assert moved.json()["stage_id"] == stage2

    won = client.post(f"/api/v1/crm/deals/{deal_id}/mark-won", headers=tenant_headers, json={"close_reason": "signed"})
    assert won.status_code == 200
    assert won.json()["status"] == "won"
