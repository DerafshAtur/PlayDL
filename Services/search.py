import asyncio
import logging
import re

from google_play_scraper import app as gp_app
from google_play_scraper import search as gp_search

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 10
FETCH_HITS = 30
SEARCH_LOCALES: tuple[tuple[str, str], ...] = (
    ("en", "us"),
    ("fa", "ir"),
)
_PACKAGE_RE = re.compile(r"^[a-zA-Z][\w]*(\.[a-zA-Z][\w]*)+$")


class SearchError(RuntimeError):
    pass


def _sync_search(query: str, lang: str, country: str, n_hits: int) -> list[dict]:
    return gp_search(query, lang=lang, country=country, n_hits=n_hits) or []


def _sync_app(package: str, lang: str, country: str) -> dict:
    return gp_app(package, lang=lang, country=country) or {}


def _normalize(item: dict) -> dict | None:
    package = item.get("appId") or item.get("package")
    title = item.get("title")
    if not package or not title:
        return None
    return {
        "package": package,
        "title": title,
        "developer": item.get("developer") or "",
        "score": item.get("score"),
        "free": bool(item.get("free", True)),
    }


async def search_apps(
    query: str,
    limit: int = DEFAULT_LIMIT,
) -> list[dict]:
    query = (query or "").strip()
    if not query:
        raise SearchError("کوئری جستجو خالی است.")

    seen: dict[str, dict] = {}

    if _PACKAGE_RE.match(query):
        for lang, country in SEARCH_LOCALES:
            try:
                info = await asyncio.to_thread(_sync_app, query, lang, country)
            except Exception:
                continue
            entry = _normalize({**info, "appId": info.get("appId") or query})
            if entry:
                seen[entry["package"]] = entry
                break

    errors: list[Exception] = []
    for lang, country in SEARCH_LOCALES:
        try:
            results = await asyncio.to_thread(_sync_search, query, lang, country, FETCH_HITS)
        except Exception as exc:
            errors.append(exc)
            logger.warning("google play search failed lang=%s country=%s: %s", lang, country, exc)
            continue
        for item in results:
            entry = _normalize(item)
            if entry and entry["package"] not in seen:
                seen[entry["package"]] = entry

    if not seen and errors:
        raise SearchError(f"جستجو ناموفق بود: {errors[0]}")

    return list(seen.values())[:limit]


def build_play_url(package: str) -> str:
    return f"https://play.google.com/store/apps/details?id={package}"


async def fetch_app_title(package: str) -> str | None:
    package = (package or "").strip()
    if not package:
        return None
    for lang, country in SEARCH_LOCALES:
        try:
            info = await asyncio.to_thread(_sync_app, package, lang, country)
        except Exception as exc:
            logger.warning(
                "google play app() failed for %s lang=%s country=%s: %s",
                package,
                lang,
                country,
                exc,
            )
            continue
        title = info.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
    return None

