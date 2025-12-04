import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.processing import router as processing_router
from app.bootstrap import seed_demo_client_account

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="NEFT Auth Host")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(processing_router)


@app.get("/health")
def health_root():
    return {"status": "ok", "service": "auth-host"}


@app.on_event("startup")
async def bootstrap_demo_user() -> None:
    logger.info("auth-host: bootstrap demo user start")
    await seed_demo_client_account()
    logger.info("auth-host: bootstrap demo user done")
