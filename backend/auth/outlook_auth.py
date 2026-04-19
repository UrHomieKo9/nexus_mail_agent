"""Microsoft OAuth2 authentication for Outlook using Authlib."""

from datetime import datetime, timedelta, timezone

import httpx
from authlib.integrations.starlette_client import OAuth
from fastapi import Request
from supabase import create_client

from backend.core.config import settings
from backend.core.logger import get_logger

logger = get_logger("outlook_auth")

# ── OAuth client setup ──

oauth = OAuth()

_outlook_oauth = oauth.register(
    name="outlook",
    client_id=settings.microsoft_client_id,
    client_secret=settings.microsoft_client_secret,
    server_metadata_url=(
        "https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration"
    ),
    client_kwargs={
        "scope": "openid email Mail.Read Mail.Send offline_access",
    },
    authorize_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
    access_token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
    access_token_params={"grant_type": "authorization_code"},
    refresh_token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
)


def get_authorization_url(request: Request, redirect_uri: str) -> str:
    """Generate the Microsoft OAuth2 authorization URL."""
    return _outlook_oauth.authorize_redirect(request, redirect_uri)


async def handle_callback(request: Request) -> dict:
    """Handle the OAuth2 callback and return token data."""
    token = await _outlook_oauth.authorize_access_token(request)
    userinfo = await _outlook_oauth.parse_id_token(request, token)

    return {
        "provider": "outlook",
        "access_token": token.get("access_token"),
        "refresh_token": token.get("refresh_token"),
        "token_type": token.get("token_type", "Bearer"),
        "expires_at": token.get("expires_at"),
        "scope": token.get("scope", ""),
        "email": userinfo.get("email") or userinfo.get("preferred_username"),
        "name": userinfo.get("name"),
    }


def store_tokens(user_id: str, token_data: dict) -> None:
    """Store OAuth tokens in Supabase (encrypted at rest)."""
    supabase = create_client(settings.supabase_url, settings.supabase_service_key)

    record = {
        "user_id": user_id,
        "provider": "outlook",
        "access_token": token_data["access_token"],
        "refresh_token": token_data.get("refresh_token", ""),
        "token_type": token_data.get("token_type", "Bearer"),
        "expires_at": token_data.get("expires_at"),
        "scope": token_data.get("scope", ""),
        "email": token_data.get("email", ""),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    existing = (
        supabase.table("oauth_tokens")
        .select("id")
        .eq("user_id", user_id)
        .eq("provider", "outlook")
        .execute()
    )

    if existing.data:
        supabase.table("oauth_tokens").update(record).eq(
            "id", existing.data[0]["id"]
        ).execute()
        logger.info("outlook_tokens_updated", user_id=user_id)
    else:
        supabase.table("oauth_tokens").insert(record).execute()
        logger.info("outlook_tokens_stored", user_id=user_id)


def get_stored_tokens(user_id: str) -> dict | None:
    """Retrieve stored OAuth tokens from Supabase."""
    supabase = create_client(settings.supabase_url, settings.supabase_service_key)

    result = (
        supabase.table("oauth_tokens")
        .select("*")
        .eq("user_id", user_id)
        .eq("provider", "outlook")
        .execute()
    )

    if not result.data:
        return None

    return result.data[0]


async def refresh_access_token(user_id: str) -> str | None:
    """Refresh the Outlook access token using the stored refresh token.

    Returns the new access token, or None if refresh failed.
    """
    stored = get_stored_tokens(user_id)
    if not stored or not stored.get("refresh_token"):
        logger.error("no_refresh_token", user_id=user_id)
        return None

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            data={
                "client_id": settings.microsoft_client_id,
                "client_secret": settings.microsoft_client_secret,
                "refresh_token": stored["refresh_token"],
                "grant_type": "refresh_token",
                "scope": "Mail.Read Mail.Send offline_access",
            },
        )

    if resp.status_code != 200:
        logger.error("token_refresh_failed", status=resp.status_code, user_id=user_id)
        return None

    token_data = resp.json()
    new_access_token = token_data["access_token"]
    expires_in = token_data.get("expires_in", 3600)

    new_expiry = (
        datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    ).isoformat()

    store_tokens(user_id, {
        "access_token": new_access_token,
        "refresh_token": stored["refresh_token"],
        "token_type": "Bearer",
        "expires_at": new_expiry,
        "scope": stored.get("scope", ""),
        "email": stored.get("email", ""),
    })

    logger.info("outlook_token_refreshed", user_id=user_id)
    return new_access_token


async def get_valid_access_token(user_id: str) -> str | None:
    """Return a valid access token, refreshing if necessary."""
    stored = get_stored_tokens(user_id)
    if not stored:
        return None

    expires_at = stored.get("expires_at")
    if expires_at:
        expiry = datetime.fromisoformat(expires_at)
        if datetime.now(timezone.utc) + timedelta(minutes=5) >= expiry:
            return await refresh_access_token(user_id)

    return stored["access_token"]