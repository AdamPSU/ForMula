import os
from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Single source of truth: repo-root .env.local. parents[2] is the repo root
# from src/backend/main.py. Loaded before any module reads os.environ.
load_dotenv(Path(__file__).resolve().parents[2] / ".env.local")

from ai.chat import router as chat_router  # noqa: E402
from ai.rerank.api import router as recommend_router  # noqa: E402
from profiles.api import router as profiles_router  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await asyncpg.create_pool(
        os.environ["DATABASE_URL"], min_size=1, max_size=10
    )
    try:
        yield
    finally:
        await app.state.pool.close()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profiles_router)
app.include_router(recommend_router)
app.include_router(chat_router)


@app.get("/")
def root():
    return {"status": "ok"}
