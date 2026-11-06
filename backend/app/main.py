from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import Base, engine
from .routers import admin, auth, circles, meta, profile

STATIC = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="CommuteCircle API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
for r in (auth.router, meta.router, profile.router, circles.router, admin.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serve the built React app from the same origin in production.
if STATIC.exists():
    app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = STATIC / path
        return FileResponse(f if path and f.is_file() else STATIC / "index.html")
