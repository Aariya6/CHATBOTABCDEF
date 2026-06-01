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
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import config


DATA_DIR = config.DATA_FOLDER
KB_PATH = config.KNOWLEDGE_BASE_PATH
FAQ_PATH = config.FAQ_BASE_PATH

# Seed URLs: structured to cover the main sections of www.ecil.co.in even
# when the home page's nav uses JavaScript (which `requests` cannot run).
# ENHANCED: Now includes additional pages for news, awards, research, training,
# quality certifications, sustainability, and detailed technical content.
SEED_URLS: List[str] = [
    "https://www.ecil.co.in/",
    "https://www.ecil.co.in/about-us",
    "https://www.ecil.co.in/about-us/history",
    "https://www.ecil.co.in/about-us/leadership",
    "https://www.ecil.co.in/about-us/vision-mission",
    "https://www.ecil.co.in/divisions",
    "https://www.ecil.co.in/divisions/defense",
    "https://www.ecil.co.in/divisions/nuclear",
    "https://www.ecil.co.in/divisions/communications",
    "https://www.ecil.co.in/divisions/customer-support",
    "https://www.ecil.co.in/divisions/components",
    "https://www.ecil.co.in/divisions/telecom",
    "https://www.ecil.co.in/products",
    "https://www.ecil.co.in/products/evm",
    "https://www.ecil.co.in/products/antenna",
    "https://www.ecil.co.in/products/satcom",
    "https://www.ecil.co.in/products/security",
    "https://www.ecil.co.in/products/smartcard",
    "https://www.ecil.co.in/products/smartmeter",
    "https://www.ecil.co.in/products/railway",
    "https://www.ecil.co.in/products/automation",
    "https://www.ecil.co.in/products/solar",
    "https://www.ecil.co.in/products/servo",
    "https://www.ecil.co.in/products/computers",
    "https://www.ecil.co.in/products/instruments",
    "https://www.ecil.co.in/services",
    "https://www.ecil.co.in/careers",
    "https://www.ecil.co.in/tenders",
    "https://www.ecil.co.in/rti",
    "https://www.ecil.co.in/vigilance",
    "https://www.ecil.co.in/csr",
    "https://www.ecil.co.in/contact-us",
    "https://www.ecil.co.in/sitemap",
    # ENHANCED SEED URLS: Additional sections for deeper content coverage
    "https://www.ecil.co.in/news",
    "https://www.ecil.co.in/press",
    "https://www.ecil.co.in/media",
    "https://www.ecil.co.in/awards",
    "https://www.ecil.co.in/achievements",
    "https://www.ecil.co.in/research",
    "https://www.ecil.co.in/innovation",
    "https://www.ecil.co.in/training",
    "https://www.ecil.co.in/quality",
    "https://www.ecil.co.in/certifications",
    "https://www.ecil.co.in/iso",
    "https://www.ecil.co.in/sustainability",
    "https://www.ecil.co.in/environment",
    "https://www.ecil.co.in/policies",
    "https://www.ecil.co.in/procurement",
    "https://www.ecil.co.in/suppliers",
    "https://www.ecil.co.in/clients",
    "https://www.ecil.co.in/case-studies",
    "https://www.ecil.co.in/projects",
    "https://www.ecil.co.in/portfolio",
    "https://www.ecil.co.in/technical",
    "https://www.ecil.co.in/documentation",
    "https://www.ecil.co.in/downloads",
    "https://www.ecil.co.in/specifications",
    "https://www.ecil.co.in/datasheet",
    "https://www.ecil.co.in/brochure",
    "https://www.ecil.co.in/annual-report",
    "https://www.ecil.co.in/financial",
    "https://www.ecil.co.in/annual-reports",
    "https://www.ecil.co.in/hr",
    "https://www.ecil.co.in/recruitment",
    "https://www.ecil.co.in/freshers",
    "https://www.ecil.co.in/internship",
    "https://www.ecil.co.in/job-vacancies",
    "https://www.ecil.co.in/grievance",
    "https://www.ecil.co.in/faq",
    "https://www.ecil.co.in/faqs",
    "https://www.ecil.co.in/help",
    "https://www.ecil.co.in/support",
    "https://www.ecil.co.in/customer-care",
    "https://www.ecil.co.in/service-centers",
    "https://www.ecil.co.in/dealers",
    "https://www.ecil.co.in/distributors",
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
    parsed = urlparse(link)
    site_host = urlparse(config.SITE_ROOT).netloc
    if parsed.scheme and parsed.netloc and parsed.netloc != site_host:
        return None
    absolute = urljoin(base, link.split("#")[0]).rstrip("/")
    return absolute or None


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

def crawl(max_pages: int, polite_delay: float = 0.4, timeout: int = None) -> List[Dict]:
    timeout = timeout or config.REQUEST_TIMEOUT
    session = requests.Session()
    session.headers.update({"User-Agent": config.USER_AGENT})

    existing = load_json(KB_PATH, [])
    existing_urls: Set[str] = {
        (doc.get("source_url") or "").rstrip("/") for doc in existing
    }

    queue = deque(SEED_URLS)
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
    args = parser.parse_args(argv)
    crawl(max_pages=args.max_pages, polite_delay=args.delay)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
