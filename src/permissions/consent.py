from typing import Optional
from pydantic import BaseModel


class ConsentScopes(BaseModel):
    calendar_read: bool = False
    calendar_write: bool = False
    payment_processing: bool = False
    preferences_usage: bool = True


class UserConsent(BaseModel):
    user_id: str
    scopes: ConsentScopes
    oauth_provider: Optional[str] = None  # e.g., 'google', 'microsoft'