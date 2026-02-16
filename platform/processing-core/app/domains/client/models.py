"""Client domain models placeholders.

PR-0 keeps SQLAlchemy models in their existing modules and provides
an explicit aggregation point for future client domain migrations.
"""

from app.models.client import Client

__all__ = ["Client"]
