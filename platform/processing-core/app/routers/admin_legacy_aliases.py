from __future__ import annotations

from fastapi import APIRouter

# Repo-truth consumer diagnosis removed the last safe /api/core/admin/* redirect tails from this module.
# Remaining hidden admin compatibility tails are kept in dedicated modules only where live consumers still exist.
router = APIRouter(prefix="/admin", tags=["admin-legacy"])


__all__ = ["router"]
