import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from app import app
from src.database import get_session
from src.audit.store import AuditEvent
import uuid

# Use an in-memory SQLite database for testing
DATABASE_URL = "sqlite:///test_wandergenie.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Dependency override for tests
def get_test_session():
    with Session(engine) as session:
        yield session

@pytest.fixture(name="session")
def session_fixture():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)

@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session
    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

def test_audit_log_is_created_on_hold(client: TestClient, session: Session):
    """Verify that an audit event is created when a hold is placed."""
    response = client.post(
        "/api/autonomous/hold",
        json={
            "user_id": "test-user",
            "amount_minor": 10000,
            "currency": "USD",
            "vendor": "TestVendor",
            "policy": {
                "max_spend_minor": 20000,
                "allowed_vendors": ["TestVendor"],
                "require_two_step_payment": False
            }
        },
    )
    assert response.status_code == 200
    reservation_id = response.json()["reservation_id"]

    # Check that an audit event was recorded
    event = session.query(AuditEvent).filter(AuditEvent.reservation_id == reservation_id).first()
    assert event is not None
    assert event.actor == "test-user"
    assert event.action == "HELD"
    assert event.status == "ok"

def test_idempotent_capture_prevents_duplicates(client: TestClient, session: Session):
    """Ensure that using the same idempotency key for capture results in the same response and no new transaction."""
    # First, create a hold
    hold_response = client.post(
        "/api/autonomous/hold",
        json={
            "user_id": "idempotent-user",
            "amount_minor": 15000,
            "currency": "EUR",
            "vendor": "IdempotentVendor",
            "policy": {
                "max_spend_minor": 20000,
                "allowed_vendors": ["IdempotentVendor"],
                "require_two_step_payment": False
            }
        },
    )
    reservation_id = hold_response.json()["reservation_id"]

    # Then, approve it
    client.post("/api/autonomous/approve", json={"reservation_id": reservation_id})

    # Now, capture with an idempotency key
    idempotency_key = str(uuid.uuid4())
    capture_payload = {
        "user_id": "idempotent-user",
        "reservation_id": reservation_id,
        "idempotency_key": idempotency_key,
    }
    
    first_capture_response = client.post("/api/autonomous/capture", json=capture_payload)
    assert first_capture_response.status_code == 200
    first_tx_id = first_capture_response.json()["transaction_id"]

    # Retry capture with the same idempotency key
    second_capture_response = client.post("/api/autonomous/capture", json=capture_payload)
    assert second_capture_response.status_code == 200
    assert second_capture_response.json()["transaction_id"] == first_tx_id
    assert "idempotent repeat" in second_capture_response.json()["status"]

    # Verify only one capture event was logged
    capture_events = session.query(AuditEvent).filter(
        AuditEvent.reservation_id == reservation_id,
        AuditEvent.action == "CAPTURED"
    ).all()
    assert len(capture_events) == 1

def test_get_audit_events(client: TestClient, session: Session):
    """Test the audit event retrieval endpoint."""
    # Create some events
    client.post("/api/autonomous/hold", json={"user_id": "audit-user-1", "amount_minor": 1000, "currency": "USD", "vendor": "V1", "policy": {"max_spend_minor": 2000, "allowed_vendors": ["V1"], "require_two_step_payment": False}})
    client.post("/api/autonomous/hold", json={"user_id": "audit-user-2", "amount_minor": 2000, "currency": "USD", "vendor": "V2", "policy": {"max_spend_minor": 3000, "allowed_vendors": ["V2"], "require_two_step_payment": False}})

    response = client.get("/api/audit/recent?limit=5")
    assert response.status_code == 200
    events = response.json()
    assert len(events) >= 2

    # Test filtering
    response_filtered = client.get("/api/audit/recent?actor=audit-user-1")
    assert response_filtered.status_code == 200
    events_filtered = response_filtered.json()
    assert len(events_filtered) == 1
    assert events_filtered[0]["actor"] == "audit-user-1"