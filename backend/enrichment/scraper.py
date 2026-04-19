"""Web Scraper — L3 website and LinkedIn scraping for lead enrichment."""

import re

import httpx
from bs4 import BeautifulSoup

from backend.core.logger import get_logger

logger = get_logger("scraper")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


class WebScraper:
    """Layer-3 enrichment: scrape company websites and LinkedIn profiles."""

    async def scrape_company(self, url: str) -> dict:
        """Scrape a company website for enrichment data.

        Args:
            url: The company website URL.

        Returns:
            Dict with company_description, recent_news, and
            other scrapable data.
        """
        result: dict = {
            "company_description": "",
            "company_website": url,
            "recent_news": [],
        }

        try:
            html = await self._fetch_page(url)
            if not html:
                return result

            soup = BeautifulSoup(html, "lxml")

            # Extract meta description
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc and meta_desc.get("content"):
                result["company_description"] = meta_desc["content"][:500]

            # Fallback: first meaningful paragraph
            if not result["company_description"]:
                result["company_description"] = self._extract_first_paragraph(soup)

            # Try to find LinkedIn URL
            linkedin = self._find_linkedin_link(soup)
            if linkedin:
                result["linkedin_url"] = linkedin

            # Look for a blog/news section
            news_items = self._extract_news_links(soup, url)
            result["recent_news"] = news_items[:5]

        except Exception as exc:
            logger.error("scrape_company_failed", url=url, error=str(exc))

        logger.info(
            "company_scraped",
            url=url,
            has_description=bool(result["company_description"]),
            news_count=len(result["recent_news"]),
        )
        return result

    async def scrape_linkedin(self, url: str) -> dict:
        """Scrape public LinkedIn profile/company page.

        Note: LinkedIn aggressively blocks scrapers. This is a
        best-effort extraction from public pages only.

        Args:
            url: LinkedIn profile or company URL.

        Returns:
            Dict with available profile data.
        """
        result: dict = {"linkedin_url": url}

        try:
            html = await self._fetch_page(url)
            if not html:
                return result

            soup = BeautifulSoup(html, "lxml")

            # Extract page title (often contains name + title)
            title_tag = soup.find("title")
            if title_tag and title_tag.string:
                result["page_title"] = title_tag.string.strip()

            # Meta description often has useful summary
            meta = soup.find("meta", attrs={"name": "description"})
            if meta and meta.get("content"):
                result["summary"] = meta["content"][:500]

        except Exception as exc:
            logger.error("scrape_linkedin_failed", url=url, error=str(exc))

        return result

    async def _fetch_page(self, url: str) -> str | None:
        """Fetch a page's HTML content."""
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        try:
            async with httpx.AsyncClient(
                timeout=15.0, follow_redirects=True, headers=_HEADERS
            ) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp.text
                logger.warning("fetch_non_200", url=url, status=resp.status_code)
        except Exception as exc:
            logger.error("fetch_page_failed", url=url, error=str(exc))

        return None

    @staticmethod
    def _extract_first_paragraph(soup: BeautifulSoup) -> str:
        """Extract the first meaningful paragraph from a page."""
        for p in soup.find_all("p"):
            text = p.get_text(strip=True)
            if len(text) > 60:
                return text[:500]
        return ""

    @staticmethod
    def _find_linkedin_link(soup: BeautifulSoup) -> str:
        """Find a LinkedIn URL in the page's links."""
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "linkedin.com/company/" in href or "linkedin.com/in/" in href:
                return href
        return ""

    @staticmethod
    def _extract_news_links(soup: BeautifulSoup, base_url: str) -> list[str]:
        """Extract blog/news article titles from the page."""
        news_keywords = ("blog", "news", "press", "update", "article")
        items = []

        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            text = a.get_text(strip=True)
            if any(kw in href for kw in news_keywords) and len(text) > 15:
                items.append(text[:200])
            if len(items) >= 10:
                break

        return items
