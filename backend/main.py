from contextlib import asynccontextmanager
from typing import List
from uuid import UUID

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import db
from ai.orchestrator import JudgedEntry, ProductCandidate, run as run_orchestrator
from auth import require_user
from profiles.routes import router as profiles_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    await db.init_pool()
    try:
        yield
    finally:
        await db.close_pool()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profiles_router)


class ResearchStats(BaseModel):
    searched: int = 0
    shortlisted: int = 0
    extracted: int = 0
    judged: int = 0


class ResearchResponse(BaseModel):
    session_id: UUID
    candidates: List[ProductCandidate]
    recommendation: str | None = None
    stats: ResearchStats


@app.post("/research", response_model=ResearchResponse)
async def research(
    prompt: str = Form(...),
    images: List[UploadFile] = File(default=[]),
    user_id: UUID = Depends(require_user),
):
    profile = await db.load_profile(user_id)
    if profile is None:
        raise HTTPException(status_code=409, detail="Complete onboarding quiz first")
    session_id = await db.create_session(user_id, prompt)
    try:
        state = await run_orchestrator(prompt, profile)
    except Exception:
        await db.fail_session(session_id)
        raise

    top: list[ProductCandidate] = state.get("candidates", []) or []
    judged: list[JudgedEntry] = state.get("judged", []) or []
    angles = state.get("angle_queries", []) or []
    recommendation = state.get("recommendation")

    await db.add_angles(session_id, angles)
    await db.add_session_products(
        session_id,
        [j.to_session_product_input() for j in judged],
    )
    await db.complete_session(session_id, recommendation)

    return ResearchResponse(
        session_id=session_id,
        candidates=top,
        recommendation=recommendation,
        stats=ResearchStats(
            searched=state.get("searched_count", 0),
            shortlisted=state.get("shortlisted_count", 0),
            extracted=state.get("extracted_count", 0),
            judged=state.get("judged_count", 0),
        ),
    )


@app.get("/sessions")
async def list_sessions(user_id: UUID = Depends(require_user)) -> list[dict]:
    rows = await db.list_sessions(user_id)
    for r in rows:
        r["id"] = str(r["id"])
        r["created_at"] = r["created_at"].isoformat()
        if r["completed_at"]:
            r["completed_at"] = r["completed_at"].isoformat()
    return rows


@app.get("/sessions/{session_id}")
async def get_session(
    session_id: UUID, user_id: UUID = Depends(require_user)
) -> dict:
    data = await db.get_session(user_id, session_id)
    if data is None:
        raise HTTPException(404, "session not found")
    data["id"] = str(data["id"])
    data["created_at"] = data["created_at"].isoformat()
    if data.get("completed_at"):
        data["completed_at"] = data["completed_at"].isoformat()
    for c in data.get("candidates", []):
        c["session_product_id"] = str(c["session_product_id"])
        c["product_id"] = str(c["product_id"])
        c["queried_at"] = c["queried_at"].isoformat()
    return data
