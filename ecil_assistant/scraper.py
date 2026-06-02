"""ECIL website crawler.

Refreshes data/knowledge_base.json with content scraped from ecil.co.in.
The crawler is **additive only** - it never deletes the hand-curated
entries that ship with the project. New pages discovered from the seed
URLs are appended; existing source_urls are skipped.

Usage:
    python scraper.py                 # crawl with defaults from config
    python scraper.py --max-pages 200 # widen the crawl
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from collections import deque
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

import config


DATA_DIR = config.DATA_FOLDER
KB_PATH = config.KNOWLEDGE_BASE_PATH
FAQ_PATH = config.FAQ_BASE_PATH
SITEMAP_URL = f"{config.SITE_ROOT.rstrip('/')}/sitemap.xml"

# Minimal fallback seed URLs. When the live sitemap is available, the crawler
# will use it instead and avoid outdated hard-coded paths.
SEED_URLS: List[str] = [
    "https://www.ecil.co.in/",
    "https://www.ecil.co.in/sitemap",
    "https://www.ecil.co.in/about",
    "https://www.ecil.co.in/tenders",
    "https://www.ecil.co.in/quality",
    "https://www.ecil.co.in/awards",
    "https://www.ecil.co.in/rnd",
    "https://www.ecil.co.in/nuclear",
    "https://www.ecil.co.in/defence",
    "https://www.ecil.co.in/aerospace",
    "https://www.ecil.co.in/hss",
    "https://www.ecil.co.in/iteg",
    "https://www.ecil.co.in/manfgunits",
    "https://www.ecil.co.in/verticals",
    "https://www.ecil.co.in/jointventures",
    "https://www.ecil.co.in/org_setup",
]


# ---------------------------------------------------------------------------
# IO helpers
# ---------------------------------------------------------------------------

def load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[–—]", " - ", text)
    return text


def _parse_sitemap(xml: str) -> List[str]:
    root = ET.fromstring(xml)
    urls: List[str] = []
    for loc in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
        candidate = clean_text(loc.text or "")
        normalized = normalize_url(config.SITE_ROOT, candidate)
        if normalized:
            urls.append(normalized)
    return urls


def load_sitemap_urls() -> List[str]:
    try:
        resp = requests.get(SITEMAP_URL, timeout=config.REQUEST_TIMEOUT,
                            headers={"User-Agent": config.USER_AGENT})
        resp.raise_for_status()
        urls = _parse_sitemap(resp.text)
        if urls:
            print(f"[scraper] loaded {len(urls)} sitemap URLs from {SITEMAP_URL}")
            return urls
    except requests.RequestException as exc:
        print(f"[scraper] sitemap load failed: {exc}")
    return []


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def normalize_url(base: str, link: str) -> Optional[str]:
    if not link:
        return None
    link = link.strip()
    if link.startswith("javascript:") or link.startswith("mailto:") or link.startswith("tel:"):
        return None
    if any(pat in link.lower() for pat in config.URL_IGNORE_PATTERNS):
        return None

    site_host = urlparse(config.SITE_ROOT).netloc
    parsed = urlparse(link)
    if parsed.scheme and parsed.netloc:
        if parsed.netloc.lower() != site_host:
            return None
        absolute = link
    else:
        absolute = urljoin(base, link.split("#")[0])

    parsed2 = urlparse(absolute)
    if parsed2.netloc.lower() != site_host:
        return None
    normalized = urlunparse(parsed2._replace(scheme="https", fragment=""))
    return normalized.rstrip("/")


# ---------------------------------------------------------------------------
# Content extraction
# ---------------------------------------------------------------------------

def _strip_non_content(soup: BeautifulSoup) -> None:
    for selector in ("script", "style", "header", "footer", "nav",
                     "aside", "noscript", "form", "iframe"):
        for el in soup.select(selector):
            el.decompose()
    for el in soup.select(
        "[class*=menu], [class*=nav], [class*=footer], [class*=header],"
        " [class*=breadcrumb], [id*=menu], [id*=nav]"
    ):
        el.decompose()


def _table_text(table) -> str:
    rows: List[str] = []
    for row in table.find_all("tr"):
        cells = [clean_text(c.get_text(" ", strip=True))
                 for c in row.find_all(["th", "td"])]
        cells = [c for c in cells if c]
        if cells:
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def extract_page(html: str, url: str) -> Optional[Dict]:
    soup = BeautifulSoup(html, "html.parser")
    _strip_non_content(soup)

    title = clean_text(soup.title.string if soup.title else "")
    if not title:
        heading = soup.find(re.compile(r"h[1-4]"))
        title = clean_text(heading.get_text(" ")) if heading else url

    fragments: List[str] = []
    headings: List[str] = []
    keywords: Set[str] = set()

    for heading in soup.find_all(re.compile(r"h[1-4]")):
        t = clean_text(heading.get_text(" "))
        if t:
            headings.append(t)
            keywords.update(t.lower().split())

    for p in soup.find_all("p"):
        t = clean_text(p.get_text(" "))
        if len(t) > 30:
            fragments.append(t)
            keywords.update(t.lower().split())

    for lst in soup.find_all(["ul", "ol"]):
        items = [clean_text(li.get_text(" ")) for li in lst.find_all("li")]
        items = [i for i in items if i]
        if items:
            joined = "; ".join(items)
            fragments.append(joined)
            keywords.update(joined.lower().split())

    for table in soup.find_all("table"):
        t = _table_text(table)
        if t:
            fragments.append(t)
            keywords.update(t.lower().split())

    content = clean_text("\n\n".join(fragments))
    if len(content) < 80:
        # Fallback: take the visible text but cap it.
        content = clean_text(soup.get_text(" "))[:4000]

    if len(content) < 80:
        return None

    # Pick a category from the URL path.
    path_segments = [seg for seg in urlparse(url).path.strip("/").split("/") if seg]
    category = "Imported"
    for seg in reversed(path_segments):
        if seg in config.CATEGORY_MAP:
            category = config.CATEGORY_MAP[seg]
            break
    else:
        if path_segments:
            category = path_segments[0].replace("-", " ").title()

    summary = content[:360] + ("..." if len(content) > 360 else "")
    kw_list = sorted({w for w in keywords if len(w) > 3})[:40]
    tag_list = sorted({h for h in headings if len(h) > 2})[:20]

    return {
        "title": title,
        "category": category,
        "keywords": kw_list,
        "tags": tag_list,
        "source_url": url.rstrip("/"),
        "content": content,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Crawler
# ---------------------------------------------------------------------------

def crawl(max_pages: int, polite_delay: float = 0.4, timeout: int = None, reset: bool = False) -> List[Dict]:
    timeout = timeout or config.REQUEST_TIMEOUT
    session = requests.Session()
    session.headers.update({"User-Agent": config.USER_AGENT})

    if reset and os.path.exists(KB_PATH):
        os.remove(KB_PATH)
        print(f"[scraper] reset: removed old knowledge base {KB_PATH}")

    existing = load_json(KB_PATH, [])
    existing_urls: Set[str] = {
        normalize_url(config.SITE_ROOT, (doc.get("source_url") or "")) or ""
        for doc in existing
    }

    seeds = load_sitemap_urls() or SEED_URLS
    queue = deque(seeds)
    visited: Set[str] = set()
    new_docs: List[Dict] = []

    while queue and len(visited) < max_pages:
        url = queue.popleft()
        if not url:
            continue
        url = url.rstrip("/")
        if url in visited:
            continue
        visited.add(url)

        try:
            resp = session.get(url, timeout=timeout)
        except requests.RequestException as exc:
            print(f"[scraper] skip {url}: {exc}")
            continue

        ct = resp.headers.get("Content-Type", "")
        if resp.status_code != 200 or "text/html" not in ct:
            continue

        # Enqueue outbound links before we decide whether to keep this page.
        soup_links = BeautifulSoup(resp.text, "html.parser")
        for a in soup_links.find_all("a", href=True):
            link = normalize_url(url, a["href"])
            if link and link not in visited and link not in queue:
                queue.append(link)

        if url in existing_urls:
            continue

        page = extract_page(resp.text, url)
        if not page:
            print(f"[scraper] empty {url}")
            continue

        next_id = len(existing) + len(new_docs) + 1
        page["id"] = f"doc-crawl-{next_id}"
        new_docs.append(page)
        existing_urls.add(url)
        print(f"[scraper] +{page['title']!r}  ({url})")
        time.sleep(polite_delay)

    if new_docs:
        save_json(KB_PATH, existing + new_docs)
        print(f"[scraper] added {len(new_docs)} new docs to {KB_PATH} "
              f"(total: {len(existing) + len(new_docs)})")
    else:
        print("[scraper] no new docs to add")
    return existing + new_docs


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-pages", type=int, default=config.MAX_CRAWL_PAGES)
    parser.add_argument("--delay", type=float, default=0.4,
                        help="Polite delay between fetches (seconds).")
    parser.add_argument("--reset", action="store_true",
                        help="Reset the knowledge base and rebuild from the live sitemap.")
    args = parser.parse_args(argv)
    crawl(max_pages=args.max_pages, polite_delay=args.delay, reset=args.reset)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
