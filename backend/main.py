from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

from ai.orchestrator import ProductCandidate, run as run_orchestrator

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
    state = await run_orchestrator(prompt)
    return ResearchResponse(
        candidates=state.get("candidates", []) or [],
        recommendation=state.get("recommendation"),
    )
