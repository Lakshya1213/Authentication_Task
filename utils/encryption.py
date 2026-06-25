"""
Token encryption helpers using Fernet symmetric encryption.

OAuth tokens are encrypted at rest so a database leak does not expose
plaintext credentials usable against Google APIs.
"""

import logging

from cryptography.fernet import Fernet, InvalidToken

from config import get_settings

logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet:
    settings = get_settings()
    return Fernet(settings.fernet_key.encode())


def encrypt_token(plain_token: str) -> str:
    """
    Encrypt a token string for database storage.

    Raises ValueError if encryption fails.
    """
    if not plain_token:
        raise ValueError("Cannot encrypt empty token")

    try:
        encrypted = _get_fernet().encrypt(plain_token.encode())
        return encrypted.decode()
    except Exception as exc:
        logger.exception("Token encryption failed")
        raise ValueError("Token encryption failed") from exc


def decrypt_token(encrypted_token: str) -> str:
    """
    Decrypt a token retrieved from the database.

    Raises ValueError if decryption fails or token is invalid.
    """
    if not encrypted_token:
        raise ValueError("Cannot decrypt empty token")

    try:
        decrypted = _get_fernet().decrypt(encrypted_token.encode())
        return decrypted.decode()
    except InvalidToken as exc:
        logger.exception("Token decryption failed — invalid or corrupted ciphertext")
        raise ValueError("Token decryption failed") from exc
    except Exception as exc:
        logger.exception("Token decryption failed")
        raise ValueError("Token decryption failed") from exc
