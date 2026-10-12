import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, copilot, dashboard, intelligence, market, misc, orgs, radar, shipments, tracking, workspace
from app.core.config import get_settings
from app.db import SessionLocal, engine, ensure_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.environment == "production" and (settings.secret_key.startswith("dev-only") or settings.demo_mode or settings.seed_demo_data):
        raise RuntimeError("Refusing to start in production with the default SECRET_KEY, DEMO_MODE=true or SEED_DEMO_DATA=true.")
    ensure_schema()
    from app.rag.store import init_vector_store

    init_vector_store(engine)
    from app.services.orgs import backfill

    with SessionLocal() as db:
        backfill(db)
    if settings.seed_demo_data:
        from app.seed import seed, seed_library, seed_personas, seed_timelines

        with SessionLocal() as db:
            seed(db)
        with SessionLocal() as db:
            seed_personas(db)
        with SessionLocal() as db:
            seed_timelines(db)
        with SessionLocal() as db:
            seed_library(db)
    task = asyncio.create_task(radar.scheduler()) if settings.radar_interval_minutes > 0 else None
    yield
    if task:
        task.cancel()


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
for router in (auth.router, shipments.router, workspace.router, tracking.router, copilot.router, orgs.router, market.router, radar.router, radar.shipment_router, dashboard.router, intelligence.router, misc.router):
    app.include_router(router, prefix="/api")
