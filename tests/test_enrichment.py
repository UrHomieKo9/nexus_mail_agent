"""Tests for the enrichment layer — Hunter, Apollo, Scraper, Social Monitor."""

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from backend.enrichment.hunter import HunterEnrichment
from backend.enrichment.apollo import ApolloEnrichment
from backend.enrichment.scraper import WebScraper


# ── Hunter.io ──


class TestHunter:
    def test_freemail_detection(self):
        assert HunterEnrichment._is_freemail("gmail.com") is True
        assert HunterEnrichment._is_freemail("yahoo.com") is True
        assert HunterEnrichment._is_freemail("company.com") is False

    @pytest.mark.asyncio
    async def test_lookup_no_api_key(self):
        with patch("backend.enrichment.hunter.settings") as mock_settings:
            mock_settings.hunter_api_key = ""
            hunter = HunterEnrichment()
            hunter._api_key = ""
            result = await hunter.lookup("test@company.com")
            assert result["email"] == "test@company.com"
            assert result["email_verified"] is False

    @pytest.mark.asyncio
    async def test_verify_no_api_key(self):
        hunter = HunterEnrichment()
        hunter._api_key = ""
        result = await hunter.verify("test@example.com")
        assert result["result"] == "unknown"

    @pytest.mark.asyncio
    async def test_lookup_freemail_skips_domain_search(self):
        hunter = HunterEnrichment()
        hunter._api_key = ""
        result = await hunter.lookup("test@gmail.com")
        assert result["company_domain"] == ""
        assert result["enrichment_layers_completed"] == 0


# ── Apollo.io ──


class TestApollo:
    @pytest.mark.asyncio
    async def test_lookup_no_api_key(self):
        apollo = ApolloEnrichment()
        apollo._api_key = ""
        result = await apollo.lookup("test@company.com")
        assert result == {}

    def test_format_size(self):
        assert ApolloEnrichment._format_size(None) == ""
        assert ApolloEnrichment._format_size(5) == "1-10"
        assert ApolloEnrichment._format_size(25) == "11-50"
        assert ApolloEnrichment._format_size(100) == "51-200"
        assert ApolloEnrichment._format_size(500) == "201-1000"
        assert ApolloEnrichment._format_size(3000) == "1001-5000"
        assert ApolloEnrichment._format_size(10000) == "5000+"


# ── Web Scraper ──


class TestWebScraper:
    @pytest.mark.asyncio
    async def test_scrape_company_unreachable(self):
        scraper = WebScraper()
        with patch.object(scraper, "_fetch_page", new_callable=AsyncMock, return_value=None):
            result = await scraper.scrape_company("https://nonexistent.example.com")
            assert result["company_description"] == ""

    @pytest.mark.asyncio
    async def test_scrape_company_with_meta(self):
        html = '<html><head><meta name="description" content="We build amazing tools for developers."></head><body></body></html>'
        scraper = WebScraper()
        with patch.object(scraper, "_fetch_page", new_callable=AsyncMock, return_value=html):
            result = await scraper.scrape_company("https://example.com")
            assert "amazing tools" in result["company_description"]

    @pytest.mark.asyncio
    async def test_scrape_finds_linkedin(self):
        html = '<html><body><a href="https://linkedin.com/company/acme">LinkedIn</a></body></html>'
        scraper = WebScraper()
        with patch.object(scraper, "_fetch_page", new_callable=AsyncMock, return_value=html):
            result = await scraper.scrape_company("https://acme.com")
            assert "linkedin.com" in result.get("linkedin_url", "")

    def test_extract_first_paragraph(self):
        from bs4 import BeautifulSoup
        html = "<html><body><p>Short</p><p>This is a much longer paragraph that contains useful information about the company.</p></body></html>"
        soup = BeautifulSoup(html, "lxml")
        text = WebScraper._extract_first_paragraph(soup)
        assert "useful information" in text
