from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

from ai.orchestrator import (
    ProductCandidate,
    ProfileParseError,
    run as run_orchestrator,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResearchResponse(BaseModel):
    candidates: List[ProductCandidate]
    recommendation: str | None = None


@app.post("/research", response_model=ResearchResponse)
async def research(
    prompt: str = Form(...),
    images: List[UploadFile] = File(default=[]),
):
    try:
        state = await run_orchestrator(prompt)
    except ProfileParseError:
        raise HTTPException(status_code=503, detail="Service unavailable: could not parse hair profile")
    return ResearchResponse(
        candidates=state.get("candidates", []) or [],
        recommendation=state.get("recommendation"),
    )
