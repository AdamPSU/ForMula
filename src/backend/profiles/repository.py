import asyncpg

from profiles.models import HairProfile


async def insert_hair_intake(
    conn: asyncpg.Connection,
    user_id: str,
    quiz_version: int,
    profile: HairProfile,
) -> str:
    row = await conn.fetchrow(
        "INSERT INTO public.hair_intakes (user_id, quiz_version, answers) "
        "VALUES ($1, $2, $3::jsonb) RETURNING id",
        user_id,
        quiz_version,
        profile.model_dump_json(),
    )
    return str(row["id"])


async def get_latest_hair_profile(
    conn: asyncpg.Connection,
    user_id: str,
) -> HairProfile | None:
    row = await conn.fetchrow(
        "SELECT answers FROM public.hair_intakes "
        "WHERE user_id = $1 ORDER BY created_at DESC LIMIT 1",
        user_id,
    )
    if not row:
        return None
    return HairProfile.model_validate_json(row["answers"])
