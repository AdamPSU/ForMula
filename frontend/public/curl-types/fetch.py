"""Download curl-type reference photos from Unsplash.

Usage: cd backend && uv run python ../frontend/public/curl-types/fetch.py
Requires UNSPLASH_ACCESS_KEY in backend/.env. Writes 1a.jpg..4c.jpg + SOURCES.md.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE.parent.parent.parent / "backend" / ".env")
KEY = os.environ["UNSPLASH_ACCESS_KEY"]
AUTH = {"Authorization": f"Client-ID {KEY}"}

# Per-subtype search queries. Tuned for Unsplash's tag/description index.
QUERIES: dict[str, str] = {
    "1a": "straight fine hair portrait",
    "1b": "straight medium hair portrait",
    "1c": "straight thick hair portrait",
    "2a": "loose wavy hair portrait",
    "2b": "wavy hair portrait",
    "2c": "defined wavy hair portrait",
    "3a": "loose curly hair portrait",
    "3b": "curly hair ringlets portrait",
    "3c": "tight curly hair portrait",
    "4a": "coily hair woman",
    "4b": "4b natural hair",
    "4c": "4c natural hair afro",
}


def search(q: str, per_page: int = 6) -> list[dict]:
    r = requests.get(
        "https://api.unsplash.com/search/photos",
        params={"query": q, "per_page": per_page, "orientation": "portrait"},
        headers=AUTH,
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("results", [])


def download(url: str, dest: Path) -> int:
    r = requests.get(url, timeout=60, stream=True)
    r.raise_for_status()
    with dest.open("wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
    return dest.stat().st_size


def main() -> int:
    lines = [
        "# Curl-type reference photos",
        "",
        "Source: Unsplash (free for commercial use, no attribution required — but we credit anyway).",
        "Review each and swap any that don't cleanly show the intended subtype.",
        "",
    ]
    for subtype, q in QUERIES.items():
        try:
            results = search(q)
        except Exception as e:
            print(f"[{subtype}] search failed: {e}", file=sys.stderr)
            continue
        if not results:
            print(f"[{subtype}] no results for {q!r}", file=sys.stderr)
            continue
        picked = results[0]
        img_url = picked["urls"]["regular"]
        page = picked["links"]["html"]
        author = picked["user"]["name"]
        alt = picked.get("alt_description") or picked.get("description") or "untitled"
        dest = HERE / f"{subtype}.jpg"
        try:
            size = download(img_url, dest)
        except Exception as e:
            print(f"[{subtype}] download failed: {e}", file=sys.stderr)
            continue
        print(f"[{subtype}] {size // 1024}KB  {alt[:60]}")
        lines.append(f"- **{subtype.upper()}** — [{alt}]({page}) by {author}")
        time.sleep(0.5)  # stay polite under rate limits
    (HERE / "SOURCES.md").write_text("\n".join(lines) + "\n")
    print("SOURCES.md written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
