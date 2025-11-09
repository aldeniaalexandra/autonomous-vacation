from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class BookingPolicy(BaseModel):
    """
    Basic booking policy used to validate proposed reservations before executing.
    - max_budget_minor: maximum amount allowed in minor units (e.g., cents)
    - currency: ISO currency code, e.g., 'USD'
    - allowed_vendors: optional whitelist of vendor names (airlines/hotels)
    - date_window_days: allowable deviation from requested dates
    - require_two_step_payment: if True, use authorize then capture flow
    """
    max_budget_minor: int = Field(default=0, ge=0)
    currency: str = "USD"
    allowed_vendors: Optional[List[str]] = None
    date_window_days: int = 3
    require_two_step_payment: bool = True


def check_policy(amount_minor: int, currency: str, vendor: Optional[str], policy: BookingPolicy) -> Dict[str, Any]:
    """
    Minimal validation against policy. Returns a dict with 'ok' and 'reasons'.
    - Checks budget cap and currency match
    - If allowed_vendors provided, vendor must be in list
    """
    reasons: List[str] = []
    ok = True

    if policy.max_budget_minor and amount_minor > policy.max_budget_minor:
        ok = False
        reasons.append(f"amount {amount_minor} exceeds cap {policy.max_budget_minor}")

    if policy.currency and currency.upper() != policy.currency.upper():
        ok = False
        reasons.append(f"currency {currency} not allowed; expected {policy.currency}")

    if policy.allowed_vendors is not None and vendor is not None:
        if vendor not in policy.allowed_vendors:
            ok = False
            reasons.append(f"vendor {vendor} not in allowed list")

    return {"ok": ok, "reasons": reasons}