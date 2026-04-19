"""Microsoft Graph API client — connects to Outlook via Microsoft Graph."""

import re
from datetime import datetime, timezone

import httpx

from backend.api.schemas import EmailMessage, EmailPlatform
from backend.connectors.base import BaseConnector
from backend.core.logger import get_logger

logger = get_logger("outlook_connector")

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"


class OutlookConnector(BaseConnector):
    """Microsoft Graph API connector implementing the BaseConnector interface."""

    platform = EmailPlatform.OUTLOOK

    async def fetch_emails(
        self,
        access_token: str,
        max_results: int = 50,
        query: str = "",
        page_token: str | None = None,
    ) -> tuple[list[EmailMessage], str | None]:
        """Fetch emails from Outlook via Microsoft Graph."""
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {
            "$top": max_results,
            "$select": "id,subject,body,receivedDateTime,from,toRecipients,internetMessageId,conversationId,isRead,hasAttachments",
            "$orderby": "receivedDateTime desc",
        }
        if query:
            params["$search"] = f'"{query}"'

        url = f"{GRAPH_API_BASE}/me/messages"
        if page_token:
            url = page_token

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()

        messages = data.get("value", [])
        emails = [self._normalize_message(msg) for msg in messages]

        # Microsoft Graph uses @odata.nextLink for pagination
        next_link = data.get("@odata.nextLink")

        logger.info("outlook_emails_fetched", count=len(emails))
        return emails, next_link

    async def send_email(
        self,
        access_token: str,
        to: str,
        subject: str,
        body: str,
        thread_id: str | None = None,
        reply_to_message_id: str | None = None,
    ) -> str:
        """Send an email via Microsoft Graph API."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "Text", "content": body},
                "toRecipients": [{"emailAddress": {"address": to}}],
            },
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{GRAPH_API_BASE}/me/sendMail",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()

        logger.info("outlook_email_sent", to=to)
        return ""

    async def get_thread(
        self,
        access_token: str,
        thread_id: str,
    ) -> list[EmailMessage]:
        """Get all messages in a conversation thread."""
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GRAPH_API_BASE}/me/messages",
                headers=headers,
                params={
                    "$filter": f"conversationId eq '{thread_id}'",
                    "$orderby": "receivedDateTime asc",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        messages = data.get("value", [])
        return [self._normalize_message(msg) for msg in messages]

    async def list_labels(
        self,
        access_token: str,
    ) -> list[dict]:
        """List Outlook mail folders (equivalent to labels)."""
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GRAPH_API_BASE}/me/mailFolders",
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        return data.get("value", [])

    def _normalize_message(self, raw: dict) -> EmailMessage:
        """Convert Microsoft Graph message to Unified Mail Schema."""
        sender_obj = raw.get("from", {}).get("emailAddress", {})
        recipients = raw.get("toRecipients", [])
        recipient_email = recipients[0]["emailAddress"]["address"] if recipients else ""

        body_content = raw.get("body", {}).get("content", "")
        body_type = raw.get("body", {}).get("contentType", "text")

        received_dt = raw.get("receivedDateTime", "")
        timestamp = datetime.fromisoformat(received_dt.replace("Z", "+00:00")) if received_dt else datetime.now(timezone.utc)

        return EmailMessage(
            platform=EmailPlatform.OUTLOOK,
            thread_id=raw.get("conversationId", ""),
            message_id=raw.get("id", ""),
            sender=sender_obj.get("address", ""),
            sender_name=sender_obj.get("name", ""),
            recipient=recipient_email,
            subject=raw.get("subject", ""),
            body_clean=self._strip_html(body_content) if body_type == "HTML" else body_content,
            body_html=body_content if body_type == "HTML" else "",
            timestamp=timestamp,
            attachments=[],
            labels=[],
            is_read=raw.get("isRead", True),
            is_sent=False,
        )

    @staticmethod
    def _strip_html(text: str) -> str:
        """Remove HTML tags for body_clean field."""
        clean = re.sub(r"<[^>]+>", " ", text)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean