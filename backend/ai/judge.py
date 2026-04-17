"""Three-judge panel: Grok (xAI direct) + MiniMax-M2.7 + GLM-5.1 (OpenRouter).

Each judge sees the same blinded input (first-person account + ingredients) and
produces a full JudgeVerdict (three axes + summary). `panel_judge` returns every
successful judge's verdict; the caller decides what to aggregate and what to persist.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

load_dotenv()

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_xai import ChatXAI
from pydantic import BaseModel

_JUDGE_PROMPT = (
    Path(__file__).resolve().parent.parent / "prompts" / "judge.txt"
).read_text().strip()

JudgeName = Literal["grok", "minimax", "glm"]
JUDGE_ATTEMPTS = 2
PROVIDER_CONCURRENCY = 128
CHEAP_MODE_ENV = "CHEAP_MODE"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


Score = Literal[1, 2, 3, 4, 5]


class AxisVerdict(BaseModel):
    rationale: str
    evidence_tokens: list[str]
    weaknesses: list[str]
    sub_criteria: dict[str, bool]
    score: Score


class JudgeVerdict(BaseModel):
    moisture_fit: AxisVerdict
    scalp_safety: AxisVerdict
    structural_fit: AxisVerdict
    summary: str


def _inline_refs(schema: dict) -> dict:
    """Resolve $defs/$ref inline — Gemini via OpenRouter rejects nested references."""
    defs = schema.get("$defs") or schema.get("definitions") or {}

    def walk(node):
        if isinstance(node, dict):
            if set(node) == {"$ref"}:
                return walk(defs[node["$ref"].split("/")[-1]])
            return {k: walk(v) for k, v in node.items() if k not in ("$defs", "definitions")}
        if isinstance(node, list):
            return [walk(x) for x in node]
        return node

    return walk(schema)


_JUDGE_SCHEMA = _inline_refs(JudgeVerdict.model_json_schema())


_JUDGE_USER_TEMPLATE = """USER
{first_person_account}

PRODUCT
Category: {category}
Ingredients (INCI, in order):
{ingredients}"""


def _openrouter(model: str, *, max_tokens: int, reasoning: bool) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url=OPENROUTER_BASE_URL,
        temperature=0.0,
        max_tokens=max_tokens,
        extra_body={"reasoning": {"effort": "low"}} if reasoning else None,
    )


_JUDGES: dict[JudgeName, BaseChatModel] = {
    "grok": ChatXAI(model="grok-4-1-fast-reasoning", temperature=0.0, max_tokens=65536),
    "minimax": _openrouter("minimax/minimax-m2.7", max_tokens=8192, reasoning=False),
    "glm": _openrouter("z-ai/glm-5.1", max_tokens=8192, reasoning=True),
}

_STRUCTURED_METHOD: dict[JudgeName, str] = {
    "grok": "function_calling",
    "minimax": "function_calling",
    "glm": "function_calling",
}

_sems: dict[JudgeName, asyncio.Semaphore] = {
    name: asyncio.Semaphore(PROVIDER_CONCURRENCY) for name in _JUDGES
}


def _user_msg(category: str, ingredients: list[str], first_person_account: str) -> str:
    return _JUDGE_USER_TEMPLATE.format(
        first_person_account=first_person_account,
        category=category,
        ingredients="\n".join(f"- {i}" for i in ingredients),
    )


async def _judge(
    name: JudgeName, category: str, ingredients: list[str], fpa: str
) -> JudgeVerdict | None:
    structured = _JUDGES[name].with_structured_output(
        _JUDGE_SCHEMA, method=_STRUCTURED_METHOD[name]
    )
    messages = [("system", _JUDGE_PROMPT), ("user", _user_msg(category, ingredients, fpa))]
    last_err: Exception | None = None
    for _ in range(JUDGE_ATTEMPTS):
        try:
            async with _sems[name]:
                raw = await structured.ainvoke(messages)
            return JudgeVerdict.model_validate(raw)
        except Exception as e:
            last_err = e
    if last_err is not None:
        print(f"[judge:{name}] failed: {type(last_err).__name__}: {last_err}", flush=True)
    return None


async def panel_judge(
    category: str, ingredients: list[str], first_person_account: str
) -> dict[JudgeName, JudgeVerdict]:
    """Run all judges in parallel. Return every successful judge's full verdict.

    Internal cheap mode: if env `CHEAP_MODE=1`, skip Gemini + Claude (Grok only).
    """
    names: tuple[JudgeName, ...] = (
        ("grok",) if os.environ.get(CHEAP_MODE_ENV) == "1" else tuple(_JUDGES)
    )
    verdicts = await asyncio.gather(
        *(_judge(name, category, ingredients, first_person_account) for name in names)
    )
    return {name: v for name, v in zip(names, verdicts) if v is not None}
