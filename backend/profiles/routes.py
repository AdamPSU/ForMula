"""FastAPI routes for the onboarding quiz, HairProfile CRUD, and current-products."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ai.orchestrator import HairProfile
from auth import require_user
from db import (
    add_current_product,
    delete_profile,
    list_current_products,
    load_profile,
    remove_current_product,
    save_profile,
)
from profiles.quiz import QUIZ, QuizAnswerError, answers_to_profile

router = APIRouter()


class AnswersPayload(BaseModel):
    answers: dict[str, Any]


@router.get("/quiz")
def get_quiz() -> dict:
    return QUIZ


@router.get("/profile", response_model=HairProfile)
async def get_profile(user_id: UUID = Depends(require_user)) -> HairProfile:
    profile = await load_profile(user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="No profile on file")
    return profile


@router.post("/profile", response_model=HairProfile)
async def post_profile(
    payload: AnswersPayload, user_id: UUID = Depends(require_user)
) -> HairProfile:
    try:
        profile = answers_to_profile(payload.answers)
    except QuizAnswerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await save_profile(user_id, profile)
    return profile


@router.delete("/profile", status_code=204)
async def delete_profile_route(user_id: UUID = Depends(require_user)) -> None:
    await delete_profile(user_id)


# --- current-products ------------------------------------------------------


class CurrentProductPayload(BaseModel):
    product_id: UUID
    notes: str | None = None


@router.get("/profile/current-products")
async def list_current(user_id: UUID = Depends(require_user)) -> list[dict]:
    rows = await list_current_products(user_id)
    for r in rows:
        r["id"] = str(r["id"])
        r["added_at"] = r["added_at"].isoformat()
    return rows


@router.post("/profile/current-products", status_code=204)
async def add_current(
    payload: CurrentProductPayload,
    user_id: UUID = Depends(require_user),
) -> None:
    await add_current_product(user_id, payload.product_id, payload.notes)


@router.delete("/profile/current-products/{product_id}", status_code=204)
async def remove_current(
    product_id: UUID,
    user_id: UUID = Depends(require_user),
) -> None:
    await remove_current_product(user_id, product_id)
