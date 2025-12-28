from app.services.explain.recommendations.common import build_recommendations as build_common_recommendations
from app.services.explain.recommendations.fuel import build_recommendations as build_fuel_recommendations
from app.services.explain.recommendations.logistics import build_recommendations as build_logistics_recommendations

__all__ = ["build_common_recommendations", "build_fuel_recommendations", "build_logistics_recommendations"]
