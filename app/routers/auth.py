from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from app.core.database import get_db, APIKey
from app.core.auth import create_api_key, hash_key, verify_and_rate_limit
from app.core.config import settings

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr


class UpgradeRequest(BaseModel):
    plan: str  # starter | pro | growth | enterprise


@router.post("/register")
async def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new account and receive a free-tier API key.
    The key is shown ONCE — store it securely.
    """
    # Prevent duplicate emails on free tier (one free key per email)
    existing = db.query(APIKey).filter(APIKey.email == req.email, APIKey.plan == "free").first()
    if existing:
        raise HTTPException(status_code=409, detail="An API key already exists for this email.")

    raw_key = create_api_key(req.email, "free", db)

    return {
        "api_key": raw_key,
        "plan": "free",
        "message": "Store this key securely — it will not be shown again.",
        "docs": "https://yourdomain.com/docs",
    }


@router.post("/upgrade")
async def upgrade(
    req: UpgradeRequest,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_and_rate_limit),
):
    """
    Create a Stripe Checkout session to upgrade the plan.
    Redirects user to Stripe hosted payment page.
    """
    valid_plans = ("starter", "pro", "growth", "enterprise")
    if req.plan not in valid_plans:
        raise HTTPException(status_code=400, detail=f"Plan must be one of: {valid_plans}")

    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Billing not configured yet.")

    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY

        price_id = settings.STRIPE_PRICES.get(req.plan)
        if not price_id:
            raise HTTPException(status_code=400, detail="Enterprise plan requires contacting sales.")

        # Create or reuse Stripe customer
        if not api_key.stripe_customer_id:
            customer = stripe.Customer.create(email=api_key.email)
            api_key.stripe_customer_id = customer.id
            db.commit()

        session = stripe.checkout.Session.create(
            customer=api_key.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url="https://yourdomain.com/dashboard?upgraded=true",
            cancel_url="https://yourdomain.com/pricing",
            metadata={"api_key_prefix": api_key.key_prefix},
        )
        return {"checkout_url": session.url}

    except ImportError:
        raise HTTPException(status_code=503, detail="Install stripe: pip install stripe")


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Stripe sends events here on subscription changes.
    Automatically upgrades/downgrades plan on payment success/failure.
    """
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Billing not configured.")

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    payload = await request.body()
    sig = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        key_prefix = session["metadata"].get("api_key_prefix")
        plan = _plan_from_price(session.get("subscription"))

        if key_prefix and plan:
            db_key = db.query(APIKey).filter(APIKey.key_prefix == key_prefix).first()
            if db_key:
                db_key.plan = plan
                db_key.stripe_subscription_id = session.get("subscription")
                db.commit()

    elif event["type"] == "customer.subscription.deleted":
        sub = event["data"]["object"]
        db_key = db.query(APIKey).filter(
            APIKey.stripe_subscription_id == sub["id"]
        ).first()
        if db_key:
            db_key.plan = "free"
            db_key.stripe_subscription_id = None
            db.commit()

    return {"received": True}


def _plan_from_price(subscription_id: str) -> str:
    """Map Stripe subscription back to a plan name"""
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        sub = stripe.Subscription.retrieve(subscription_id)
        price_id = sub["items"]["data"][0]["price"]["id"]
        for plan, pid in settings.STRIPE_PRICES.items():
            if pid == price_id:
                return plan
    except Exception:
        pass
    return "free"
