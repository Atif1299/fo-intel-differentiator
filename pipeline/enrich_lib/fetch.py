"""Fetch Class C page text for FO proof."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

UA = "FO-Intel-Differentiator/0.2 (assessment; ranaatif1299@gmail.com)"


def _clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:12000]


def _looks_like_homepage(url: str) -> bool:
    try:
        p = urlparse(url)
        if p.scheme not in {"http", "https"}:
            return False
        path = (p.path or "/").rstrip("/")
        return path in {"", "/"} or path.count("/") <= 1
    except Exception:
        return False


def resolve_website_ddg(name: str) -> tuple[str | None, dict[str, Any]]:
    """Best-effort official site via DuckDuckGo."""
    meta: dict[str, Any] = {"method": "ddg_site_resolve", "query": f'{name} family office official site'}
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(meta["query"], max_results=5))
    except Exception as exc:  # noqa: BLE001
        meta["error"] = str(exc)
        return None, meta
    for row in results:
        href = row.get("href") or row.get("link") or row.get("url") or ""
        if not href:
            continue
        host = urlparse(href).netloc.lower()
        if any(x in host for x in ("linkedin.com", "wikipedia.org", "facebook.com", "twitter.com", "youtube.com", "sec.gov")):
            continue
        meta["picked"] = href
        meta["title"] = row.get("title")
        return href, meta
    return None, meta


def fetch_url(url: str, timeout: float = 25.0) -> tuple[str | None, dict[str, Any]]:
    meta: dict[str, Any] = {"url": url}
    try:
        with httpx.Client(timeout=timeout, headers={"User-Agent": UA}, follow_redirects=True) as client:
            r = client.get(url)
            meta["status_code"] = r.status_code
            if r.status_code >= 400:
                meta["error"] = f"http_{r.status_code}"
                return None, meta
            text = _clean_text(r.text)
            meta["chars"] = len(text)
            return text, meta
    except Exception as exc:  # noqa: BLE001
        meta["error"] = str(exc)
        return None, meta


def collect_proof_corpus(candidate: dict[str, Any], website: str | None) -> tuple[str, list[str], list[dict[str, Any]]]:
    """Fetch website + discovery URLs; return concatenated text, urls used, fetch logs."""
    urls: list[str] = []
    if website:
        urls.append(website)
        # try /about
        try:
            about = urljoin(website if website.endswith("/") else website + "/", "about")
            urls.append(about)
        except Exception:
            pass
    for u in candidate.get("discovery_urls") or []:
        if u and u not in urls:
            urls.append(u)
    urls = urls[:4]

    chunks: list[str] = []
    logs: list[dict[str, Any]] = []
    used: list[str] = []
    for u in urls:
        text, meta = fetch_url(u)
        logs.append(meta)
        if text:
            chunks.append(f"URL: {u}\n{text}")
            used.append(u)
    corpus = "\n\n----\n\n".join(chunks)[:20000]
    return corpus, used, logs
