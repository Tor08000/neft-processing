from __future__ import annotations

from fastapi import APIRouter

from ...model_registry import model_registry
from ...schemas import ModelType, TrainingRequest, TrainingResponse

router = APIRouter(prefix="/admin/ai", tags=["admin-ai"])


@router.post("/train-model", response_model=TrainingResponse)
async def train_model(request: TrainingRequest) -> TrainingResponse:
    info = model_registry.train(ModelType(request.model_type), metrics=request.metrics)
    return TrainingResponse(
        model_type=info.model_type,
        model_version=info.version,
        status="trained",
        trained_at=info.trained_at,
        metrics=info.metrics,
        simulated=info.simulated,
        provider_mode=info.provider_mode,
    )


@router.post("/update-model", response_model=TrainingResponse)
async def update_model(request: TrainingRequest) -> TrainingResponse:
    info = model_registry.update(ModelType(request.model_type), metrics=request.metrics)
    return TrainingResponse(
        model_type=info.model_type,
        model_version=info.version,
        status="updated",
        trained_at=info.trained_at,
        metrics=info.metrics,
        simulated=info.simulated,
        provider_mode=info.provider_mode,
    )


@router.post("/activate-model", response_model=TrainingResponse)
async def activate_model(request: TrainingRequest) -> TrainingResponse:
    info = model_registry.update(ModelType(request.model_type), metrics=request.metrics)
    return TrainingResponse(
        model_type=info.model_type,
        model_version=info.version,
        status="updated",
        trained_at=info.trained_at,
        metrics=info.metrics,
        simulated=info.simulated,
        provider_mode=info.provider_mode,
    )


@router.post("/models/train", response_model=TrainingResponse)
async def train_model_v3(request: TrainingRequest) -> TrainingResponse:
    info = model_registry.train(ModelType(request.model_type), metrics=request.metrics)
    return TrainingResponse(
        model_type=info.model_type,
        model_version=info.version,
        status="trained",
        trained_at=info.trained_at,
        metrics=info.metrics,
        simulated=info.simulated,
        provider_mode=info.provider_mode,
    )


@router.post("/models/activate", response_model=TrainingResponse)
async def activate_model_v3(request: TrainingRequest) -> TrainingResponse:
    info = model_registry.update(ModelType(request.model_type), metrics=request.metrics)
    return TrainingResponse(
        model_type=info.model_type,
        model_version=info.version,
        status="updated",
        trained_at=info.trained_at,
        metrics=info.metrics,
        simulated=info.simulated,
        provider_mode=info.provider_mode,
    )
