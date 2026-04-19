"""Hunter.io — L1 email verification and domain lookup."""

import httpx

from backend.core.config import settings
from backend.core.logger import get_logger

logger = get_logger("hunter")

HUNTER_API_BASE = "https://api.hunter.io/v2"


class HunterEnrichment:
    """Layer-1 enrichment: email verification + domain search via Hunter.io."""

    def __init__(self):
        self._api_key = settings.hunter_api_key

    async def lookup(self, email: str) -> dict:
        """Full L1 lookup: verify email, then search its domain.

        Returns a dict compatible with EnrichmentData fields.
        """
        result: dict = {
            "email": email,
            "email_verified": False,
            "company_domain": "",
            "first_name": "",
            "last_name": "",
            "title": "",
            "enrichment_layers_completed": 0,
        }

        if not self._api_key:
            logger.warning("hunter_no_api_key")
            return result

        # Step 1 — verify the email address
        verification = await self.verify(email)
        result["email_verified"] = verification.get("result") == "deliverable"

        # Step 2 — domain search for company info
        domain = email.split("@")[-1] if "@" in email else ""
        if domain and not self._is_freemail(domain):
            domain_data = await self._domain_search(domain)
            result["company_domain"] = domain
            result["company_name"] = domain_data.get("organization", "")
            result["company_website"] = f"https://{domain}"

            # Try to find the specific person in domain results
            emails_found = domain_data.get("emails", [])
            for entry in emails_found:
                if entry.get("value", "").lower() == email.lower():
                    result["first_name"] = entry.get("first_name", "")
                    result["last_name"] = entry.get("last_name", "")
                    result["title"] = entry.get("position", "")
                    break

            result["enrichment_layers_completed"] = 1

        logger.info(
            "hunter_lookup_complete",
            email=email,
            verified=result["email_verified"],
            domain=result["company_domain"],
        )
        return result

    async def verify(self, email: str) -> dict:
        """Verify a single email address.

        Returns Hunter verification response with 'result' and 'score'.
        """
        if not self._api_key:
            return {"result": "unknown", "score": 0}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{HUNTER_API_BASE}/email-verifier",
                    params={"email": email, "api_key": self._api_key},
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("data", {})
        except Exception as exc:
            logger.error("hunter_verify_failed", email=email, error=str(exc))
            return {"result": "unknown", "score": 0}

    async def _domain_search(self, domain: str) -> dict:
        """Search for all known email addresses at a domain."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{HUNTER_API_BASE}/domain-search",
                    params={"domain": domain, "api_key": self._api_key},
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("data", {})
        except Exception as exc:
            logger.error("hunter_domain_search_failed", domain=domain, error=str(exc))
            return {}

    @staticmethod
    def _is_freemail(domain: str) -> bool:
        """Check if domain is a common freemail provider."""
        freemail_domains = {
            "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
            "aol.com", "icloud.com", "mail.com", "protonmail.com",
            "zoho.com", "yandex.com", "gmx.com", "live.com",
        }
        return domain.lower() in freemail_domains
