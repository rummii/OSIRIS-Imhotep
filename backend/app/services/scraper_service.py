# -*- coding: utf-8 -*-
from __future__ import annotations
import asyncio, logging, re, time
import httpx
from bs4 import BeautifulSoup
logger = logging.getLogger("osiris.scraper")

SCRAPE_SOURCES = {
    "dole_oshc": {
        "name": "DOLE / OSHC Advisories", "domain": "dole_oshc",
        "jurisdiction": "Philippines", "base_url": "https://www.oshc.dole.gov.ph",
        "list_url": "https://www.oshc.dole.gov.ph/advisories/",
        "list_selector": "article.post, .post-entry, .advisory-item",
        "link_selector": "a[href]", "title_selector": "h2, h3, .entry-title",
        "content_selector": ".entry-content, .post-content, .content",
        "domain_filter": "oshc.dole.gov.ph",
    },
    "philgeps": {
        "name": "PhilGEPS Notices", "domain": "philgeps",
        "jurisdiction": "Philippines", "base_url": "https://www.philgeps.gov.ph",
        "list_url": "https://www.philgeps.gov.ph/gle/gle.aspx",
        "list_selector": "tr, .notice-row",
        "link_selector": "a[href*='pid']",
        "title_selector": "td, .notice-title",
        "content_selector": ".notice-content, .detail-content",
        "domain_filter": "philgeps.gov.ph",
    },
    "dpwh": {
        "name": "DPWH Bulletins", "domain": "dpwh",
        "jurisdiction": "Philippines", "base_url": "https://www.dpwh.gov.ph",
        "list_url": "https://www.dpwh.gov.ph/dpwh/bulletin-board",
        "list_selector": "article, .bulletin-item, .news-item",
        "link_selector": "a[href]", "title_selector": "h3, h4, .title",
        "content_selector": ".content, .article-content, .entry-content",
        "domain_filter": "dpwh.gov.ph",
    },
}
class ScrapeResult:
    def __init__(self, source, domain="", jurisdiction="Philippines"):
        self.source = source; self.domain = domain; self.jurisdiction = jurisdiction
        self.chunks = []; self.errors = []; self.duration_seconds = 0.0
        self.pages_scraped = 0; self.items_found = 0
    def to_dict(self):
        return {"source": self.source, "domain": self.domain, "jurisdiction": self.jurisdiction,
                "chunk_count": len(self.chunks), "pages_scraped": self.pages_scraped,
                "items_found": self.items_found, "errors": self.errors,
                "duration_seconds": round(self.duration_seconds, 2)}

class ScraperService:
    def __init__(self, timeout=30.0, rate_limit=1.0, max_retries=3, user_agent="OSIRIS-Imhotep/1.0"):
        self._timeout = timeout; self._rate_limit = rate_limit; self._max_retries = max_retries
        self._user_agent = user_agent; self._last_request_time = {}
        self._enabled_sources = set(); self._custom_fetchers = {}; self._errors = []
    def enable_source(self, source): self._enabled_sources.add(source)
    def disable_source(self, source): self._enabled_sources.discard(source)
    def is_enabled(self, source): return source in self._enabled_sources
    def list_sources(self):
        return [{"source": k, "name": v["name"], "enabled": self.is_enabled(k),
                 "registered": k in self._custom_fetchers} for k, v in SCRAPE_SOURCES.items()]
    def scrape_url(self, url):
        import asyncio
        return asyncio.get_event_loop().run_until_complete(self._scrape_url_async(url))
    def scrape_source(self, source):
        import asyncio
        if source in self._custom_fetchers:
            return asyncio.get_event_loop().run_until_complete(self._run_custom_fetcher(source))
        return asyncio.get_event_loop().run_until_complete(self._scrape_source_async(source))
    async def _get_client(self):
        return httpx.AsyncClient(timeout=httpx.Timeout(self._timeout),
                             headers={"User-Agent": self._user_agent}, follow_redirects=True)
    async def _fetch_with_retry(self, client, url):
        for attempt in range(self._max_retries):
            try:
                resp = await client.get(url)
                if resp.status_code == 200: return resp.text
                if resp.status_code in (429, 503): await asyncio.sleep((attempt + 1) * 2)
                else: return None
            except httpx.RequestError:
                if attempt < self._max_retries - 1: await asyncio.sleep(2 ** attempt)
        self._errors.append("Failed: " + url); return None
    async def _scrape_url_async(self, url):
        self._errors = []; started = time.monotonic(); result = ScrapeResult(url, domain="custom")
        async with await self._get_client() as client:
            html = await self._fetch_with_retry(client, url)
            if html:
                chunks = self._parse_html_to_chunks(html, url, "custom", "Philippines")
                result.chunks = chunks; result.pages_scraped = 1; result.items_found = len(chunks)
        result.errors = self._errors; result.duration_seconds = time.monotonic() - started; return result

    async def _scrape_source_async(self, source):
        self._errors = []; started = time.monotonic(); cfg = SCRAPE_SOURCES.get(source)
        if not cfg: self._errors.append("Unknown source: " + source); return ScrapeResult(source, errors=self._errors)
        result = ScrapeResult(source, domain=cfg["domain"], jurisdiction=cfg["jurisdiction"])
        async with await self._get_client() as client:
            list_html = await self._fetch_with_retry(client, cfg["list_url"])
            if not list_html: result.errors = self._errors; result.duration_seconds = time.monotonic() - started; return result
            result.pages_scraped += 1; links = self._extract_links(list_html, cfg); result.items_found = len(links)
            for link_info in links[:10]:
                await self._rate_limit(source)
                html = await self._fetch_with_retry(client, link_info["url"])
                if html:
                    chunks = self._parse_html_to_chunks(html, link_info["url"], cfg["domain"], cfg["jurisdiction"])
                    title = link_info.get("title", "")
                    for c in chunks:
                        if isinstance(c, dict) and "text" in c and title: c["text"] = "[" + title + "] " + c["text"]
                    result.chunks.extend(chunks); result.pages_scraped += 1
        result.errors = self._errors; result.duration_seconds = time.monotonic() - started; return result
    async def _run_custom_fetcher(self, source):
        self._errors = []; started = time.monotonic()
        try: fetcher = self._custom_fetchers[source]; result = await fetcher(); result.duration_seconds = time.monotonic() - started; return result
        except Exception as exc: self._errors.append(str(exc)); return ScrapeResult(source, errors=self._errors, duration_seconds=time.monotonic() - started)
    async def _rate_limit(self, source):
        domain = SCRAPE_SOURCES.get(source, {}).get("domain_filter", source)
        now = time.monotonic(); last = self._last_request_time.get(domain, 0)
        if now - last < self._rate_limit: await asyncio.sleep(self._rate_limit - (now - last))
        self._last_request_time[domain] = time.monotonic()

    def _extract_links(self, html, cfg):
        soup = BeautifulSoup(html, "lxml"); links = []
        for a_tag in soup.select(cfg.get("link_selector", "a[href]")):
            href = a_tag.get("href", "")
            if not href or href.startswith("#") or href.startswith("mailto:"): continue
            df = cfg.get("domain_filter", "")
            if df and df not in href and not href.startswith("/"): continue
            if href.startswith("/"): href = cfg.get("base_url", "").rstrip("/") + href
            elif not href.startswith("http"): href = cfg.get("base_url", "").rstrip("/") + "/" + href.lstrip("/")
            title = a_tag.get_text(strip=True) or href
            links.append({"url": href, "title": title[:200]})
        seen = set(); return [l for l in links if l["url"] not in seen and not seen.add(l["url"])]
    def _parse_html_to_chunks(self, html, url, domain, jurisdiction):
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["nav", "header", "footer", "script", "style"]): tag.decompose()
        body = ""
        for sel in [".entry-content", ".post-content", ".content", "article", "main"]:
            el = soup.select_one(sel)
            if el: body = el.get_text(separator="XNL", strip=True); break
        if not body: body = soup.get_text(separator="XNL", strip=True)
        body = body.replace("XNL", "\n")
        body = re.sub(r"\n{3,}", "\n\n", body)
        body = re.sub(r" {2,}", " ", body)
        chunks = self._chunk_text(body)
        return [{"text": c, "source": domain + "-web", "domain": domain, "jurisdiction": jurisdiction, "citation": "Scraped from " + url} for c in chunks]
    def _chunk_text(self, text, max_words=200, overlap=30):
        SEP = "\x00"; text2 = re.sub(r"(?<=[.!?])\s+(?=[A-Z0-9])", SEP, text)
        sentences = [s.strip() for s in text2.split(SEP) if s.strip()]
        if not sentences: return [text] if text else []
        chunks, curr, cnt = [], [], 0
        for s in sentences:
            words = s.split()
            while len(words) > max_words:
                if curr: chunks.append(" ".join(curr)); curr = curr[-overlap:] if overlap else []
                piece = words[:max_words]; words = words[max_words:]; curr.extend(piece); cnt = len(curr)
            if cnt + len(words) > max_words and curr:
                chunks.append(" ".join(curr)); curr = curr[-overlap:] + words if overlap else words; cnt = len(curr)
            else: curr.extend(words); cnt += len(words)
        if curr: chunks.append(" ".join(curr))
        return [c for c in chunks if c]

_scraper_instance = None

def get_scraper():
    global _scraper_instance
    if _scraper_instance is None: _scraper_instance = ScraperService()
    return _scraper_instance