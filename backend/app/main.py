from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .create_admin import bootstrap_admin
from .db import engine
from .migrate import migrate
from .routers import admin, auth, meta, student

STATIC = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.check()
    migrate(engine)
    bootstrap_admin()
    yield


app = FastAPI(title="CommuteCircle API", version="2.0.0", lifespan=lifespan,
              docs_url=None if settings.production else "/docs", redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if settings.production:
        resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return resp


for r in (auth.router, meta.router, student.router, admin.router):
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
