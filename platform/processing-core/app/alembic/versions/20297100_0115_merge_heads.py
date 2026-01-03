"""Merge alembic heads.

Revision ID: 20297100_0115_merge_heads
Revises: 20250320_0106_audit_signing_keys_object_lock, 20260201_0104_fleet_ingestion_v1, 20292010_0108_marketplace_order_sla_v1, 20292020_0109_marketplace_promotions_v1, 20292020_0109_marketplace_recommendations_v1, 20293010_0110_marketplace_sponsored_v1, 20297000_0114_bank_erp_stub_v1, 20297000_0114_marketplace_moderation_v1, 20297000_0114_webhook_hmac_sms_voice_stub_v1
Create Date: 2029-07-10 00:00:00
"""

revision = "20297100_0115_merge_heads"
down_revision = (
    "20250320_0106_audit_signing_keys_object_lock",
    "20260201_0104_fleet_ingestion_v1",
    "20292010_0108_marketplace_order_sla_v1",
    "20292020_0109_marketplace_promotions_v1",
    "20292020_0109_marketplace_recommendations_v1",
    "20293010_0110_marketplace_sponsored_v1",
    "20297000_0114_bank_erp_stub_v1",
    "20297000_0114_marketplace_moderation_v1",
    "20297000_0114_webhook_hmac_sms_voice_stub_v1",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
