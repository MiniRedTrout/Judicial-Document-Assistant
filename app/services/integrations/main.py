from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.api.exports import router as exports_router

from app.api.documents import router as documents_router
from app.api.lawyer import router as lawyer_router
from app.openapi import configure_upload_schema
from app.services.document_store import init_db, mark_interrupted_documents


APP_NAME = "AI Judicial Assistant"
APP_VERSION = "0.1.0"
APP_DESCRIPTION = (
    "Backend для обработки судебных документов "
    "и документов ФССП"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    interrupted = mark_interrupted_documents()
    if interrupted:
        logging.getLogger(__name__).warning(
            "Обнаружено прерванных документов: %s", interrupted
        )
    yield


app = FastAPI(
    title=APP_NAME,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    lifespan=lifespan,
)


app.include_router(exports_router)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.include_router(documents_router)
app.include_router(lawyer_router)
configure_upload_schema(app)


@app.get("/", include_in_schema=False)
def root():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


@app.get("/info")
def info():
    return {
        "name": APP_NAME,
        "version": APP_VERSION,
        "description": APP_DESCRIPTION,
    }
