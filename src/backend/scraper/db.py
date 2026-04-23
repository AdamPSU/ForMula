import os
from contextlib import asynccontextmanager

import asyncpg

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        dsn = os.environ["DATABASE_URL"]
        _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=10)
    return _pool


@asynccontextmanager
async def connection():
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


async def close():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
