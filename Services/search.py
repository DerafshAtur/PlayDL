import asyncio
import logging

from google_play_scraper import search as gp_search

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 8
DEFAULT_LANG = "en"
DEFAULT_COUNTRY = "us"


class SearchError(RuntimeError):
    pass


def _sync_search(query: str, lang: str, country: str, n_hits: int) -> list[dict]:
    return gp_search(query, lang=lang, country=country, n_hits=n_hits) or []


async def search_apps(
    query: str,
    limit: int = DEFAULT_LIMIT,
    lang: str = DEFAULT_LANG,
    country: str = DEFAULT_COUNTRY,
) -> list[dict]:
    query = (query or "").strip()
    if not query:
        raise SearchError("کوئری جستجو خالی است.")

    try:
        results = await asyncio.to_thread(_sync_search, query, lang, country, max(limit, 1))
    except Exception as exc:
        logger.exception("google play search failed: %s", query)
        raise SearchError(f"جستجو ناموفق بود: {exc}") from exc

    cleaned: list[dict] = []
    for item in results[:limit]:
        package = item.get("appId")
        title = item.get("title")
        if not package or not title:
            continue
        cleaned.append(
            {
                "package": package,
                "title": title,
                "developer": item.get("developer") or "",
                "score": item.get("score"),
                "free": bool(item.get("free", True)),
            }
        )
    return cleaned


def build_play_url(package: str) -> str:
    return f"https://play.google.com/store/apps/details?id={package}"
