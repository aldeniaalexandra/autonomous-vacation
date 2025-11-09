import asyncio
from typing import Dict, Any, Optional


class MockGatewayClient:
    async def authorize(self, amount_minor: int, currency: str, method, details: Dict[str, Any]) -> Dict[str, Any]:
        await asyncio.sleep(0.05)
        return {
            "status": "authorized",
            "authorization_id": "auth_12345",
            "amount_minor": amount_minor,
            "currency": currency,
            "method_label": getattr(method, "label", None),
            "details": details,
        }

    async def capture(self, authorization_id: str) -> Dict[str, Any]:
        await asyncio.sleep(0.05)
        return {"status": "captured", "payment_id": "pay_67890", "authorization_id": authorization_id}

    async def refund(self, payment_id: str, amount_minor: Optional[int] = None) -> Dict[str, Any]:
        await asyncio.sleep(0.05)
        return {"status": "refunded", "payment_id": payment_id, "amount_minor": amount_minor}