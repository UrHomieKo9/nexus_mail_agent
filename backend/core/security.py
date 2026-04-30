"""Encryption and security utilities for sensitive data."""

import base64
import hashlib
from cryptography.fernet import Fernet
from backend.core.config import settings

def _get_encryption_key() -> bytes:
    """Get or derive a 32-byte base64 encoded key for Fernet."""
    if settings.encryption_key:
        return settings.encryption_key.encode()
    
    # Derive a key from app_secret_key if no specific encryption key is provided
    # This ensures consistency across restarts if the secret key stays the same
    key_hash = hashlib.sha256(settings.app_secret_key.encode()).digest()
    return base64.urlsafe_b64encode(key_hash)

def encrypt_token(token: str | None) -> str:
    """Encrypt a sensitive token string."""
    if not token:
        return ""
    
    f = Fernet(_get_encryption_key())
    return f.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str | None) -> str:
    """Decrypt an encrypted token string."""
    if not encrypted_token:
        return ""
    
    try:
        f = Fernet(_get_encryption_key())
        return f.decrypt(encrypted_token.encode()).decode()
    except Exception:
        # Fallback for old plaintext tokens during migration or if key is wrong
        return encrypted_token
