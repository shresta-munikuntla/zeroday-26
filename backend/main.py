"""FastAPI application entry point."""
from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes_auth import router as auth_router
from backend.api.routes_ai import router as ai_router
from backend.api.routes_incidents import router as incidents_router
from backend.api.routes_notifications import router as notifications_router
from backend.agents.employee_notification import match_and_draft
from backend.agents.incident_workflow import dashboard_report, run_detection_and_investigation
from backend.database.db import db_path
from backend.database.seed import seed
from backend.security.auth import initialize_users
from backend.storage import connect, initialize


def ensure_agent_database() -> None:
    path = db_path()
    if path == ":memory:":
        raise RuntimeError("Use a file-backed SQLite DATABASE_URL for the agent workflow")
    database_path = Path(path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    if not database_path.exists():
        seed(path)


def sync_agent_incidents() -> None:
    from backend.workflow.orchestrator import run_incident_workflow
    run_incident_workflow()


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize()
    ensure_agent_database()
    initialize_users()
    sync_agent_incidents()
    yield


app = FastAPI(title="SentinelAI API", version="0.1.0", lifespan=lifespan,
              docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True,
                   allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])
app.include_router(auth_router)
app.include_router(ai_router)
app.include_router(incidents_router)
app.include_router(notifications_router)


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok"}
