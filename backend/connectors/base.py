"""Abstract base class for email provider connectors."""

from abc import ABC, abstractmethod
from datetime import datetime

from backend.api.schemas import EmailMessage, EmailPlatform


class BaseConnector(ABC):
    """Platform-agnostic interface that all email connectors implement."""

    platform: EmailPlatform

    @abstractmethod
    async def fetch_emails(
        self,
        access_token: str,
        max_results: int = 50,
        query: str = "",
        page_token: str | None = None,
    ) -> tuple[list[EmailMessage], str | None]:
        """Fetch emails from the provider.

        Returns a tuple of (emails, next_page_token).
        """
        ...

    @abstractmethod
    async def send_email(
        self,
        access_token: str,
        to: str,
        subject: str,
        body: str,
        thread_id: str | None = None,
        reply_to_message_id: str | None = None,
    ) -> str:
        """Send an email. Returns the message ID of the sent email."""
        ...

    @abstractmethod
    async def get_thread(
        self,
        access_token: str,
        thread_id: str,
    ) -> list[EmailMessage]:
        """Get all messages in a thread."""
        ...

    @abstractmethod
    async def list_labels(
        self,
        access_token: str,
    ) -> list[dict]:
        """List available labels/folders for the account."""
        ...

    @abstractmethod
    def _normalize_message(self, raw: dict) -> EmailMessage:
        """Convert provider-specific message format to Unified Mail Schema."""
        ...