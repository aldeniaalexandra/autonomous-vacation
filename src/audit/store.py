from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Session, select
from src.database import get_engine


class AuditEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    actor: str = Field(index=True)
    action: str = Field(index=True)  # e.g., PROPOSED, HELD, APPROVED, AUTHORIZED, CAPTURED, CONFIRMED, DENIED, ERROR
    status: str  # e.g., ok, denied, error
    reservation_id: Optional[str] = Field(default=None, index=True)
    amount_minor: Optional[int] = None
    currency: Optional[str] = None
    vendor: Optional[str] = None
    reasons: Optional[str] = None  # pipe-separated reasons for simplicity
    details: Optional[str] = None  # lightweight JSON string if needed


def create_tables():
    engine = get_engine()
    SQLModel.metadata.create_all(engine)


def record_event(actor: str, action: str, status: str, reservation_id: Optional[str] = None,
                 amount_minor: Optional[int] = None, currency: Optional[str] = None,
                 vendor: Optional[str] = None, reasons: Optional[List[str]] = None,
                 details: Optional[Dict[str, Any]] = None) -> AuditEvent:
    engine = get_engine()
    with Session(engine) as session:
        evt = AuditEvent(
            actor=actor,
            action=action,
            status=status,
            reservation_id=reservation_id,
            amount_minor=amount_minor,
            currency=currency,
            vendor=vendor,
            reasons=("|".join(reasons) if reasons else None),
            details=(str(details) if details else None),
        )
        session.add(evt)
        session.commit()
        session.refresh(evt)
        return evt


def list_events(limit: int = 50) -> List[AuditEvent]:
    engine = get_engine()
    with Session(engine) as session:
        stmt = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)
        return list(session.exec(stmt))