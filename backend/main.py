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


class ResearchResult(BaseModel):
    title: str
    snippet: str
    url: str
    source: str


class ResearchResponse(BaseModel):
    results: List[ResearchResult]
    recommendation: str | None = None


def _to_result(c: ProductCandidate) -> ResearchResult:
    return ResearchResult(
        title=f"{c.brand} {c.name}".strip(),
        snippet=", ".join(c.ingredients) if c.ingredients else "",
        url=c.url,
        source=c.source_angle,
    )


@app.post("/research", response_model=ResearchResponse)
async def research(
    prompt: str = Form(...),
    images: List[UploadFile] = File(default=[]),
):
    state = await run_orchestrator(prompt)
    candidates = state.get("candidates", []) or []
    return ResearchResponse(
        results=[_to_result(c) for c in candidates],
        recommendation=state.get("recommendation"),
    )
