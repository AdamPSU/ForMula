"""Multi-agent hair-product recommender orchestrator.

Pipeline: search -> dedup (URL/content) -> extract (upsert to catalog) -> judge -> synthesize.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, TypedDict
from uuid import UUID
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field, field_validator

from ai.auto_prompt import auto_prompt
from ai.dedup import dedup_search_results
from ai.embeddings import embed
from ai.exa import (
    PER_PAGE_PRODUCT_SCHEMA,
    PER_PAGE_SUMMARY_QUERY,
    RESEARCH_SYSTEM_PROMPT,
    SEARCH_EXCLUDE_DOMAINS,
    SEARCH_HIGHLIGHTS_QUERY,
    get_exa_client,
)
from ai.judge import AxisVerdict, JudgeVerdict, panel_judge
import db

EST = ZoneInfo("America/New_York")
SEARCH_TYPE = "deep-reasoning"
SEARCH_BATCHES = 3
ANGLES_PER_BATCH = 3
RESEARCH_NUM_RESULTS = 100
MAX_EXTRACT_URLS = 100
TOP_K = 5

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
    "1A", "1B", "1C",
    "2A", "2B", "2C",
    "3A", "3B", "3C",
    "4A", "4B", "4C",
]
Density = Literal["thin", "medium", "thick"]
StrandThickness = Literal["fine", "medium", "coarse"]
ScalpCondition = Literal["oily", "dry", "flaky", "sensitive", "balanced"]
ChemicalTreatment = Literal["bleach", "color", "relaxer", "keratin", "none"]
ChemicalRecency = Literal["within_1mo", "1_3mo", "3_6mo", "6plus", "na"]
HeatFrequency = Literal["daily", "weekly", "rare", "never"]
ProductAbsorption = Literal["soaks", "sits", "greasy", "unsure"]
WashFrequency = Literal["daily", "2_3_days", "weekly", "less"]
Climate = Literal["humid", "dry", "cold", "mixed"]
StylingTime = Literal["under_10", "10_30", "30plus"]


class HairProfile(BaseModel):
    type: HairType
    density: Density
    strand_thickness: StrandThickness
    scalp_condition: ScalpCondition
    chemical_history: list[ChemicalTreatment]
    chemical_recency: ChemicalRecency
    heat_frequency: HeatFrequency
    concerns: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    product_absorption: ProductAbsorption
    wash_frequency: WashFrequency
    climate: Climate
    styling_time: StylingTime
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
    moisture_fit: AxisVerdict | None = None
    scalp_safety: AxisVerdict | None = None
    structural_fit: AxisVerdict | None = None
    overall_score: float | None = None
    panel_scores: dict[str, float] | None = None
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


@dataclass
class JudgedEntry:
    candidate: ProductCandidate
    product_id: UUID
    verdicts: dict[str, JudgeVerdict]
    rank: int | None = None

    def to_session_product_input(self) -> db.SessionProductInput:
        return db.SessionProductInput(
            product_id=self.product_id,
            rank=self.rank,
            overall_score=self.candidate.overall_score or 0.0,
            summary=self.candidate.summary or "",
            queried_at=self.candidate.queried_at,
            judges=[
                db.JudgePanelInput(
                    judge=jname,
                    overall_score=_overall(v),
                    summary=v.summary,
                    axes=[
                        _axis_input("moisture_fit", v.moisture_fit),
                        _axis_input("scalp_safety", v.scalp_safety),
                        _axis_input("structural_fit", v.structural_fit),
                    ],
                )
                for jname, v in self.verdicts.items()
            ],
        )


def _overall(v: JudgeVerdict) -> float:
    return (v.moisture_fit.score + v.scalp_safety.score + v.structural_fit.score) / 3


def _axis_input(axis: str, av: AxisVerdict) -> db.AxisVerdictInput:
    return db.AxisVerdictInput(
        axis=axis,
        score=av.score,
        rationale=av.rationale,
        evidence_tokens=list(av.evidence_tokens),
        weaknesses=list(av.weaknesses),
        sub_criteria=dict(av.sub_criteria),
    )


class OrchestratorState(TypedDict, total=False):
    prompt: str
    profile: HairProfile | None
    raw_results: list
    survivors: list
    first_person_account: str
    angle_queries: list[str]
    searched_count: int
    shortlisted_count: int
    extracted: list[tuple[ProductCandidate, UUID]]
    extracted_count: int
    judged: list[JudgedEntry]
    candidates: list[ProductCandidate]
    judged_count: int
    recommendation: str | None


async def search(state: OrchestratorState) -> dict:
    ap = await auto_prompt(state["profile"], state["prompt"])
    client = get_exa_client()
    search_kwargs = dict(
        type=SEARCH_TYPE,
        system_prompt=RESEARCH_SYSTEM_PROMPT,
        num_results=RESEARCH_NUM_RESULTS,
        exclude_domains=SEARCH_EXCLUDE_DOMAINS,
        contents={"highlights": {"query": SEARCH_HIGHLIGHTS_QUERY, "num_sentences": 3}},
    )
    search_results = await asyncio.gather(
        *(
            client.search(
                query=ap.primary_query,
                additional_queries=ap.angle_queries[i * ANGLES_PER_BATCH : (i + 1) * ANGLES_PER_BATCH],
                **search_kwargs,
            )
            for i in range(SEARCH_BATCHES)
        )
    )
    seen: set[str] = set()
    raw_results: list = []
    for sr in search_results:
        for r in sr.results:
            if r.highlights and r.url not in seen:
                seen.add(r.url)
                raw_results.append(r)
    print(f"[search] {len(raw_results)} urls", flush=True)
    return {
        "raw_results": raw_results,
        "searched_count": len(raw_results),
        "first_person_account": ap.first_person_account,
        "angle_queries": list(ap.angle_queries),
    }


async def dedup(state: OrchestratorState) -> dict:
    raw = state.get("raw_results", [])
    if not raw:
        return {"survivors": [], "shortlisted_count": 0}
    survivors = await asyncio.to_thread(dedup_search_results, raw)
    print(f"[dedup] {len(survivors)}/{len(raw)} urls kept", flush=True)
    return {"survivors": survivors, "shortlisted_count": len(survivors)}


async def extract(state: OrchestratorState) -> dict:
    survivors = state.get("survivors", [])[:MAX_EXTRACT_URLS]
    if not survivors:
        return {"extracted": [], "extracted_count": 0}
    print(f"[extract] fetching contents for {len(survivors)} urls", flush=True)
    contents_result = await get_exa_client().get_contents(
        [r.url for r in survivors],
        summary={"query": PER_PAGE_SUMMARY_QUERY, "schema": PER_PAGE_PRODUCT_SCHEMA},
        max_age_hours=-1,
    )
    parsed: list[ProductCandidate] = []
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
            parsed.append(cand)
    # Cheap within-session dedup by (brand, name) before hitting the catalog.
    seen_keys: set[tuple[str, str]] = set()
    unique: list[ProductCandidate] = []
    for c in parsed:
        k = (c.brand.lower().strip(), c.name.lower().strip())
        if k in seen_keys:
            continue
        seen_keys.add(k)
        unique.append(c)
    if not unique:
        return {"extracted": [], "extracted_count": 0}
    texts = [f"{c.brand} {c.name} {c.category}" for c in unique]
    vectors = await asyncio.to_thread(embed, texts)
    extracted: list[tuple[ProductCandidate, UUID]] = []
    seen_ids: set[UUID] = set()
    for cand, vec in zip(unique, vectors):
        product_id, _created = await db.upsert_product(cand, vec)
        if product_id in seen_ids:
            continue
        seen_ids.add(product_id)
        extracted.append((cand, product_id))
    print(f"[extract] {len(extracted)} unique catalog products", flush=True)
    return {"extracted": extracted, "extracted_count": len(extracted)}


async def judge_candidates(state: OrchestratorState) -> dict:
    extracted = state.get("extracted", [])
    if not extracted:
        return {"judged": [], "candidates": [], "judged_count": 0}
    fpa = state.get("first_person_account") or ""
    panel_results = await asyncio.gather(
        *(panel_judge(c.category, c.ingredients, fpa) for c, _ in extracted)
    )
    judged: list[JudgedEntry] = []
    for (cand, product_id), verdicts in zip(extracted, panel_results):
        if not verdicts:
            continue
        narrative = verdicts.get("grok") or next(iter(verdicts.values()))
        panel_scores = {j: _overall(v) for j, v in verdicts.items()}
        overall = sum(panel_scores.values()) / len(panel_scores)
        enriched = cand.model_copy(update={
            "moisture_fit": narrative.moisture_fit,
            "scalp_safety": narrative.scalp_safety,
            "structural_fit": narrative.structural_fit,
            "overall_score": overall,
            "panel_scores": panel_scores,
            "summary": narrative.summary,
        })
        judged.append(JudgedEntry(candidate=enriched, product_id=product_id, verdicts=verdicts))
    judged.sort(key=lambda j: j.candidate.overall_score or 0.0, reverse=True)
    for i, j in enumerate(judged):
        j.rank = i + 1 if i < TOP_K else None
    top = [j.candidate for j in judged if j.rank is not None]
    print(f"[judge] top {len(top)} of {len(judged)} (panel averaged)", flush=True)
    return {
        "judged": judged,
        "candidates": top,
        "judged_count": len(judged),
    }


async def synthesize(state: OrchestratorState) -> dict:
    candidates = state.get("candidates", [])
    print(f"[synthesize] writing recommendation for {len(candidates)} candidates", flush=True)
    return {"recommendation": f"{len(candidates)} candidate(s) found."}


def build_graph():
    g = StateGraph(OrchestratorState)
    g.add_node("search", search)
    g.add_node("dedup", dedup)
    g.add_node("extract", extract)
    g.add_node("judge_candidates", judge_candidates)
    g.add_node("synthesize", synthesize)
    g.add_edge(START, "search")
    g.add_edge("search", "dedup")
    g.add_edge("dedup", "extract")
    g.add_edge("extract", "judge_candidates")
    g.add_edge("judge_candidates", "synthesize")
    g.add_edge("synthesize", END)
    return g.compile()


_graph = None


async def run(prompt: str, profile: HairProfile) -> OrchestratorState:
    global _graph
    if _graph is None:
        _graph = build_graph()
    profile_with_prompt = profile.model_copy(update={"free_text": prompt})
    return await _graph.ainvoke({"prompt": prompt, "profile": profile_with_prompt})
