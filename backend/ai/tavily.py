"""Tavily search/extract helpers for the hair-product pipeline."""

from __future__ import annotations

TAVILY_EXCLUDED_DOMAINS: list[str] = [
    # --- Social media / UGC (no structured product data) ---
    "tiktok.com",
    "instagram.com",
    "facebook.com",
    "x.com",
    "twitter.com",
    "pinterest.com",
    "threads.net",
    "linkedin.com",
    "tumblr.com",
    "snapchat.com",

    # --- Video / streaming (no extractable text) ---
    "youtube.com",
    "vimeo.com",
    "twitch.tv",
    "dailymotion.com",

    # --- Forums / Q&A (unstructured opinion, no price/ingredients) ---
    "reddit.com",
    "quora.com",
    "stackexchange.com",
    "answers.com",
    "makeupalley.com",

    # --- Review aggregators (thin, often anti-scrape) ---
    "yelp.com",
    "trustpilot.com",
    "sitejabber.com",

    # --- Editorial magazines (list products, omit ingredients/price) ---
    "cosmopolitan.com",
    "elle.com",
    "vogue.com",
    "allure.com",
    "byrdie.com",
    "harpersbazaar.com",
    "glamour.com",
    "marieclaire.com",
    "refinery29.com",
    "buzzfeed.com",

    # --- Blogging platforms (unstructured, low authority) ---
    "medium.com",
    "substack.com",
    "wordpress.com",
    "blogspot.com",

    # --- Low-quality aggregators / how-to mills ---
    "wikihow.com",
    "ehow.com",
    "ebay.com",
    "etsy.com",
]
