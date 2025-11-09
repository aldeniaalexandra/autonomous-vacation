from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional, Dict
from src.main import generate_vacation_plan
import os
from dotenv import load_dotenv
from src.audit.logger import configure_logging
from src.audit.store import create_tables, record_event, list_events
from starlette.middleware.sessions import SessionMiddleware
from src.database import init_db
from src.permissions.consent import UserConsent, ConsentScopes
from src.permissions.oauth import get_oauth
from src.payment.vault import PaymentVault, StoredPaymentToken
from src.payment.processor import PaymentProcessor, PaymentMethod
from src.payment.gateway_mock import MockGatewayClient
from src.booking.automation import process_reservations, send_confirmations
from src.booking.policy import BookingPolicy, check_policy

app = FastAPI(
    title="WanderGenie API",
    description="An AI-powered vacation planner that generates personalized itineraries.",
    version="0.1.0",
)
# Enable server-side sessions required by OAuth client
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "change_me_dev_only"))

templates = Jinja2Templates(directory="templates")

# Ensure environment variables are loaded in server process
@app.on_event("startup")
def _startup():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(dotenv_path=env_path, override=True)
    configure_logging()
    init_db()
    # Ensure audit tables exist
    create_tables()

    # Initialize shared services
    global payment_vault, payment_processor, oauth, CONSENTS, OAUTH_TOKENS, PAYMENT_TOKENS, HOLDS, IDEMPOTENCY, IDEMPOTENCY_CAPTURE
    payment_vault = PaymentVault()
    payment_processor = PaymentProcessor(MockGatewayClient())
    oauth = get_oauth()
    CONSENTS = {}
    OAUTH_TOKENS = {}
    PAYMENT_TOKENS = {}
    HOLDS = {}
    IDEMPOTENCY = {}
    IDEMPOTENCY_CAPTURE = {}

class VacationPreferences(BaseModel):
    destination: str
    duration: int
    budget: str
    interests: List[str]

@app.post("/api/plan", tags=["Vacation Planning"])
async def create_vacation_plan(preferences: VacationPreferences):
    """
    Generates a personalized vacation plan based on user preferences.

    - **destination**: The desired travel destination (e.g., "Paris, France").
    - **duration**: The length of the trip in days (e.g., 7).
    - **budget**: The estimated budget for the trip (e.g., "Budget-friendly", "Moderate", "Luxury").
    - **interests**: A list of interests to tailor the plan (e.g., ["History", "Food", "Adventure"]).
    """
    plan = generate_vacation_plan(preferences.dict())
    return {"plan": plan}


# ----- Permissions & OAuth2 -----
@app.post("/api/consent", tags=["Permissions"])
async def set_consent(consent: UserConsent):
    CONSENTS[consent.user_id] = consent
    return {"status": "ok", "user_id": consent.user_id, "scopes": consent.scopes.dict()}


@app.get("/oauth/login", tags=["OAuth2"])
async def oauth_login(request: Request):
    redirect_uri = os.getenv("OAUTH_REDIRECT_URI")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/oauth/callback", tags=["OAuth2"])
async def oauth_callback(request: Request):
    token = await oauth.google.authorize_access_token(request)
    # In production, associate with authenticated user
    user_id = "demo-user"
    OAUTH_TOKENS[user_id] = token
    return JSONResponse({"status": "ok", "user_id": user_id, "provider": "google"})


# ----- Payments -----
class StoreTokenRequest(BaseModel):
    user_id: str
    gateway_token: str
    last4: str
    brand: Optional[str] = None


@app.post("/api/payment/store-token", tags=["Payments"])
async def store_payment_token(payload: StoreTokenRequest):
    masked_pan = f"**** **** **** {payload.last4}"
    stored: StoredPaymentToken = payment_vault.store_token(payload.gateway_token, masked_pan, payload.brand)
    PAYMENT_TOKENS[payload.user_id] = stored
    return {"status": "ok", "user_id": payload.user_id, "masked_pan": stored.masked_pan, "brand": stored.brand}


class AuthorizePaymentRequest(BaseModel):
    user_id: str
    amount_minor: int
    currency: str


@app.post("/api/payment/authorize", tags=["Payments"])
async def authorize_payment(payload: AuthorizePaymentRequest):
    stored = PAYMENT_TOKENS.get(payload.user_id)
    if not stored:
        return JSONResponse({"error": "no payment token"}, status_code=400)
    token = payment_vault.retrieve_token(stored)
    method = PaymentMethod(type="card", token=token, label=stored.masked_pan)
    res = await payment_processor.authorize(payload.amount_minor, payload.currency, method, details={"user_id": payload.user_id})
    return res


# ----- Booking Automation -----
class BookingRequest(BaseModel):
    user_id: str
    itinerary: List[dict]


@app.post("/api/book", tags=["Booking"])
async def book_itinerary(payload: BookingRequest):
    consent: Optional[UserConsent] = CONSENTS.get(payload.user_id)
    if not consent:
        return JSONResponse({"error": "no consent"}, status_code=400)
    authorized = bool(consent.scopes.payment_processing)
    results = await process_reservations(payload.itinerary, authorized=authorized)
    await send_confirmations(results)
    return {"status": "ok", "results": results}

# ----- Autonomous Booking Controls -----
class HoldRequest(BaseModel):
    user_id: str
    amount_minor: int
    currency: str
    vendor: Optional[str] = None
    policy: BookingPolicy
    idempotency_key: Optional[str] = None


class ApproveRequest(BaseModel):
    reservation_id: str


class CaptureRequest(BaseModel):
    user_id: str
    reservation_id: str
    idempotency_key: Optional[str] = None


@app.get("/api/audit/recent", tags=["Audit"])
async def recent_audit(limit: int = 50, actor: Optional[str] = None, action: Optional[str] = None):
    events = list_events(limit=limit)
    if actor:
        events = [e for e in events if e.actor == actor]
    if action:
        events = [e for e in events if e.action == action]
    return [{
        "id": e.id,
        "created_at": e.created_at.isoformat() + "Z",
        "actor": e.actor,
        "action": e.action,
        "status": e.status,
        "reservation_id": e.reservation_id,
        "amount_minor": e.amount_minor,
        "currency": e.currency,
        "vendor": e.vendor,
        "reasons": e.reasons,
    } for e in events]


@app.post("/api/autonomous/hold", tags=["Autonomous"])
async def autonomous_hold(payload: HoldRequest):
    consent: Optional[UserConsent] = CONSENTS.get(payload.user_id)
    if not consent:
        record_event(actor=payload.user_id, action="PROPOSED", status="error", amount_minor=payload.amount_minor, currency=payload.currency, vendor=payload.vendor, details={"reasons": ["no consent"]})
        return JSONResponse({"error": "no consent"}, status_code=400)

    # Idempotency check
    if payload.idempotency_key:
        existing = IDEMPOTENCY.get(payload.idempotency_key)
        if existing:
            record_event(actor=payload.user_id, action="HELD", status="ok", reservation_id=existing, amount_minor=payload.amount_minor, currency=payload.currency, vendor=payload.vendor, details={"reasons": ["idempotent-return"]})
            return {"status": "HELD", "reservation_id": existing, "idempotent": True}

    # Policy checks
    policy_res = check_policy(payload.amount_minor, payload.currency, payload.vendor, payload.policy)
    if not policy_res["ok"]:
        record_event(actor=payload.user_id, action="PROPOSED", status="denied", amount_minor=payload.amount_minor, currency=payload.currency, vendor=payload.vendor, details={"reasons": policy_res["reasons"]}) 
        return JSONResponse({"status": "denied", "reasons": policy_res["reasons"]}, status_code=400)

    # Create a simple hold record
    reservation_id = f"res_{len(HOLDS) + 1:05d}"
    HOLDS[reservation_id] = {
        "status": "HELD",
        "user_id": payload.user_id,
        "amount_minor": payload.amount_minor,
        "currency": payload.currency,
        "vendor": payload.vendor,
        "require_two_step": payload.policy.require_two_step_payment,
    }
    if payload.idempotency_key:
        IDEMPOTENCY[payload.idempotency_key] = reservation_id
    record_event(actor=payload.user_id, action="HELD", status="ok", reservation_id=reservation_id, amount_minor=payload.amount_minor, currency=payload.currency, vendor=payload.vendor)
    return {"status": "HELD", "reservation_id": reservation_id}


@app.post("/api/autonomous/approve", tags=["Autonomous"])
async def autonomous_approve(payload: ApproveRequest):
    rec = HOLDS.get(payload.reservation_id)
    if not rec:
        return JSONResponse({"error": "no reservation"}, status_code=404)
    rec["status"] = "APPROVED"
    record_event(actor=rec.get("user_id", "unknown"), action="APPROVED", status="ok", reservation_id=payload.reservation_id)
    return {"status": "APPROVED", "reservation_id": payload.reservation_id}


@app.post("/api/autonomous/capture", tags=["Autonomous"])
async def autonomous_capture(payload: CaptureRequest):
    consent: Optional[UserConsent] = CONSENTS.get(payload.user_id)
    if not consent:
        record_event(actor=payload.user_id, action="CAPTURED", status="error", reservation_id=payload.reservation_id, details={"reasons": ["no consent"]})
        return JSONResponse({"error": "no consent"}, status_code=400)
    if not bool(consent.scopes.payment_processing):
        record_event(actor=payload.user_id, action="CAPTURED", status="error", reservation_id=payload.reservation_id, details={"reasons": ["payment_processing scope missing"]})
        return JSONResponse({"error": "payment_processing scope missing"}, status_code=403)

    # Idempotency check for capture
    if payload.idempotency_key:
        existing = IDEMPOTENCY_CAPTURE.get(payload.idempotency_key)
        if existing:
            return {"status": "CONFIRMED", "reservation_id": payload.reservation_id, "payment": existing, "idempotent": True}

    rec = HOLDS.get(payload.reservation_id)
    if not rec:
        return JSONResponse({"error": "no reservation"}, status_code=404)
    if rec.get("status") != "APPROVED":
        return JSONResponse({"error": "reservation not approved"}, status_code=400)

    stored = PAYMENT_TOKENS.get(payload.user_id)
    if not stored:
        return JSONResponse({"error": "no payment token"}, status_code=400)
    token = payment_vault.retrieve_token(stored)
    method = PaymentMethod(type="card", token=token, label=stored.masked_pan)

    auth_res = await payment_processor.authorize(rec["amount_minor"], rec["currency"], method, details={"reservation_id": payload.reservation_id})
    if auth_res.get("status") != "authorized":
        record_event(actor=payload.user_id, action="AUTHORIZED", status="error", reservation_id=payload.reservation_id, amount_minor=rec["amount_minor"], currency=rec["currency"], vendor=rec.get("vendor"))
        return JSONResponse({"error": "authorization failed", "details": auth_res}, status_code=400)

    cap_res = await payment_processor.capture(auth_res["authorization_id"])
    rec["status"] = "CONFIRMED"
    rec["payment_id"] = cap_res.get("payment_id")
    record_event(actor=payload.user_id, action="CAPTURED", status="ok", reservation_id=payload.reservation_id, amount_minor=rec["amount_minor"], currency=rec["currency"], vendor=rec.get("vendor"))
    if payload.idempotency_key:
        IDEMPOTENCY_CAPTURE[payload.idempotency_key] = cap_res
    return {"status": "CONFIRMED", "reservation_id": payload.reservation_id, "payment": cap_res, "idempotent": bool(payload.idempotency_key)}

@app.get("/", response_class=HTMLResponse, tags=["Frontend"])
async def read_root(request: Request):
    """
    Serves the main HTML page of the application.
    """
    return templates.TemplateResponse("index.html", {"request": request})
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)