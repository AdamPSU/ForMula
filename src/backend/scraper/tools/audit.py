"""Catalog audits — non-destructive checks on the brands table.

Currently exposes one verb:

  audit-website-urls [--apply]
    HEAD-probes every active brand's `website_url`, follows redirects,
    and reports any brand whose canonical apex differs from what we
    have on file. With `--apply`, writes the canonical URL back.

Cheap (curl HEAD only, no Firecrawl credits). Run before a discovery
sweep so `discover-and-stage` doesn't burn cycles on stale www-prefix
URLs that 301 to the apex.
"""

import asyncio
import re
from urllib.parse import urlparse, urlunparse

from ..db import connection


_HEAD_CONCURRENCY = 20
_HEAD_TIMEOUT = 10  # seconds

# Multi-part public suffixes we routinely encounter — needed to compute
# eTLD+1 correctly so `shop.example.co.uk` and `www.example.co.uk`
# count as the same brand domain.
_MULTI_PART_TLDS = {
    "co.jp", "co.kr", "co.uk", "co.in", "co.nz", "co.za",
    "com.au", "com.br", "com.cn", "com.hk", "com.mx", "com.sg", "com.tw",
}


async def _head_final_url(url: str) -> tuple[str | None, str]:
    """Run `curl -sIL --max-time N` and return (final_url, error). On
    success final_url is the post-redirect URL string; on failure
    final_url is None and error is a short reason."""
    proc = await asyncio.create_subprocess_exec(
        "/usr/bin/curl",
        "-sIL",
        "--max-time", str(_HEAD_TIMEOUT),
        "-A", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "-w", "%{url_effective}\n",
        "-o", "/dev/null",
        url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=_HEAD_TIMEOUT + 2)
    except asyncio.TimeoutError:
        proc.kill()
        return None, "timeout"
    if proc.returncode != 0:
        return None, f"curl exit {proc.returncode}"
    final = stdout.decode().strip().splitlines()[-1] if stdout else ""
    if not final:
        return None, "empty url_effective"
    return final, ""


def _canonicalize(url: str) -> str:
    """Strip trailing slash, collapse to scheme://host[/path] for stable
    diff. Doesn't touch query/fragment — they're rare on apex URLs and
    a real difference there matters."""
    p = urlparse(url)
    path = re.sub(r"/+$", "", p.path)
    return urlunparse(p._replace(path=path))


def _etld1(url: str) -> str:
    """Best-effort eTLD+1 (e.g. `www.example.com` → `example.com`,
    `shop.example.co.uk` → `example.co.uk`). Used to classify a
    redirect as same-brand vs cross-domain."""
    netloc = urlparse(url).netloc.lower()
    netloc = re.sub(r"^www\.", "", netloc)
    parts = netloc.split(".")
    if len(parts) < 2:
        return netloc
    last2 = ".".join(parts[-2:])
    if last2 in _MULTI_PART_TLDS and len(parts) >= 3:
        return ".".join(parts[-3:])
    return last2


def _classify_redirect(from_url: str, to_url: str) -> str:
    """`safe` = same brand domain (www → apex, locale path, subdomain).
    `password` = Shopify/etc. coming-soon lockout.
    `cross_domain` = different eTLD+1 (rebrand, acquisition, broken).
    """
    if "/password" in to_url or "/expire" in to_url:
        return "password"
    if _etld1(from_url) == _etld1(to_url):
        return "safe"
    return "cross_domain"


async def _check_brand(sem: asyncio.Semaphore, row: dict) -> dict:
    async with sem:
        final, err = await _head_final_url(row["website_url"])
    if final is None:
        return {
            "id": row["id"], "slug": row["slug"],
            "from": row["website_url"], "to": None,
            "status": "error", "error": err,
        }
    if _canonicalize(row["website_url"]) == _canonicalize(final):
        return {
            "id": row["id"], "slug": row["slug"],
            "from": row["website_url"], "to": final,
            "status": "ok",
        }
    return {
        "id": row["id"], "slug": row["slug"],
        "from": row["website_url"], "to": final,
        "status": "redirected",
        "redirect_class": _classify_redirect(row["website_url"], final),
    }


async def audit_website_urls(apply: bool = False) -> dict:
    """Probe every active brand's website_url. Default is dry-run.

    Redirects are partitioned into three classes:

      - `safe`         — same eTLD+1 (www→apex, locale path,
                         subdomain). Auto-apply on `--apply`.
      - `cross_domain` — different eTLD+1 (rebrand, acquisition,
                         broken). Surfaced for human review; never
                         auto-applied.
      - `password`     — `/password` lockout, `/expire` notice, or
                         similar maintenance/discontinuation pages.
                         Surfaced for review; never auto-applied.

    Hard errors (DNS failure, connection refused, timeout) are surfaced
    in `error_samples`; they often correlate with brands that should
    be parked anyway.
    """
    async with connection() as conn:
        rows = await conn.fetch(
            "select id::text as id, slug, website_url from brands where active order by slug"
        )

    sem = asyncio.Semaphore(_HEAD_CONCURRENCY)
    results = await asyncio.gather(*[_check_brand(sem, dict(r)) for r in rows])

    ok = [r for r in results if r["status"] == "ok"]
    redirected = [r for r in results if r["status"] == "redirected"]
    errors = [r for r in results if r["status"] == "error"]

    safe = [r for r in redirected if r["redirect_class"] == "safe"]
    cross = [r for r in redirected if r["redirect_class"] == "cross_domain"]
    password = [r for r in redirected if r["redirect_class"] == "password"]

    applied = 0
    if apply and safe:
        async with connection() as conn:
            for r in safe:
                await conn.execute(
                    "update brands set website_url = $1 where id = $2::uuid",
                    r["to"],
                    r["id"],
                )
                applied += 1

    return {
        "checked": len(results),
        "ok": len(ok),
        "safe_redirects": len(safe),
        "cross_domain_redirects": len(cross),
        "password_or_expired": len(password),
        "errors": len(errors),
        "applied": applied,
        "safe": [{"slug": r["slug"], "from": r["from"], "to": r["to"]} for r in safe],
        "cross_domain": [
            {"slug": r["slug"], "from": r["from"], "to": r["to"]} for r in cross
        ],
        "password": [
            {"slug": r["slug"], "from": r["from"], "to": r["to"]} for r in password
        ],
        "error_samples": [
            {"slug": r["slug"], "from": r["from"], "error": r["error"]}
            for r in errors[:10]
        ],
    }
