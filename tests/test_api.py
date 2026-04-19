"""Tests for FastAPI API routes."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.schemas import EmailPlatform


@pytest.fixture
def client():
    """Create a test client with mocked dependencies."""
    with patch("backend.api.routes.create_client") as mock_supabase, \
         patch("backend.api.routes.fetch_user_emails") as mock_fetch:
        # Mock Supabase client
        mock_table = MagicMock()
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.order.return_value = mock_table
        mock_table.range.return_value = mock_table
        mock_table.limit.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.update.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[])
        mock_supabase.return_value.table.return_value = mock_table

        # Mock Celery task
        mock_fetch.delay.return_value = MagicMock(id="task-123")

        from backend.main import app
        yield TestClient(app)


class TestHealthCheck:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestStatsRoute:
    def test_stats(self, client):
        resp = client.get("/api/v1/stats/u1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "u1"
        assert "emails" in data
        assert "drafts" in data


class TestEmailRoutes:
    def test_fetch_emails(self, client):
        resp = client.post(
            "/api/v1/emails/fetch",
            json={"user_id": "u1", "provider": "gmail", "max_results": 10},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "queued"

    def test_list_emails(self, client):
        resp = client.get("/api/v1/emails/u1?page=1&page_size=10")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_get_thread(self, client):
        resp = client.get("/api/v1/emails/u1/thread/t1")
        assert resp.status_code == 200
        assert "messages" in resp.json()


class TestDraftRoutes:
    def test_list_drafts(self, client):
        resp = client.get("/api/v1/drafts/u1?page=1")
        assert resp.status_code == 200
        assert "items" in resp.json()

    def test_review_draft_not_found(self, client):
        resp = client.post(
            "/api/v1/drafts/nonexistent/review",
            json={"action": "approved"},
        )
        assert resp.status_code == 404


class TestLeadRoutes:
    def test_list_leads(self, client):
        resp = client.get("/api/v1/leads/u1")
        assert resp.status_code == 200


class TestCampaignRoutes:
    def test_create_campaign(self, client):
        resp = client.post(
            "/api/v1/campaigns",
            json={
                "user_id": "u1",
                "name": "Test Campaign",
                "subject_template": "Hi {{name}}",
                "body_template": "Hello {{name}} from {{company}}",
                "recipient_emails": ["a@b.com"],
            },
        )
        assert resp.status_code == 200
        assert "campaign_id" in resp.json()

    def test_list_campaigns(self, client):
        resp = client.get("/api/v1/campaigns/u1")
        assert resp.status_code == 200


class TestWebhookRoutes:
    def test_gmail_webhook(self, client):
        resp = client.post("/api/v1/webhooks/gmail", json={"data": "test"})
        assert resp.status_code == 200

    def test_outlook_webhook(self, client):
        resp = client.post("/api/v1/webhooks/outlook", json={"data": "test"})
        assert resp.status_code == 200
