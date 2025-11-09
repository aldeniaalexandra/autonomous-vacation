from dataclasses import dataclass
from typing import Optional
import os

from loguru import logger
from src.security.crypto import encrypt_str, decrypt_str, mask_card


@dataclass
class StoredPaymentToken:
    token: str
    masked_pan: str
    brand: Optional[str] = None


class PaymentVault:
    """
    Secure vault for storing payment tokens, not raw card data.
    In production, back this with a PCI-DSS compliant provider or HSM.
    """

    def __init__(self, secret_env_var: str = "ENCRYPTION_SECRET"):
        secret = os.getenv(secret_env_var)
        if not secret:
            raise RuntimeError("ENCRYPTION_SECRET is not set. Configure .env before using PaymentVault.")
        self._secret = secret

    def store_token(self, gateway_token: str, masked_pan: str, brand: Optional[str] = None) -> StoredPaymentToken:
        enc = encrypt_str(gateway_token, self._secret)
        logger.bind(event="payment_token_store").info("Stored encrypted payment token")
        return StoredPaymentToken(token=enc, masked_pan=masked_pan, brand=brand)

    def retrieve_token(self, stored: StoredPaymentToken) -> str:
        token = decrypt_str(stored.token, self._secret)
        logger.bind(event="payment_token_retrieve").info("Retrieved decrypted payment token")
        return token

    @staticmethod
    def mask_pan(card_number: str) -> str:
        return mask_card(card_number)