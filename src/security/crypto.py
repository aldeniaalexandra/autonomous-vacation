import base64
import os
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def _derive_key(secret: str, salt: Optional[bytes] = None) -> bytes:
    """
    Derive a Fernet-compatible key from a secret using PBKDF2-HMAC.
    For demo purposes, salt is static if not provided. In production, use per-record salt.
    """
    if salt is None:
        salt = b"wandergenie-static-salt"
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=salt, iterations=390000
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret.encode("utf-8")))
    return key


def get_fernet(secret: str) -> Fernet:
    key = _derive_key(secret)
    return Fernet(key)


def encrypt_str(plain: str, secret: str) -> str:
    f = get_fernet(secret)
    return f.encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_str(token: str, secret: str) -> str:
    f = get_fernet(secret)
    return f.decrypt(token.encode("utf-8")).decode("utf-8")


def mask_card(card_number: str) -> str:
    """
    Return masked PAN, keeping last 4 digits visible (e.g., **** **** **** 1234).
    """
    last4 = card_number[-4:] if len(card_number) >= 4 else card_number
    return f"**** **** **** {last4}"