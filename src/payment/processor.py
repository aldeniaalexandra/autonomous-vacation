from dataclasses import dataclass
from typing import Optional, Dict, Any

from loguru import logger


@dataclass
class PaymentMethod:
    type: str  # 'card' | 'wallet'
    token: str  # gateway token or wallet handle
    label: Optional[str] = None  # masked PAN or wallet id


class PaymentProcessor:
    """
    Abstract payment processor orchestrating authorization, capture, refund.
    Integrate with a gateway client in implementation.
    """

    def __init__(self, gateway_client: Any):
        self.gateway = gateway_client

    async def authorize(self, amount_minor: int, currency: str, method: PaymentMethod, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        logger.bind(event="payment_authorize").info("Authorizing payment")
        return await self.gateway.authorize(amount_minor, currency, method, details or {})

    async def capture(self, authorization_id: str) -> Dict[str, Any]:
        logger.bind(event="payment_capture").info("Capturing payment")
        return await self.gateway.capture(authorization_id)

    async def refund(self, payment_id: str, amount_minor: Optional[int] = None) -> Dict[str, Any]:
        logger.bind(event="payment_refund").info("Refunding payment")
        return await self.gateway.refund(payment_id, amount_minor)