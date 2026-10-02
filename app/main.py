"""Main FastAPI application for ContextIQ."""
import os
import pathlib
import time

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routes.analytics import router as analytics_router
from app.routes.incidents import router as incidents_router

load_dotenv()

app = FastAPI(
    title="ContextIQ Backend API",
    description="Multimodal AI Incident Prioritization & Decision-Support System",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directory paths
BASE_DIR = pathlib.Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_UPLOADS = BASE_DIR.parent / "data" / "uploads"
DATA_UPLOADS.mkdir(parents=True, exist_ok=True)

# Mount static file directories
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/data/uploads", StaticFiles(directory=str(DATA_UPLOADS)), name="uploads")

app.include_router(incidents_router)
app.include_router(analytics_router)

MODE = os.getenv("MODE", "local")
GEMINI_SURFACE = os.getenv("GEMINI_SURFACE", "generate_content")
EXTRACT_MODEL = os.getenv("EXTRACT_MODEL", "gemini-3-flash")
DECIDE_MODEL = os.getenv("DECIDE_MODEL", "gemini-3-flash")
EMBED_MODEL = os.getenv("EMBED_MODEL", "gemini-embedding-001")


@app.get("/")
def read_root():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/healthz")
def health_check():
    return {
        "status": "ok",
        "timestamp": time.time(),
        "mode": MODE,
        "gemini_surface": GEMINI_SURFACE,
        "models": {
            "extract": EXTRACT_MODEL,
            "decide": DECIDE_MODEL,
            "embed": EMBED_MODEL
        },
        "backends": {
            "storage": "gcp:gcs" if MODE == "gcp" else "local:fs",
            "bus": "gcp:pubsub" if MODE == "gcp" else "local:asyncio_queue",
            "warehouse": "gcp:bigquery" if MODE == "gcp" else "local:sqlite",
            "retriever": "gcp:vectorsearch" if MODE == "gcp" else "local:numpy_cosine",
            "llm": f"vertexai:{DECIDE_MODEL}" if MODE == "gcp" else f"genai:{DECIDE_MODEL}"
        }
    }
