import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.services.cleanup import cleanup_loop
from app.services.job_store import JobStore

logging.basicConfig(level=logging.INFO)

settings = get_settings()
app = FastAPI(title="PowerPoint Translator API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")


@app.on_event("startup")
async def start_cleanup_task() -> None:
    store = JobStore(settings)
    asyncio.create_task(cleanup_loop(settings, store))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

