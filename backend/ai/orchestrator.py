"""Multi-agent hair-product recommender orchestrator.

Pipeline:
    User prompt -> parse_profile -> research_products -> synthesize -> END
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Literal, TypedDict
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()
from langchain_xai import ChatXAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from ai.tavily import PRODUCT_SCHEMA, build_research_query, get_tavily_client

EST = ZoneInfo("America/New_York")

Category = Literal[
    "shampoo",
    "conditioner",
    "leave-in",
    "mask",
    "oil",
    "gel",
    "mousse",
    "cream",
    "serum",
    "other",
]


class HairProfile(BaseModel):
    texture: Literal["straight", "wavy", "curly", "coily", "unknown"] = "unknown"
    porosity: Literal["low", "medium", "high", "unknown"] = "unknown"
    density: Literal["thin", "medium", "thick", "unknown"] = "unknown"
    concerns: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    free_text: str = ""


class ProductCandidate(BaseModel):
    name: str
    brand: str
    url: str
    ingredients: list[str]
    category: Category
    price: str | None = None
    key_actives: list[str] = Field(default_factory=list)
    allergens: list[str] = Field(default_factory=list)
    queried_at: datetime = Field(default_factory=lambda: datetime.now(EST))


class OrchestratorState(TypedDict, total=False):
    prompt: str
    profile: HairProfile | None
    candidates: list[ProductCandidate]
    recommendation: str | None


FAST_MODEL = "grok-4-1-fast-non-reasoning"

_grok_sem = asyncio.Semaphore(32)
_fast_llm = ChatXAI(model=FAST_MODEL)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_PROFILE_PROMPT = (_PROMPTS_DIR / "parse_profile.txt").read_text().strip()


async def parse_profile(state: OrchestratorState) -> dict:
    structured = _fast_llm.with_structured_output(HairProfile)
    async with _grok_sem:
        profile = await structured.ainvoke(
            [("system", _PROFILE_PROMPT), ("user", state["prompt"])]
        )
    return {"profile": profile}


async def research_products(state: OrchestratorState) -> dict:
    query = build_research_query(state.get("profile"), state["prompt"])
    client = get_tavily_client()
    resp = await client.research(
        input=query, model="mini", output_schema=PRODUCT_SCHEMA
    )
    request_id = resp["request_id"]
    while True:
        result = await client.get_research(request_id)
        if result["status"] in ("completed", "failed"):
            break
        await asyncio.sleep(5)
    if result["status"] != "completed":
        return {"candidates": []}
    content = result["content"]
    if isinstance(content, str):
        content = json.loads(content)
    return {
        "candidates": [ProductCandidate(**c) for c in content.get("candidates", [])]
    }


async def synthesize(state: OrchestratorState) -> dict:
    candidates = state.get("candidates", [])
    return {"recommendation": f"{len(candidates)} candidate(s) found."}


def build_graph():
    g = StateGraph(OrchestratorState)
    g.add_node("parse_profile", parse_profile)
    g.add_node("research_products", research_products)
    g.add_node("synthesize", synthesize)
    g.add_edge(START, "parse_profile")
    g.add_edge("parse_profile", "research_products")
    g.add_edge("research_products", "synthesize")
    g.add_edge("synthesize", END)
    return g.compile()


_graph = None


async def run(prompt: str) -> OrchestratorState:
    global _graph
    if _graph is None:
        _graph = build_graph()
    return await _graph.ainvoke({"prompt": prompt})
