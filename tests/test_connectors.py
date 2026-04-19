"""Tests for email connectors — Gmail and Outlook normalization."""

from datetime import datetime, timezone

import pytest

from backend.api.schemas import EmailMessage, EmailPlatform
from backend.connectors.gmail import GmailConnector
from backend.connectors.outlook import OutlookConnector


# ── Gmail Connector ──


class TestGmailNormalization:
    """Test Gmail API message → Unified Mail Schema conversion."""

    def setup_method(self):
        self.connector = GmailConnector()

    def test_normalize_basic_message(self):
        raw = {
            "id": "msg-123",
            "threadId": "thread-456",
            "internalDate": "1700000000000",
            "labelIds": ["INBOX", "UNREAD"],
            "payload": {
                "headers": [
                    {"name": "From", "value": "Alice Chen <alice@example.com>"},
                    {"name": "To", "value": "me@example.com"},
                    {"name": "Subject", "value": "Test Subject"},
                ],
                "body": {},
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {
                            "data": "SGVsbG8gV29ybGQ=",  # "Hello World" base64
                        },
                    }
                ],
            },
        }

        result = self.connector._normalize_message(raw)
        assert isinstance(result, EmailMessage)
        assert result.platform == EmailPlatform.GMAIL
        assert result.message_id == "msg-123"
        assert result.thread_id == "thread-456"
        assert result.sender == "Alice Chen <alice@example.com>"
        assert result.sender_name == "Alice Chen"
        assert result.subject == "Test Subject"
        assert "Hello World" in result.body_clean
        assert result.is_read is False  # UNREAD label present
        assert result.is_sent is False

    def test_normalize_sent_message(self):
        raw = {
            "id": "msg-sent",
            "threadId": "t-1",
            "internalDate": "1700000000000",
            "labelIds": ["SENT"],
            "payload": {"headers": [], "body": {}, "parts": []},
        }
        result = self.connector._normalize_message(raw)
        assert result.is_sent is True
        assert result.is_read is True

    def test_extract_name_simple(self):
        assert GmailConnector._extract_name("Alice <alice@ex.com>") == "Alice"

    def test_extract_name_quoted(self):
        assert GmailConnector._extract_name('"Bob Smith" <bob@ex.com>') == "Bob Smith"

    def test_extract_name_email_only(self):
        assert GmailConnector._extract_name("alice@ex.com") == ""

    def test_strip_html(self):
        assert GmailConnector._strip_html("<p>Hello <b>World</b></p>") == "Hello World"

    def test_extract_attachments(self):
        raw = {
            "payload": {
                "parts": [
                    {"filename": "doc.pdf"},
                    {"filename": ""},
                    {"filename": "image.png"},
                ],
            },
        }
        result = GmailConnector._extract_attachments(raw)
        assert result == ["doc.pdf", "image.png"]


# ── Outlook Connector ──


class TestOutlookNormalization:
    """Test Microsoft Graph message → Unified Mail Schema conversion."""

    def setup_method(self):
        self.connector = OutlookConnector()

    def test_normalize_basic_message(self):
        raw = {
            "id": "ol-msg-123",
            "conversationId": "ol-thread-456",
            "subject": "Outlook Test",
            "body": {"contentType": "Text", "content": "Plain text body"},
            "from": {"emailAddress": {"address": "bob@outlook.com", "name": "Bob"}},
            "toRecipients": [{"emailAddress": {"address": "me@outlook.com"}}],
            "receivedDateTime": "2024-11-14T10:00:00Z",
            "isRead": True,
            "hasAttachments": False,
        }

        result = self.connector._normalize_message(raw)
        assert isinstance(result, EmailMessage)
        assert result.platform == EmailPlatform.OUTLOOK
        assert result.message_id == "ol-msg-123"
        assert result.sender == "bob@outlook.com"
        assert result.sender_name == "Bob"
        assert result.body_clean == "Plain text body"

    def test_normalize_html_body(self):
        raw = {
            "id": "ol-2",
            "conversationId": "t",
            "subject": "HTML",
            "body": {"contentType": "HTML", "content": "<p>Hello <b>World</b></p>"},
            "from": {"emailAddress": {"address": "a@b.com", "name": "A"}},
            "toRecipients": [],
            "receivedDateTime": "2024-01-01T00:00:00Z",
            "isRead": False,
        }
        result = self.connector._normalize_message(raw)
        assert "Hello" in result.body_clean
        assert "<p>" not in result.body_clean

    def test_normalize_missing_recipients(self):
        raw = {
            "id": "ol-3",
            "conversationId": "t",
            "subject": "No To",
            "body": {"contentType": "Text", "content": ""},
            "from": {"emailAddress": {"address": "a@b.com", "name": "A"}},
            "toRecipients": [],
            "receivedDateTime": "",
        }
        result = self.connector._normalize_message(raw)
        assert result.recipient == ""
