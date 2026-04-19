"""Apollo.io — L2 company and contact data enrichment."""

import httpx

from backend.core.config import settings
from backend.core.logger import get_logger

logger = get_logger("apollo")

APOLLO_API_BASE = "https://api.apollo.io/v1"


class ApolloEnrichment:
    """Layer-2 enrichment: company + contact data via Apollo.io."""

    def __init__(self):
        self._api_key = settings.apollo_api_key

    async def lookup(self, email: str, domain: str = "") -> dict:
        """L2 enrichment: fetch company + contact details from Apollo.

        Args:
            email: Contact email address.
            domain: Company domain (from Hunter L1).

        Returns:
            Dict compatible with EnrichmentData fields.
        """
        result: dict = {}

        if not self._api_key:
            logger.warning("apollo_no_api_key")
            return result

        # Step 1 — People enrichment (by email)
        person = await self._enrich_person(email)
        if person:
            result["first_name"] = person.get("first_name", "")
            result["last_name"] = person.get("last_name", "")
            result["title"] = person.get("title", "")
            result["linkedin_url"] = person.get("linkedin_url", "")

            org = person.get("organization", {})
            if org:
                result["company_name"] = org.get("name", "")
                result["company_size"] = self._format_size(
                    org.get("estimated_num_employees")
                )
                result["industry"] = org.get("industry", "")
                result["funding_stage"] = org.get("funding_stage", "")
                result["estimated_arr"] = org.get("annual_revenue_printed", "")
                result["company_website"] = org.get("website_url", "")

        # Step 2 — Organization enrichment (by domain, if person didn't yield org)
        if domain and "company_name" not in result:
            org_data = await self._enrich_organization(domain)
            if org_data:
                result["company_name"] = org_data.get("name", "")
                result["company_size"] = self._format_size(
                    org_data.get("estimated_num_employees")
                )
                result["industry"] = org_data.get("industry", "")
                result["funding_stage"] = org_data.get("funding_stage", "")
                result["estimated_arr"] = org_data.get("annual_revenue_printed", "")
                result["company_website"] = org_data.get("website_url", "")

        if result:
            result["enrichment_layers_completed"] = 2

        logger.info(
            "apollo_lookup_complete",
            email=email,
            has_person=bool(person),
            has_company="company_name" in result,
        )
        return result

    async def _enrich_person(self, email: str) -> dict | None:
        """Enrich a person by email using Apollo People API."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{APOLLO_API_BASE}/people/match",
                    headers={"X-Api-Key": self._api_key},
                    json={"email": email},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("person")
        except Exception as exc:
            logger.error("apollo_person_failed", email=email, error=str(exc))
        return None

    async def _enrich_organization(self, domain: str) -> dict | None:
        """Enrich an organization by domain."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{APOLLO_API_BASE}/organizations/enrich",
                    headers={"X-Api-Key": self._api_key},
                    json={"domain": domain},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("organization")
        except Exception as exc:
            logger.error("apollo_org_failed", domain=domain, error=str(exc))
        return None

    @staticmethod
    def _format_size(num_employees: int | None) -> str:
        """Format employee count into a human-readable size bracket."""
        if not num_employees:
            return ""
        if num_employees < 10:
            return "1-10"
        if num_employees < 50:
            return "11-50"
        if num_employees < 200:
            return "51-200"
        if num_employees < 1000:
            return "201-1000"
        if num_employees < 5000:
            return "1001-5000"
        return "5000+"
