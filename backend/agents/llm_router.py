"""LLM Router — Groq → Gemini → Ollama cascade with automatic fallback."""

from dataclasses import dataclass

from backend.core.config import settings
from backend.core.logger import get_logger

logger = get_logger("llm_router")


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""

    text: str
    provider: str
    model: str
    usage: dict | None = None


class LLMRouter:
    """Cascade LLM router: Groq (primary) → Gemini (fallback) → Ollama (local).

    No single provider failure can take down the system.
    """

    def __init__(self):
        self._groq_available = bool(settings.groq_api_key)
        self._gemini_available = bool(settings.gemini_api_key)
        self._ollama_available = bool(settings.ollama_base_url)

    async def generate(self, prompt: str, system: str = "", max_tokens: int = 2048) -> LLMResponse:
        """Generate a response using the cascade.

        Tries providers in order: Groq → Gemini → Ollama.
        Returns the first successful response.
        """
        errors = []

        # Layer 1: Groq (Llama 4) — primary
        if self._groq_available:
            try:
                return await self._call_groq(prompt, system, max_tokens)
            except Exception as exc:
                errors.append(f"groq: {exc}")
                logger.warning("groq_failed", error=str(exc))

        # Layer 2: Gemini Flash-Lite — fallback if 429 or error
        if self._gemini_available:
            try:
                return await self._call_gemini(prompt, system, max_tokens)
            except Exception as exc:
                errors.append(f"gemini: {exc}")
                logger.warning("gemini_failed", error=str(exc))

        # Layer 3: Ollama (local) — fallback if both cloud providers fail
        if self._ollama_available:
            try:
                return await self._call_ollama(prompt, system, max_tokens)
            except Exception as exc:
                errors.append(f"ollama: {exc}")
                logger.warning("ollama_failed", error=str(exc))

        logger.error("all_providers_failed", errors=errors)
        raise RuntimeError(f"All LLM providers failed: {errors}")

    async def _call_groq(self, prompt: str, system: str, max_tokens: int) -> LLMResponse:
        """Call Groq API (Llama 4)."""
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": 0.7,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        return LLMResponse(
            text=content,
            provider="groq",
            model="llama-3.3-70b-versatile",
            usage=usage,
        )

    async def _call_gemini(self, prompt: str, system: str, max_tokens: int) -> LLMResponse:
        """Call Gemini API (Flash-Lite)."""
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            contents = []
            if system:
                contents.append({"role": "user", "parts": [{"text": system}]})
                contents.append({"role": "model", "parts": [{"text": "Understood."}]})
            contents.append({"role": "user", "parts": [{"text": prompt}]})

            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent?key={settings.gemini_api_key}",
                json={
                    "contents": contents,
                    "generationConfig": {
                        "maxOutputTokens": max_tokens,
                        "temperature": 0.7,
                    },
                },
            )
            resp.raise_for_status()
            data = resp.json()

        text = data["candidates"][0]["content"]["parts"][0]["text"]

        return LLMResponse(
            text=text,
            provider="gemini",
            model="gemini-2.0-flash-lite",
            usage=data.get("usageMetadata", {}),
        )

    async def _call_ollama(self, prompt: str, system: str, max_tokens: int) -> LLMResponse:
        """Call local Ollama API."""
        import httpx

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json={
                    "model": "llama3.2",
                    "messages": [
                        {"role": "system", "content": system} if system else None,
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": 0.7,
                    },
                },
            )
            resp.raise_for_status()
            data = resp.json()

        return LLMResponse(
            text=data["message"]["content"],
            provider="ollama",
            model="llama3.2",
            usage={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
            },
        )


# Singleton router instance
llm_router = LLMRouter()