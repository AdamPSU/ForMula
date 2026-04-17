"""Fetch front-facing portrait candidates for a curl subtype from Unsplash.

Usage (from backend/): uv run python ../frontend/public/curl-types/fetch_candidates.py <subtype> <query1> [<query2> ...]
Each query is augmented with 'front facing portrait' to bias composition.
Writes candidates/<subtype>/0.jpg..7.jpg + manifest.json.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE.parent.parent.parent / "backend" / ".env")

KEY = os.environ["UNSPLASH_ACCESS_KEY"]
AUTH = {"Authorization": f"Client-ID {KEY}"}


def search(q: str, per_page: int = 10) -> list[dict]:
    r = requests.get(
        "https://api.unsplash.com/search/photos",
        params={
            "query": q,
            "per_page": per_page,
            "orientation": "portrait",
            "content_filter": "high",
        },
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
    subtype = sys.argv[1]
    base_queries = sys.argv[2:]
    queries = [f"front facing portrait {q}" for q in base_queries] + list(base_queries)

    out = HERE / "candidates" / subtype
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    all_results: list[dict] = []
    seen: set[str] = set()
    for q in queries:
        try:
            res = search(q)
        except Exception as e:
            print(f"[{subtype}] {q!r} failed: {e}", file=sys.stderr)
            continue
        for r in res:
            if r["id"] not in seen:
                seen.add(r["id"])
                r["_query"] = q
                all_results.append(r)
        time.sleep(0.4)

    manifest: list[dict] = []
    for i, p in enumerate(all_results[:8]):
        dest = out / f"{i}.jpg"
        try:
            download(p["urls"]["regular"], dest)
        except Exception as e:
            print(f"  #{i} download failed: {e}", file=sys.stderr)
            continue
        manifest.append({
            "idx": i,
            "query": p["_query"],
            "alt": p.get("alt_description") or p.get("description") or "",
            "page": p["links"]["html"],
            "author": p["user"]["name"],
            "regular_url": p["urls"]["regular"],
        })
        print(f"  #{i} {dest.stat().st_size // 1024}KB  {(p.get('alt_description') or '')[:70]}")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
