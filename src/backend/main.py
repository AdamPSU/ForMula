from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Single source of truth: repo-root .env.local. parents[2] is the repo root
# from src/backend/main.py. Loaded before any module reads os.environ.
load_dotenv(Path(__file__).resolve().parents[2] / ".env.local")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "ok"}
