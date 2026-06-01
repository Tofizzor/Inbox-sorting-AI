"""FastAPI application entry point.

Run (from the backend/ folder):
    uvicorn main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.database import init_db
from routers.classify import router as classify_router
from routers.guide import router as guide_router
from routers.messages import router as messages_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    init_db()
    app = FastAPI(
        title="AI Inbox Triage",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(classify_router)
    app.include_router(messages_router)
    app.include_router(guide_router)
    return app


app = create_app()


@app.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok"}
