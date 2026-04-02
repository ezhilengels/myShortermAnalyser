"""
news_fetcher.py — Fetch geopolitical and market news via NewsAPI.
Used for Check 15 (Geopolitical Trigger) feeding into Groq AI.
"""

import logging
import requests
from datetime import datetime, timedelta
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET

from config import NEWS_API_KEY, STOCK_NAMES
from data.cache.redis_cache import cache_get, cache_set

logger = logging.getLogger(__name__)

NEWS_API_URL = "https://newsapi.org/v2/everything"
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"

GEOPOLITICAL_QUERIES = [
    "India stock market",
    "FII investment India",
    "Iran war oil price",
    "US tariffs India",
    "RBI interest rate",
    "India budget economy",
]


def fetch_market_news(query: str = "India stock market NSE", max_articles: int = 5) -> list[dict]:
    """
    Fetch recent news articles matching the query.
    Returns list of {title, description, published_at, url} dicts.
    """
    key = f"news_{query[:30]}"
    cached = cache_get(key)
    if cached:
        return cached

    if not NEWS_API_KEY:
        logger.warning("NEWS_API_KEY not set — skipping news fetch")
        return []

    from_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")

    params = {
        "q":        query,
        "from":     from_date,
        "sortBy":   "publishedAt",
        "pageSize": max_articles,
        "language": "en",
        "apiKey":   NEWS_API_KEY,
    }
    try:
        resp = requests.get(NEWS_API_URL, params=params, timeout=10)
        resp.raise_for_status()
        articles = resp.json().get("articles", [])
        result = [
            {
                "title":        a.get("title", ""),
                "description":  a.get("description", ""),
                "published_at": a.get("publishedAt", ""),
                "url":          a.get("url", ""),
            }
            for a in articles
        ]
        cache_set(key, result, 1800)  # 30 min cache
        return result
    except Exception as e:
        logger.error(f"NewsAPI fetch failed: {e}")
        return []


def _dedupe_articles(articles: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for article in articles:
        key = (
            str(article.get("title") or "").strip().lower(),
            str(article.get("url") or "").strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(article)
    return deduped


def fetch_google_news_rss(query: str, max_articles: int = 5) -> list[dict]:
    """
    Fetch simple Google News RSS results as a fallback when NewsAPI is sparse.
    """
    key = f"gnrss_{query[:40]}"
    cached = cache_get(key)
    if cached:
        return cached

    url = GOOGLE_NEWS_RSS_URL.format(query=quote_plus(query))
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        items = []
        for item in root.findall(".//item")[:max_articles]:
            items.append(
                {
                    "title": item.findtext("title", default=""),
                    "description": item.findtext("description", default=""),
                    "published_at": item.findtext("pubDate", default=""),
                    "url": item.findtext("link", default=""),
                }
            )
        cache_set(key, items, 1800)
        return items
    except Exception as e:
        logger.error(f"Google News RSS fetch failed for '{query}': {e}")
        return []


def fetch_stock_news(stock_symbol: str, max_articles: int = 8) -> list[dict]:
    """
    Fetch stock-specific headlines using multiple NewsAPI queries plus RSS fallback.
    Returns deduped articles ordered by discovery.
    """
    key = f"stock_news_{stock_symbol}_{max_articles}"
    cached = cache_get(key)
    if cached:
        return cached

    company_name = STOCK_NAMES.get(stock_symbol, stock_symbol.replace(".NS", "").replace(".BO", ""))
    raw_symbol = stock_symbol.replace(".NS", "").replace(".BO", "")
    tokens = [token for token in company_name.replace("&", " ").replace("-", " ").split() if len(token) > 2]
    queries = [
        f'"{company_name}" stock India NSE',
        f'"{company_name}" share price India',
        f'"{raw_symbol}" NSE stock',
        f'"{company_name}" results India',
    ]

    collected: list[dict] = []
    for query in queries[:2]:
        collected.extend(fetch_market_news(query, max_articles=max_articles))
        if len(_dedupe_articles(collected)) >= max_articles:
            break

    if len(_dedupe_articles(collected)) < max(3, max_articles // 2):
        for query in queries:
            collected.extend(fetch_google_news_rss(query, max_articles=max_articles))
            if len(_dedupe_articles(collected)) >= max_articles:
                break

    filtered = []
    for article in _dedupe_articles(collected):
        blob = f"{article.get('title', '')} {article.get('description', '')}".lower()
        if raw_symbol.lower() in blob or company_name.lower() in blob or any(token.lower() in blob for token in tokens):
            filtered.append(article)

    deduped = (filtered or _dedupe_articles(collected))[:max_articles]
    cache_set(key, deduped, 1800)
    return deduped


def fetch_geopolitical_news_summary() -> str:
    """
    Fetch and concatenate recent geopolitical headlines for Groq AI context.
    Returns a plain-text summary string.
    """
    articles = fetch_market_news("India market NSE FII geopolitical", max_articles=5)
    if not articles:
        return "No recent geopolitical news available."

    headlines = [f"- {a['title']}" for a in articles if a.get("title")]
    return "Recent market headlines:\n" + "\n".join(headlines[:5])
