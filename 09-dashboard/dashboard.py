"""Local portfolio dashboard. Uses only synthetic data and offline integrations."""
from __future__ import annotations

import json
import os
import sys
import threading
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "01-lifecycle-engine"))
for source in ROOT.glob("[0-9][0-9]-*/src"):
    sys.path.insert(0, str(source))

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import String, create_engine, func, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.integrations import Integrations
from app.models import Base, Customer, StripeEvent, EventStatus
from app.processor import run_event
from app.reconcile import reconcile
from batch_classifier.baseline import classify_text
from coaching_ai.assistant import CoachingAssistant
from coaching_ai.cli import stub_llm
from coaching_ai.evals import load_cases, run_suite
from coaching_ai.kb import Index, load_dir
from copilot_api.patterns import build_playbook
from copilot_api.suggest import suggest_reply
from revenue_report.metrics import compute_daily_report

STATIC = Path(__file__).parent / "static"
PRICES = {"basic": 9700, "pro": 29700, "annual": 240000}
NAMES = {"cus_a": "Avery Chen", "cus_b": "Jordan Morgan", "cus_c": "Sam Rivera",
         "cus_d": "Taylor Brooks", "cus_e": "Casey Patel", "cus_f": "Alex Kim"}


class DemoMember(Base):
    __tablename__ = "demo_members"
    email: Mapped[str] = mapped_column(String(320), primary_key=True)
    plan: Mapped[str] = mapped_column(String(100))


class DemoContact(Base):
    __tablename__ = "demo_contacts"
    customer_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    email: Mapped[str] = mapped_column(String(320))
    status: Mapped[str] = mapped_column(String(30))
    plan: Mapped[str] = mapped_column(String(100))


class DemoCRM:
    def __init__(self, session):
        self.session = session

    def upsert_contact(self, *, stripe_customer_id, email, plan, status):
        self.session.merge(DemoContact(customer_id=stripe_customer_id,
                                       email=email or "", plan=plan or "basic", status=status))


class DemoAccess:
    def __init__(self, session, fail=False):
        self.session, self.fail = session, fail

    def grant(self, *, email, plan):
        if self.fail:
            raise RuntimeError("Simulated community access outage. Retry to restore delivery.")
        self.session.merge(DemoMember(email=email, plan=plan or "basic"))

    def revoke(self, *, email):
        member = self.session.get(DemoMember, email)
        if member:
            self.session.delete(member)


class Simulation(BaseModel):
    scenario: Literal["checkout", "access_failure", "payment_failed", "payment_recovered", "cancel"]
    customer_id: str | None = Field(default=None, max_length=100)
    plan: Literal["basic", "pro", "annual"] = "pro"


class TextInput(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class ResetInput(BaseModel):
    confirm: Literal[True]


def create_app(database_url: str | None = None):
    # Separate from lifecycle production settings: no .env, credentials or real adapters.
    data_dir = Path(os.environ.get("DEMO_DATA_DIR", str(Path(__file__).parent)))
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "demo.db"
    engine = create_engine(database_url or f"sqlite:///{db_path}",
                           connect_args={"check_same_thread": False})
    sessions = sessionmaker(engine, expire_on_commit=False)
    lock = threading.RLock()  # single-process demo; not a distributed worker lock
    index = Index(load_dir(ROOT / "04-coaching-evals/knowledge"))
    coach = CoachingAssistant(index, stub_llm)
    playbook = build_playbook(json.loads((ROOT / "07-sales-copilot/data/sample_conversations.json").read_text()))

    def integrations(session, fail=False):
        return Integrations(crm=DemoCRM(session), access=DemoAccess(session, fail))

    def insert_event(session, kind, cid, plan="pro", created=None, fail=False):
        latest = session.scalar(select(func.max(StripeEvent.created))) or 0
        created = created if created is not None else max(int(datetime.now(timezone.utc).timestamp()), latest + 1)
        obj = {"customer": cid}
        if kind == "checkout.session.completed":
            obj.update(customer_details={"email": f"{cid}@example.com"}, metadata={"plan": plan},
                       amount_total=PRICES[plan], payment_status="paid")
        if kind == "invoice.paid":
            obj["amount_paid"] = PRICES[plan]
        if kind == "invoice.payment_failed":
            obj["amount_due"] = PRICES[plan]
        event_id = "evt_demo_" + uuid.uuid4().hex[:12]
        payload = {"id": event_id, "type": kind, "created": created,
                   "livemode": False, "data": {"object": obj}}
        session.add(StripeEvent(id=event_id, type=kind, created=created, payload=payload))
        session.commit()
        status = run_event(session, event_id, integrations(session, fail), 5)
        return {"event_id": event_id, "status": status.value}

    def seed():
        with sessions() as session:
            if session.scalar(select(func.count()).select_from(StripeEvent)):
                return
            now = datetime.now(timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0)
            for n, cid in enumerate(NAMES):
                insert_event(session, "checkout.session.completed", cid,
                             "annual" if cid == "cus_b" else "basic" if cid == "cus_e" else "pro",
                             int((now - timedelta(days=6-n)).timestamp()))
            insert_event(session, "invoice.payment_failed", "cus_e", "basic")
            insert_event(session, "customer.subscription.deleted", "cus_d")
            insert_event(session, "checkout.session.completed", "cus_pending", fail=True)

    @asynccontextmanager
    async def lifespan(app):
        Base.metadata.create_all(engine)
        seed()
        yield
        engine.dispose()

    app = FastAPI(title="Martell Operations Demo", lifespan=lifespan)
    app.state.engine = engine
    hosted_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
    allowed_hosts = ["localhost", "127.0.0.1", "testserver"]
    if hosted_hostname:
        allowed_hosts.append(hosted_hostname)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    @app.middleware("http")
    async def protect_demo(request: Request, call_next):
        # Require a non-simple header on mutations; don't allow cross-origin writes.
        if request.method == "POST":
            origin = request.headers.get("origin")
            expected = f"{request.url.scheme}://{request.headers.get('host')}"
            if request.headers.get("x-demo-action") != "1" or (origin and origin != expected):
                return JSONResponse({"detail": "Use this dashboard to perform demo actions."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'"
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/health")
    def health():
        return {"status": "ok", "mode": "synthetic_demo", "live_integrations": False,
                "hosted": bool(hosted_hostname)}

    def event_json(event):
        obj = event.payload["data"]["object"]
        return {"id": event.id, "type": event.type, "created": event.created,
                "customer_id": obj.get("customer"), "email": (obj.get("customer_details") or {}).get("email"),
                "status": event.status.value, "attempts": event.attempts, "error": event.last_error,
                "amount_cents": obj.get("amount_total", obj.get("amount_paid", obj.get("amount_due", 0)))}

    @app.get("/api/dashboard")
    def dashboard():
        with lock, sessions() as session:
            customers = session.scalars(select(Customer).order_by(Customer.id)).all()
            events = session.scalars(select(StripeEvent).order_by(StripeEvent.created.desc())).all()
            members = {m.email: m.plan for m in session.scalars(select(DemoMember)).all()}
            contacts = {c.customer_id: c for c in session.scalars(select(DemoContact)).all()}
            rows, subs, invoices = [], [], []
            today = datetime.now(timezone.utc).date()
            for customer in customers:
                own = [e for e in events if e.payload["data"]["object"].get("customer") == customer.stripe_customer_id
                       and e.status == EventStatus.PROCESSED]
                first = min(e.created for e in own)
                started = datetime.fromtimestamp(first, timezone.utc).date()
                canceled = max((e.created for e in own if e.type == "customer.subscription.deleted"), default=None)
                row = {"id": customer.stripe_customer_id, "name": NAMES.get(customer.stripe_customer_id, "Demo member"),
                       "email": customer.email, "plan": customer.plan, "status": customer.status.value,
                       "access": customer.email in members, "crm_synced": customer.stripe_customer_id in contacts,
                       "monthly_cents": round(PRICES.get(customer.plan, 0) / (12 if customer.plan == "annual" else 1)),
                       "started": started.isoformat()}
                rows.append(row)
                subs.append({"customer_id": row["id"], "plan": row["plan"], "status": row["status"],
                             "amount_cents": PRICES.get(customer.plan, 0), "interval": "year" if customer.plan == "annual" else "month",
                             "started_at": started.isoformat(), "canceled_at": datetime.fromtimestamp(canceled, timezone.utc).date().isoformat() if canceled else None})
            for e in events:
                row = event_json(e)
                if e.status == EventStatus.PROCESSED and e.type in ("checkout.session.completed", "invoice.paid", "invoice.payment_failed"):
                    invoices.append({"customer_id": row["customer_id"], "amount_cents": row["amount_cents"],
                                     "status": "failed" if e.type == "invoice.payment_failed" else "paid",
                                     "created": datetime.fromtimestamp(e.created, timezone.utc).date().isoformat()})
            report = asdict(compute_daily_report(subs, invoices, today))
            chart = [{"day": (today-timedelta(days=n)).isoformat(),
                      "collected_cents": sum(i["amount_cents"] for i in invoices if i["status"] == "paid" and i["created"] == (today-timedelta(days=n)).isoformat())} for n in reversed(range(7))]
            drift = reconcile({c["id"]: c for c in rows},
                              {cid: {"subscription_status": c.status, "subscription_plan": c.plan} for cid,c in contacts.items()}, set(members))
            return {"mode": "synthetic_demo", "currency": "USD", "customers": rows,
                    "hosted": bool(hosted_hostname),
                    "events": [event_json(e) for e in events], "revenue": report, "chart": chart,
                    "issues": [asdict(d) for d in drift], "updated_at": datetime.now(timezone.utc).isoformat()}

    @app.get("/api/events/{event_id}")
    def event_detail(event_id: str):
        with lock, sessions() as session:
            event = session.get(StripeEvent, event_id)
            if not event:
                raise HTTPException(404, "Event not found")
            return {**event_json(event), "payload": event.payload}

    @app.post("/api/simulate")
    def simulate(body: Simulation):
        with lock, sessions() as session:
            if session.scalar(select(func.count()).select_from(StripeEvent)) >= 2000:
                raise HTTPException(409, "Demo limit reached. Reset the demo to start again.")
            new = body.scenario in ("checkout", "access_failure")
            cid = "cus_demo_" + uuid.uuid4().hex[:8] if new else body.customer_id
            if not new:
                customer = session.scalar(select(Customer).where(Customer.stripe_customer_id == cid))
                if not customer:
                    raise HTTPException(404, "Choose an existing customer")
                if customer.status.value == "canceled":
                    raise HTTPException(409, "This subscription is canceled. Simulate a new signup instead.")
                plan = customer.plan
            else:
                plan = body.plan
            kinds = {"checkout": "checkout.session.completed", "access_failure": "checkout.session.completed",
                     "payment_failed": "invoice.payment_failed", "payment_recovered": "invoice.paid", "cancel": "customer.subscription.deleted"}
            return insert_event(session, kinds[body.scenario], cid, plan, fail=body.scenario == "access_failure")

    @app.post("/api/events/{event_id}/retry")
    def retry(event_id: str):
        with lock, sessions() as session:
            event = session.get(StripeEvent, event_id)
            if not event:
                raise HTTPException(404, "Event not found")
            if event.status not in (EventStatus.FAILED, EventStatus.RECEIVED):
                raise HTTPException(409, "Only failed or received events can be retried")
            return {"status": run_event(session, event_id, integrations(session), 5).value}

    @app.post("/api/events/{event_id}/replay")
    def replay(event_id: str):
        with lock, sessions() as session:
            if not session.get(StripeEvent, event_id):
                raise HTTPException(404, "Event not found")
            return {"status": "duplicate", "message": "Event already stored. No duplicate customer or access grant created."}

    @app.post("/api/reset")
    def reset(body: ResetInput):
        with lock:
            Base.metadata.drop_all(engine)
            Base.metadata.create_all(engine)
            seed()
        return {"status": "reset"}

    @app.post("/api/tools/classify")
    def classify(body: TextInput):
        return {"label": classify_text(body.text), "mode": "Offline keyword baseline", "note": "No LLM request was made. Compare this baseline with the separate Anthropic batch module."}

    @app.post("/api/tools/coach")
    def coaching(body: TextInput):
        answer = coach.ask(body.text)
        return {**asdict(answer), "mode": "Offline retrieval demo", "note": "Extracted sample coaching notes, not a live model response or official Dan Martell content."}

    @app.post("/api/tools/copilot")
    def copilot(body: TextInput):
        return {**suggest_reply(playbook, [{"role": "prospect", "text": body.text}]),
                "mode": "Offline sample conversations", "note": "Examples from synthetic closed-won conversations. Review before using; nothing is sent."}

    @app.post("/api/tools/evaluate")
    def evaluate():
        results = run_suite(coach, load_cases(ROOT / "04-coaching-evals/evals/cases.jsonl"))
        return {"mode": "Offline evaluation", "passed": sum(r.passed and not r.skipped for r in results),
                "total": sum(not r.skipped for r in results), "skipped": sum(r.skipped for r in results),
                "cases": [{**asdict(r), "passed": r.passed and not r.skipped} for r in results],
                "note": "Live-model refusal cases are skipped. This measures retrieval and citation checks, not live-model quality."}

    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/")
    def home():
        return FileResponse(STATIC / "index.html")

    return app


app = create_app()
