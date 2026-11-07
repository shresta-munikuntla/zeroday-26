"""FastAPI application entry point."""
from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes_auth import router as auth_router
from backend.api.routes_incidents import router as incidents_router
from backend.api.routes_notifications import router as notifications_router
from backend.agents.employee_notification import match_and_draft
from backend.security.auth import initialize_users
from backend.storage import demo_report, initialize


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize()
    initialize_users()
    match_and_draft(demo_report())
    yield


app = FastAPI(title="SentinelAI API", version="0.1.0", lifespan=lifespan,
              docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True,
                   allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])
app.include_router(auth_router)
app.include_router(incidents_router)
app.include_router(notifications_router)


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok"}
