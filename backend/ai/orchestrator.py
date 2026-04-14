"""Multi-agent hair-product recommender orchestrator.

Pipeline:
    User prompt -> parse_profile -> generate_angles -> [Send × N]
        search_agent (stub) -> dedupe (stub) -> synthesize (stub) -> END
"""

from __future__ import annotations

import operator
from datetime import datetime
from zoneinfo import ZoneInfo

EST = ZoneInfo("America/New_York")
from pathlib import Path
from typing import Annotated, Literal, TypedDict

from dotenv import load_dotenv; load_dotenv()
from langchain_xai import ChatXAI
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from pydantic import BaseModel, Field, field_validator

MIN_ANGLES = 3
MAX_ANGLES = 6


class HairProfile(BaseModel):
    """Structured hair attributes extracted from the user's free-text prompt."""

    texture: Literal["straight", "wavy", "curly", "coily", "unknown"] = "unknown"
    porosity: Literal["low", "medium", "high", "unknown"] = "unknown"
    density: Literal["thin", "medium", "thick", "unknown"] = "unknown"
    concerns: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    free_text: str = ""


class SearchAngle(BaseModel):
    """One research direction: a search query for a specific product need."""

    query: str = Field(min_length=1)


class SearchAngles(BaseModel):
    """Wrapper enforcing the CLAUDE.md cap of MIN_ANGLES-MAX_ANGLES angles per run."""

    angles: list[SearchAngle]

    @field_validator("angles")
    @classmethod
    def _cap(cls, v: list[SearchAngle]) -> list[SearchAngle]:
        if not MIN_ANGLES <= len(v) <= MAX_ANGLES:
            raise ValueError(f"need {MIN_ANGLES}-{MAX_ANGLES} angles, got {len(v)}")
        return v


class ProductCandidate(BaseModel):
    """A single product hit from a search agent; matches the Pinecone storage schema."""

    name: str
    brand: str
    ingredients: list[str] = Field(default_factory=list)
    price: str | None = None
    url: str
    source_angle: str
    queried_at: datetime = Field(default_factory=lambda: datetime.now(EST))


class OrchestratorState(TypedDict, total=False):
    """Shared state threaded through every LangGraph node in the pipeline."""

    prompt: str
    profile: HairProfile | None
    angles: list[SearchAngle]
    candidates: Annotated[list[ProductCandidate], operator.add]
    recommendation: str | None


class SearchAgentInput(TypedDict):
    """Per-invocation payload handed to each fanned-out search_agent node."""

    prompt: str
    profile: HairProfile | None
    angle: SearchAngle


REASONING_MODEL = "grok-4-1-fast-reasoning"
FAST_MODEL = "grok-4-1-fast-non-reasoning"

_llms: dict[str, ChatXAI] = {}


def _get_llm(model: str) -> ChatXAI:
    if model not in _llms:
        _llms[model] = ChatXAI(model=model)
    return _llms[model]

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_PROFILE_PROMPT = (_PROMPTS_DIR / "parse_profile.txt").read_text().strip()
_ANGLES_PROMPT = (
    (_PROMPTS_DIR / "generate_angles.txt")
    .read_text()
    .strip()
    .format(min_angles=MIN_ANGLES, max_angles=MAX_ANGLES)
)


async def parse_profile(state: OrchestratorState) -> dict:
    structured = _get_llm(FAST_MODEL).with_structured_output(HairProfile)
    profile = await structured.ainvoke(
        [("system", _PROFILE_PROMPT), ("user", state["prompt"])]
    )
    return {"profile": profile}


async def generate_angles(state: OrchestratorState) -> dict:
    profile = state["profile"]
    structured = _get_llm(REASONING_MODEL).with_structured_output(SearchAngles)
    result = await structured.ainvoke(
        [
            ("system", _ANGLES_PROMPT),
            ("user", profile.model_dump_json() if profile else state["prompt"]),
        ]
    )
    return {"angles": result.angles}


def fan_out(state: OrchestratorState) -> list[Send]:
    return [
        Send(
            "search_agent",
            {"prompt": state["prompt"], "profile": state.get("profile"), "angle": a},
        )
        for a in state["angles"]
    ]


async def search_agent(payload: SearchAgentInput) -> dict:
    # TODO: ai/tavily.py — search(angle.query) -> filter snippets -> extract -> ProductCandidate
    return {"candidates": []}


async def dedupe(state: OrchestratorState) -> dict:
    # TODO: ai/pinecone.py — upsert + >97% similarity filter
    return {"candidates": state.get("candidates", [])}


async def synthesize(state: OrchestratorState) -> dict:
    candidates = state.get("candidates", [])
    return {"recommendation": f"{len(candidates)} candidate(s) found."}


def build_graph():
    g = StateGraph(OrchestratorState)
    g.add_node("parse_profile", parse_profile)
    g.add_node("generate_angles", generate_angles)
    g.add_node("search_agent", search_agent)
    g.add_node("dedupe", dedupe)
    g.add_node("synthesize", synthesize)

    g.add_edge(START, "parse_profile")
    g.add_edge("parse_profile", "generate_angles")
    g.add_conditional_edges("generate_angles", fan_out, ["search_agent"])
    g.add_edge("search_agent", "dedupe")
    g.add_edge("dedupe", "synthesize")
    g.add_edge("synthesize", END)

    return g.compile()


_graph = None


async def run(prompt: str) -> OrchestratorState:
    global _graph
    if _graph is None:
        _graph = build_graph()
    return await _graph.ainvoke({"prompt": prompt})
