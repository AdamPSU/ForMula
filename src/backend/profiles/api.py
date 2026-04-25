from fastapi import APIRouter, Depends, HTTPException, Request, status

from auth.jwt import get_current_user_id
from profiles.models import HairProfile, HairProfileSubmission
from profiles.repository import get_latest_hair_profile, insert_hair_intake

router = APIRouter(prefix="/me", tags=["profiles"])


@router.post("/hair-profile", status_code=status.HTTP_201_CREATED)
async def submit_hair_profile(
    payload: HairProfileSubmission,
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, str]:
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        intake_id = await insert_hair_intake(
            conn, user_id, payload.quiz_version, payload.profile
        )
    return {"id": intake_id}


@router.get("/hair-profile")
async def read_latest_hair_profile(
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> HairProfile:
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        profile = await get_latest_hair_profile(conn, user_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no hair profile yet")
    return profile
