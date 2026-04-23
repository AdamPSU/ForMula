"""Firecrawl budget: live credit usage via the Firecrawl API."""

from .pipeline import _client


async def check_budget() -> dict:
    fc = _client()
    usage = await fc.get_credit_usage()
    return {
        "remaining_credits": usage.remaining_credits,
        "plan_credits": usage.plan_credits,
        "billing_period_start": usage.billing_period_start,
        "billing_period_end": usage.billing_period_end,
    }
