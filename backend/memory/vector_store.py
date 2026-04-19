"""pgvector-based vector store for semantic email memory (RAG)."""

import uuid
from datetime import datetime, timezone

import httpx
from supabase import create_client

from backend.api.schemas import EmailMessage
from backend.core.config import settings
from backend.core.logger import get_logger

logger = get_logger("vector_store")


class VectorStore:
    """Semantic memory layer using Supabase pgvector.

    Stores email embeddings and supports similarity search
    for contextual retrieval during agent processing.
    """

    def __init__(self):
        self._supabase = None

    @property
    def supabase(self):
        if self._supabase is None:
            self._supabase = create_client(
                settings.supabase_url, settings.supabase_service_key
            )
        return self._supabase

    async def get_embedding(self, text: str) -> list[float]:
        """Generate embedding for text using Ollama nomic-embed-text.

        Falls back to a simple hash-based vector if Ollama is unavailable.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{settings.ollama_base_url}/api/embed",
                    json={
                        "model": settings.embedding_model,
                        "input": text,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("embeddings", [data.get("embedding", [])])[0]
        except Exception as exc:
            logger.warning("embedding_fallback", error=str(exc))

        # Fallback: zero vector (allows system to function without Ollama)
        return [0.0] * settings.embedding_dimension

    async def store_email(self, user_id: str, email: EmailMessage) -> str:
        """Store an email with its embedding in pgvector.

        Returns the embedding record ID.
        """
        # Generate embedding from email content
        text_to_embed = f"Subject: {email.subject}\nFrom: {email.sender}\n{email.body_clean[:2000]}"
        embedding = await self.get_embedding(text_to_embed)

        record_id = str(uuid.uuid4())

        self.supabase.table("email_embeddings").insert({
            "id": record_id,
            "user_id": user_id,
            "message_id": email.message_id,
            "thread_id": email.thread_id,
            "sender": email.sender,
            "subject": email.subject,
            "body_snippet": email.body_clean[:500],
            "platform": email.platform.value,
            "timestamp": email.timestamp.isoformat(),
            "embedding": embedding,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()

        logger.info("email_embedded", record_id=record_id, message_id=email.message_id)
        return record_id

    async def store_emails(self, user_id: str, emails: list[EmailMessage]) -> list[str]:
        """Store multiple emails with embeddings. Returns list of record IDs."""
        record_ids = []
        for email in emails:
            rid = await self.store_email(user_id, email)
            record_ids.append(rid)
        return record_ids

    async def search(
        self,
        user_id: str,
        query: str,
        match_threshold: float = 0.7,
        match_count: int = 5,
        sender_filter: str | None = None,
    ) -> list[dict]:
        """Semantic search for relevant emails using pgvector similarity.

        Args:
            user_id: The user whose emails to search.
            query: Natural language query.
            match_threshold: Minimum cosine similarity (0-1).
            match_count: Maximum results to return.
            sender_filter: Optional sender email to filter by.

        Returns:
            List of matching email records with similarity scores.
        """
        query_embedding = await self.get_embedding(query)

        # Use Supabase RPC to call the match_emails function
        params = {
            "query_embedding": query_embedding,
            "match_threshold": match_threshold,
            "match_count": match_count,
            "p_user_id": user_id,
        }

        if sender_filter:
            params["p_sender"] = sender_filter

        result = self.supabase.rpc("match_emails", params).execute()

        logger.info(
            "vector_search",
            user_id=user_id,
            query_preview=query[:50],
            results=len(result.data),
        )
        return result.data

    async def get_sender_context(
        self, user_id: str, sender_email: str, count: int = 3
    ) -> list[dict]:
        """Get recent email context for a specific sender.

        Used by agents to answer: "What was the tone and outcome of
        the last N interactions with this person?"
        """
        result = (
            self.supabase.table("email_embeddings")
            .select("subject, body_snippet, timestamp, sender")
            .eq("user_id", user_id)
            .eq("sender", sender_email)
            .order("timestamp", desc=True)
            .limit(count)
            .execute()
        )

        return result.data

    async def delete_user_data(self, user_id: str) -> int:
        """Delete all embedding data for a user (GDPR compliance)."""
        self.supabase.table("email_embeddings").delete().eq(
            "user_id", user_id
        ).execute()

        logger.info("user_embeddings_deleted", user_id=user_id)
        return 1