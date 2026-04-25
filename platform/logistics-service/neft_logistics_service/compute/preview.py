from __future__ import annotations

from neft_logistics_service.providers.base import BaseProvider
from neft_logistics_service.schemas import RoutePreviewRequest, RoutePreviewResponse


def preview_route(request: RoutePreviewRequest, provider: BaseProvider) -> RoutePreviewResponse:
    return provider.preview_route(request)
