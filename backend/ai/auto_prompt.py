"""Auto-prompter: turn (HairProfile, free-text) into Exa queries + a first-person account."""

from __future__ import annotations

import asyncio
from pathlib import Path

from langchain_xai import ChatXAI
from pydantic import BaseModel, Field

from ai.exa import profile_to_summary

_PROMPT = (
    Path(__file__).resolve().parent.parent / "prompts" / "auto_prompt.txt"
).read_text().strip()

_llm = ChatXAI(model="grok-4-1-fast-non-reasoning")
_sem = asyncio.Semaphore(128)


class AutoPrompt(BaseModel):
    primary_query: str = Field(
        description="One long, semantically-rich natural-language product description."
    )
    angle_queries: list[str] = Field(min_length=9, max_length=9)
    first_person_account: str = Field(
        description="First-person paragraph the judge reads before ingredients."
    )


async def auto_prompt(profile, free_text: str) -> AutoPrompt:
    structured = _llm.with_structured_output(AutoPrompt)
    user = (
        f"HAIR PROFILE\n{profile_to_summary(profile)}\n\n"
        f"USER REQUEST\n{free_text.strip() or '(none)'}"
    )
    async with _sem:
        return await structured.ainvoke([("system", _PROMPT), ("user", user)])
