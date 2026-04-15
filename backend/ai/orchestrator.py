"""Multi-agent hair-product recommender orchestrator.

Pipeline:
    User prompt -> parse_profile -> research_products -> judge_candidates -> synthesize -> END
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
from pydantic import BaseModel, Field, field_validator

from ai import cache
from ai.dedup import dedup_search_results
from ai.exa import (
    PER_PAGE_PRODUCT_SCHEMA,
    PER_PAGE_SUMMARY_QUERY,
    RESEARCH_SYSTEM_PROMPT,
    SEARCH_EXCLUDE_DOMAINS,
    SEARCH_HIGHLIGHTS_QUERY,
    build_search_query,
    get_exa_client,
    profile_to_summary,
)

EST = ZoneInfo("America/New_York")
RESEARCH_NUM_RESULTS = 100

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


HairType = Literal[
    "straight", "1A", "1B", "1C",
    "wavy", "2A", "2B", "2C",
    "curly", "3A", "3B", "3C",
    "coily", "4A", "4B", "4C",
    "unknown",
]


class HairProfile(BaseModel):
    type: HairType = "unknown"
    porosity: Literal["low", "medium", "high", "unknown"] = "unknown"
    density: Literal["thin", "medium", "thick", "unknown"] = "unknown"
    concerns: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    free_text: str = ""

    def is_informative(self) -> bool:
        return (
            self.type != "unknown"
            or self.porosity != "unknown"
            or self.density != "unknown"
            or bool(self.concerns)
            or bool(self.goals)
        )


class ProfileParseError(RuntimeError):
    """Raised when the hair profile cannot be extracted after retries."""


class AxisVerdict(BaseModel):
    rationale: str
    evidence_tokens: list[str]
    weaknesses: list[str]
    sub_criteria: dict[str, bool]
    score: int = Field(ge=1, le=5)


class JudgeVerdict(BaseModel):
    moisture_fit: AxisVerdict
    scalp_safety: AxisVerdict
    structural_fit: AxisVerdict
    summary: str


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
    moisture_fit: AxisVerdict | None = None
    scalp_safety: AxisVerdict | None = None
    structural_fit: AxisVerdict | None = None
    overall_score: float | None = None
    summary: str | None = None

    @field_validator("ingredients", mode="before")
    @classmethod
    def _coerce_ingredients(cls, v):
        if isinstance(v, str):
            v = [tok.strip() for tok in v.split(",") if tok.strip()]
        if isinstance(v, list):
            return [x for x in v if isinstance(x, str) and x.strip().lower() not in ("null", "none", "")]
        return v

    @field_validator("category", mode="before")
    @classmethod
    def _coerce_category(cls, v):
        if not isinstance(v, str):
            return "other"
        key = v.strip().lower()
        valid = {"shampoo", "conditioner", "leave-in", "mask", "oil",
                 "gel", "mousse", "cream", "serum", "other"}
        return key if key in valid else "other"

    @field_validator("key_actives", "allergens", mode="before")
    @classmethod
    def _coerce_string_list(cls, v):
        if isinstance(v, str):
            return [tok.strip() for tok in v.split(",") if tok.strip()]
        return v


class OrchestratorState(TypedDict, total=False):
    prompt: str
    profile: HairProfile | None
    candidates: list[ProductCandidate]
    recommendation: str | None
    cache_hit: bool


FAST_MODEL = "grok-4-1-fast-non-reasoning"
REASONING_MODEL = "grok-4-1-fast-reasoning"

_grok_sem = asyncio.Semaphore(32)
_fast_llm = ChatXAI(model=FAST_MODEL)
_reasoning_llm = ChatXAI(model=REASONING_MODEL, temperature=0.0)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_PROFILE_PROMPT = (_PROMPTS_DIR / "parse_profile.txt").read_text().strip()
_JUDGE_PROMPT = (_PROMPTS_DIR / "judge.txt").read_text().strip()
_ANGLE_PROMPT = (_PROMPTS_DIR / "angle_generation.txt").read_text().strip()


class SearchAngles(BaseModel):
    queries: list[str] = Field(min_length=9, max_length=9)


async def _generate_angles(profile: HairProfile) -> list[str]:
    structured = _fast_llm.with_structured_output(SearchAngles)
    user = f"HAIR PROFILE\n{profile_to_summary(profile)}"
    async with _grok_sem:
        result = await structured.ainvoke(
            [("system", _ANGLE_PROMPT), ("user", user)]
        )
    return result.queries

_JUDGE_USER_TEMPLATE = """HAIR PROFILE
{profile_summary}

PRODUCT
Category: {category}
Ingredients (INCI, in order):
{ingredients}"""


PROFILE_PARSE_ATTEMPTS = 3


async def parse_profile(state: OrchestratorState) -> dict:
    structured = _fast_llm.with_structured_output(HairProfile)
    messages = [("system", _PROFILE_PROMPT), ("user", state["prompt"])]
    last_exc: Exception | None = None
    for _ in range(PROFILE_PARSE_ATTEMPTS):
        try:
            async with _grok_sem:
                profile = await structured.ainvoke(messages)
            if profile.is_informative():
                return {"profile": profile}
        except Exception as e:
            last_exc = e
    raise ProfileParseError(
        "Could not extract a hair profile from the prompt"
    ) from last_exc


SEARCH_TYPE = "deep-reasoning"


async def research_products(state: OrchestratorState) -> dict:
    query = build_search_query(state["profile"], state["prompt"])
    client = get_exa_client()

    angles = await _generate_angles(state["profile"])
    search_kwargs = dict(
        type=SEARCH_TYPE,
        system_prompt=RESEARCH_SYSTEM_PROMPT,
        num_results=RESEARCH_NUM_RESULTS,
        exclude_domains=SEARCH_EXCLUDE_DOMAINS,
        contents={
            "highlights": {"query": SEARCH_HIGHLIGHTS_QUERY, "num_sentences": 3},
        },
    )
    search_results = await asyncio.gather(
        *(
            client.search(
                query=query,
                additional_queries=angles[i * 3 : (i + 1) * 3],
                **search_kwargs,
            )
            for i in range(3)
        )
    )
    seen: set[str] = set()
    raw_results: list = []
    for sr in search_results:
        for r in sr.results:
            if r.highlights and r.url not in seen:
                seen.add(r.url)
                raw_results.append(r)
    if not raw_results:
        return {"candidates": []}

    survivors = dedup_search_results(raw_results)
    print(
        f"[dedup] {len(survivors)}/{len(raw_results)} urls after semantic collapse",
        flush=True,
    )
    urls = [r.url for r in survivors]

    # Exa caps urls at 100 per /contents request.
    contents_result = await client.get_contents(
        urls[:100],
        summary={"query": PER_PAGE_SUMMARY_QUERY, "schema": PER_PAGE_PRODUCT_SCHEMA},
        max_age_hours=-1,
    )

    candidates: list[ProductCandidate] = []
    for r in contents_result.results:
        raw = r.summary
        if not raw:
            continue
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                continue
        if not isinstance(raw, dict):
            continue
        raw.setdefault("url", r.url)
        try:
            cand = ProductCandidate(**raw)
        except Exception:
            continue
        if cand.name and cand.brand and cand.ingredients:
            candidates.append(cand)
    return {"candidates": candidates}


JUDGE_ATTEMPTS = 2
TOP_K = 5


async def _judge_one(
    candidate: ProductCandidate, profile_summary: str
) -> JudgeVerdict | None:
    structured = _reasoning_llm.with_structured_output(JudgeVerdict)
    messages = [
        ("system", _JUDGE_PROMPT),
        (
            "user",
            _JUDGE_USER_TEMPLATE.format(
                profile_summary=profile_summary,
                category=candidate.category,
                ingredients="\n".join(f"- {ing}" for ing in candidate.ingredients),
            ),
        ),
    ]
    for _ in range(JUDGE_ATTEMPTS):
        try:
            async with _grok_sem:
                return await structured.ainvoke(messages)
        except Exception:
            continue
    return None


async def judge_candidates(state: OrchestratorState) -> dict:
    candidates = state.get("candidates", [])
    if not candidates:
        return {"candidates": []}
    profile_summary = profile_to_summary(state["profile"])
    verdicts = await asyncio.gather(
        *(_judge_one(c, profile_summary) for c in candidates)
    )
    judged: list[ProductCandidate] = []
    for cand, verdict in zip(candidates, verdicts):
        if verdict is None:
            continue
        overall = (
            verdict.moisture_fit.score
            + verdict.scalp_safety.score
            + verdict.structural_fit.score
        ) / 3
        judged.append(
            cand.model_copy(
                update={
                    "moisture_fit": verdict.moisture_fit,
                    "scalp_safety": verdict.scalp_safety,
                    "structural_fit": verdict.structural_fit,
                    "overall_score": overall,
                    "summary": verdict.summary,
                }
            )
        )
    judged.sort(key=lambda c: c.overall_score or 0.0, reverse=True)
    return {"candidates": judged[:TOP_K]}


async def synthesize(state: OrchestratorState) -> dict:
    if state.get("recommendation") is not None:
        return {}
    candidates = state.get("candidates", [])
    return {"recommendation": f"{len(candidates)} candidate(s) found."}


async def cache_lookup(state: OrchestratorState) -> dict:
    summary = profile_to_summary(state["profile"])
    hit = cache.lookup(summary)
    if hit is None:
        print("[cache] miss", flush=True)
        return {"cache_hit": False}
    print(f"[cache] hit ({len(hit['candidates'])} candidates)", flush=True)
    return {
        "cache_hit": True,
        "candidates": [ProductCandidate(**c) for c in hit["candidates"]],
        "recommendation": hit.get("recommendation"),
    }


async def cache_upsert(state: OrchestratorState) -> dict:
    summary = profile_to_summary(state["profile"])
    cache.upsert(summary, state.get("candidates", []), state.get("recommendation"))
    return {}


def _route_after_cache(state: OrchestratorState) -> str:
    return "synthesize" if state.get("cache_hit") else "research_products"


def _route_after_synthesize(state: OrchestratorState) -> str:
    return END if state.get("cache_hit") else "cache_upsert"


def build_graph():
    g = StateGraph(OrchestratorState)
    g.add_node("parse_profile", parse_profile)
    g.add_node("cache_lookup", cache_lookup)
    g.add_node("research_products", research_products)
    g.add_node("judge_candidates", judge_candidates)
    g.add_node("synthesize", synthesize)
    g.add_node("cache_upsert", cache_upsert)
    g.add_edge(START, "parse_profile")
    g.add_edge("parse_profile", "cache_lookup")
    g.add_conditional_edges(
        "cache_lookup",
        _route_after_cache,
        {"research_products": "research_products", "synthesize": "synthesize"},
    )
    g.add_edge("research_products", "judge_candidates")
    g.add_edge("judge_candidates", "synthesize")
    g.add_conditional_edges(
        "synthesize",
        _route_after_synthesize,
        {"cache_upsert": "cache_upsert", END: END},
    )
    g.add_edge("cache_upsert", END)
    return g.compile()


_graph = None


async def run(prompt: str) -> OrchestratorState:
    global _graph
    if _graph is None:
        _graph = build_graph()
    return await _graph.ainvoke({"prompt": prompt})
