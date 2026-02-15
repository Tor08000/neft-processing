"""merge heads station_margin_day and commercial_recommendation_actions

Revision ID: 20299730_0182_merge_heads_station_margin_day_and_commercial_recommendation_actions
Revises: 20299680_0177_station_margin_day, 20299720_0181_commercial_recommendation_actions
Create Date: 2026-02-16 13:00:00.000000
"""

revision = "20299730_0182_merge_heads_station_margin_day_and_commercial_recommendation_actions"
down_revision = (
    "20299680_0177_station_margin_day",
    "20299720_0181_commercial_recommendation_actions",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration."""
    pass


def downgrade() -> None:
    """Rollback migration."""
    pass
