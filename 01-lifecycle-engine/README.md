# Lifecycle Engine

Turns Stripe payment events into an automated customer lifecycle: onboarding, upgrades, renewals
and offboarding across a CRM and a community/access platform. It is built so that when data goes
missing, you can find out where and why in minutes.

## The problem

Payment events are the source of truth for who is a customer, but they arrive at-least-once, out
of order, and sometimes while a downstream system (CRM, community platform) is down. Naive
webhook handlers double-grant access, resurrect canceled customers, or silently drop events.

## What this does about it

| Concern | Approach |
| --- | --- |
| Forged or replayed requests | HMAC signature check on the raw body, with a timestamp tolerance |
| Duplicate delivery | Event id is the primary key; a replay hits the constraint and is acknowledged as `duplicate` |
| Out-of-order delivery | Each customer remembers the newest Stripe `created` it applied; older events are dropped |
| Downstream outage | Failure is recorded on the event (`failed`), DB changes are rolled back, and it is retried; after `MAX_ATTEMPTS` it becomes `dead` for a human |
| Stripe retry storms | Once stored, the endpoint always returns 200; retries are owned by this service |
| Partial state | Business-state changes and the event's `processed` status commit in one transaction |

## Flow

```
Stripe --webhook--> POST /webhooks/stripe
                      verify signature -> store event (idempotent) -> dispatch handler
                                                                        |-- update customer row
                                                                        |-- CRM.upsert_contact
                                                                        '-- Access.grant / revoke
                      failure -> event.status = failed -> POST /admin/retry -> ... -> dead
```

Handled events: `checkout.session.completed`, `invoice.paid`, `invoice.payment_failed`,
`customer.subscription.updated`, `customer.subscription.deleted`. Anything else is stored and
marked `ignored`, so the event log stays complete.

## Run it

```bash
uv sync
uv run pytest            # tests use in-memory SQLite

cp .env.example .env     # set STRIPE_WEBHOOK_SECRET
docker compose up --build
# forward real events with the Stripe CLI:
stripe listen --forward-to localhost:8000/webhooks/stripe
```

## Design decisions

- **Deterministic code owns money and access.** Nothing probabilistic sits in the payment path.
  The planned AI features (below) read from the event log and never write to customer state.
- **Integrations are interfaces.** Handlers call `CRM` and `AccessProvider` protocols
  (`app/integrations/base.py`). Real clients must be idempotent, because a crash between a side
  effect and the commit means the handler can run twice.
- **Signature check uses the stdlib**, not the Stripe SDK, so the logic is small and fully unit
  tested.
- **Known limit:** two simultaneous first events for a brand-new customer can race on the unique
  customer row. One fails, is recorded, and succeeds on retry.

## Status and roadmap

- [x] Webhook receiver, signature verification, idempotent event log
- [x] Customer state machine with out-of-order protection
- [x] Failure tracking, retry, dead-letter status, admin retry endpoint
- [x] Alembic migration, Docker, CI
- [x] HubSpot CRM v3 contact client (`app/integrations/hubspot.py`), tested with a fake transport; create the three custom properties in HubSpot first
- [x] Generic REST access provider (`app/integrations/rest_access.py`); map it to the real platform's API
- [x] `GET /trace/{stripe_customer_id}`: ordered event history plus current state (admin-only)
- [x] Nightly reconciliation logic across Stripe, CRM and access (`app/reconcile.py`); fetching the snapshots is not built
- [ ] Slack alert when an event goes `dead`
- [x] Conversation classifier: see `../03-ai-batch-classifier`
- [x] Daily revenue report: see `../02-revenue-reporting`
- [ ] Deploy to Cloud Run

See `RUNBOOK.md` for what to do when something breaks.

## Configuration for real integrations
Set `HUBSPOT_TOKEN` to use the HubSpot client, and `ACCESS_API_BASE` / `ACCESS_API_TOKEN` for the access provider.
With them empty, handlers use logging no-ops, so the service runs locally with no external accounts.
