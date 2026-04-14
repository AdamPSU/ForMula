"""Multi-agent hair-product recommender orchestrator.

Pipeline (CLAUDE.md):
    User prompt -> parse_profile -> generate_angles -> [Send × N]
        search_agent (stub) -> dedupe (stub) -> synthesize (stub) -> END
"""

from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

from dotenv import load_dotenv
from langchain_xai import ChatXAI
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from pydantic import BaseModel, Field, field_validator

load_dotenv()

MIN_ANGLES = 3
MAX_ANGLES = 6


class HairProfile(BaseModel):
    texture: Literal["straight", "wavy", "curly", "coily", "unknown"] = "unknown"
    porosity: Literal["low", "medium", "high", "unknown"] = "unknown"
    density: Literal["thin", "medium", "thick", "unknown"] = "unknown"
    concerns: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    free_text: str = ""


class SearchAngle(BaseModel):
    query: str = Field(min_length=1)
    justification: str = Field(min_length=1)


class SearchAngles(BaseModel):
    angles: list[SearchAngle]

    @field_validator("angles")
    @classmethod
    def _cap(cls, v: list[SearchAngle]) -> list[SearchAngle]:
        if not MIN_ANGLES <= len(v) <= MAX_ANGLES:
            raise ValueError(f"need {MIN_ANGLES}-{MAX_ANGLES} angles, got {len(v)}")
        return v


class ProductCandidate(BaseModel):
    name: str
    brand: str
    ingredients: list[str] = Field(default_factory=list)
    price: str | None = None
    url: str
    source_angle: str


class OrchestratorState(TypedDict, total=False):
    prompt: str
    profile: HairProfile | None
    angles: list[SearchAngle]
    candidates: Annotated[list[ProductCandidate], operator.add]
    recommendation: str | None


class SearchAgentInput(TypedDict):
    prompt: str
    profile: HairProfile | None
    angle: SearchAngle


_llm: ChatXAI | None = None


def _get_llm() -> ChatXAI:
    global _llm
    if _llm is None:
        _llm = ChatXAI(model="grok-4", temperature=0.2)
    return _llm

_PROFILE_PROMPT = (
    "Extract a structured hair profile from the user's message. "
    "Use 'unknown' for any attribute not stated. Keep concerns and goals short (2-5 words each). "
    "Preserve the original message in free_text."
)

_ANGLES_PROMPT = (
    f"You are the orchestrator of a product-research pipeline. Given a hair profile, "
    f"propose {MIN_ANGLES}-{MAX_ANGLES} distinct search angles that, taken together, "
    "cover the user's needs without redundancy. Every angle MUST include a justification "
    "tying it to a specific attribute/concern/goal in the profile. Prefer angles that "
    "differ by mechanism (ingredient class, product category, use case) rather than by wording."
)


async def parse_profile(state: OrchestratorState) -> dict:
    structured = _get_llm().with_structured_output(HairProfile)
    profile = await structured.ainvoke(
        [("system", _PROFILE_PROMPT), ("user", state["prompt"])]
    )
    return {"profile": profile}


async def generate_angles(state: OrchestratorState) -> dict:
    profile = state["profile"]
    structured = _get_llm().with_structured_output(SearchAngles)
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
