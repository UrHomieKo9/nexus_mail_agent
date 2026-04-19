"""Gmail API client — connects to Gmail via Google API."""

import base64
import re
from datetime import datetime, timezone

import httpx

from backend.api.schemas import EmailMessage, EmailPlatform
from backend.connectors.base import BaseConnector
from backend.core.logger import get_logger

logger = get_logger("gmail_connector")

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


class GmailConnector(BaseConnector):
    """Gmail API connector implementing the BaseConnector interface."""

    platform = EmailPlatform.GMAIL

    async def fetch_emails(
        self,
        access_token: str,
        max_results: int = 50,
        query: str = "",
        page_token: str | None = None,
    ) -> tuple[list[EmailMessage], str | None]:
        """Fetch emails from Gmail."""
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"maxResults": max_results}
        if query:
            params["q"] = query
        if page_token:
            params["pageToken"] = page_token

        async with httpx.AsyncClient() as client:
            # List messages
            resp = await client.get(
                f"{GMAIL_API_BASE}/messages",
                headers=headers,
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

            messages = data.get("messages", [])
            next_page_token = data.get("nextPageToken")

            # Fetch each message detail
            emails = []
            for msg_ref in messages:
                msg_resp = await client.get(
                    f"{GMAIL_API_BASE}/messages/{msg_ref['id']}",
                    headers=headers,
                    params={"format": "full"},
                )
                if msg_resp.status_code == 200:
                    emails.append(self._normalize_message(msg_resp.json()))

        logger.info("gmail_emails_fetched", count=len(emails))
        return emails, next_page_token

    async def send_email(
        self,
        access_token: str,
        to: str,
        subject: str,
        body: str,
        thread_id: str | None = None,
        reply_to_message_id: str | None = None,
    ) -> str:
        """Send an email via Gmail API."""
        headers_auth = {"Authorization": f"Bearer {access_token}"}

        # Build raw RFC 2822 message
        raw_msg = f"To: {to}\r\nSubject: {subject}\r\n"
        if reply_to_message_id:
            raw_msg += f"In-Reply-To: {reply_to_message_id}\r\n"
        raw_msg += "Content-Type: text/plain; charset=utf-8\r\n\r\n"
        raw_msg += body

        encoded = base64.urlsafe_b64encode(raw_msg.encode("utf-8")).decode("utf-8")

        payload: dict = {"raw": encoded}
        if thread_id:
            payload["threadId"] = thread_id

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{GMAIL_API_BASE}/messages/send",
                headers=headers_auth,
                json=payload,
            )
            resp.raise_for_status()
            result = resp.json()

        logger.info("gmail_email_sent", message_id=result.get("id"), to=to)
        return result.get("id", "")

    async def get_thread(
        self,
        access_token: str,
        thread_id: str,
    ) -> list[EmailMessage]:
        """Get all messages in a Gmail thread."""
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GMAIL_API_BASE}/threads/{thread_id}",
                headers=headers,
                params={"format": "full"},
            )
            resp.raise_for_status()
            data = resp.json()

        messages = []
        for msg in data.get("messages", []):
            messages.append(self._normalize_message(msg))

        return messages

    async def list_labels(
        self,
        access_token: str,
    ) -> list[dict]:
        """List Gmail labels."""
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GMAIL_API_BASE}/labels",
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        return data.get("labels", [])

    def _normalize_message(self, raw: dict) -> EmailMessage:
        """Convert Gmail API message to Unified Mail Schema."""
        headers_map = {}
        for h in raw.get("payload", {}).get("headers", []):
            headers_map[h["name"].lower()] = h["value"]

        body_text = self._extract_body(raw)
        labels = raw.get("labelIds", [])
        timestamp_ms = int(raw.get("internalDate", 0))

        return EmailMessage(
            platform=EmailPlatform.GMAIL,
            thread_id=raw.get("threadId", ""),
            message_id=raw.get("id", ""),
            sender=headers_map.get("from", ""),
            sender_name=self._extract_name(headers_map.get("from", "")),
            recipient=headers_map.get("to", ""),
            subject=headers_map.get("subject", ""),
            body_clean=self._strip_html(body_text),
            body_html=body_text,
            timestamp=datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc),
            attachments=self._extract_attachments(raw),
            labels=labels,
            is_read="UNREAD" not in labels,
            is_sent="SENT" in labels,
        )

    @staticmethod
    def _extract_body(raw: dict) -> str:
        """Recursively extract text body from Gmail message payload."""
        payload = raw.get("payload", {})

        # Check direct body
        if payload.get("body", {}).get("data"):
            data = payload["body"]["data"]
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

        # Check parts (multipart)
        parts = payload.get("parts", [])
        for part in parts:
            mime_type = part.get("mimeType", "")
            if mime_type == "text/plain" and part.get("body", {}).get("data"):
                data = part["body"]["data"]
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            if mime_type.startswith("multipart/"):
                # Recurse into nested multipart
                return GmailConnector._extract_body({"payload": part})

        # Fallback to HTML if no plain text
        for part in parts:
            if part.get("mimeType") == "text/html" and part.get("body", {}).get("data"):
                data = part["body"]["data"]
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

        return ""

    @staticmethod
    def _extract_name(from_header: str) -> str:
        """Extract display name from 'Name <email>' format."""
        match = re.match(r"^(.+?)\s*<", from_header)
        return match.group(1).strip().strip('"') if match else ""

    @staticmethod
    def _strip_html(text: str) -> str:
        """Remove HTML tags for body_clean field."""
        clean = re.sub(r"<[^>]+>", " ", text)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    @staticmethod
    def _extract_attachments(raw: dict) -> list[str]:
        """Extract attachment filenames from message."""
        attachments = []
        parts = raw.get("payload", {}).get("parts", [])
        for part in parts:
            if part.get("filename"):
                attachments.append(part["filename"])
        return attachments