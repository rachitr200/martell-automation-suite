# Operations dashboard

A complete local visual demo connected to the suite's Python logic. The frontend is served by FastAPI, with a separate SQLite database and simulated CRM/community providers. No external accounts, API keys, Node build, or paid LLM calls are needed.

## Run (Python 3.12+)

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r 09-dashboard/requirements.txt
python -m uvicorn dashboard:app --app-dir 09-dashboard --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. Keep the terminal running. Windows users can activate with `.venv\Scripts\activate` instead. The persistent database is `09-dashboard/demo.db` (git-ignored). Use **Reset demo** to restore sample data.

## What works

- Overview: current MRR, customers, membership access, event counts and seven-day collections.
- Customers: search, status filters and per-customer event timelines.
- Payment events: search/filter, inspect stored payloads and check duplicate handling.
- Access & recovery: inspect a simulated outage, retry the same event and reconcile local records.
- Revenue: reuse the reporting module with actual local demo customer/event records. USD, illustrative prices; annual plans normalize to monthly MRR. Past-due membership remains in MRR and retains access during dunning.
- AI workspace: keyword classification, cited retrieval from sample coaching documents, replies from sample won conversations, and offline coaching evaluations with live-only cases explicitly skipped.

## A five-minute walkthrough

1. Start at Overview; open the failed signup in **Access & recovery**.
2. Retry it. Watch the new customer, CRM record and membership appear.
3. Simulate a new paid signup. Inspect its payload and customer timeline.
4. Use **Check duplicate guard** on the stored event. No duplicate customer is created.
5. Simulate a failed payment, recover it, then cancel that member. See status/access update.
6. Open Revenue to see changing MRR and collections. Try all four AI tools.

## Architecture and boundaries

Browser → same-origin `/api/*` → FastAPI → existing lifecycle processor / reporting / AI tools → SQLite.

The dashboard uses the existing lifecycle `Customer`, `StripeEvent` and `run_event` code. Its two extra tables persist the simulated CRM contacts and community memberships. Unlike real remote APIs, these local simulated side effects participate in the SQLite transaction. This intentionally makes a reliable demo; it does not prove distributed side-effect atomicity.

The simulation endpoint feeds synthetic events directly to the processor; it does not exercise Stripe signature verification. Use the original lifecycle service and its tests for webhook signature handling. **Check duplicate guard** acknowledges a known event without reprocessing; it is not a live Stripe redelivery test.

AI tools are explicitly offline: the coach extracts retrieved notes using the existing stub; no generative model runs. The classifier is the existing keyword baseline. The separate Anthropic adapters remain available in their original modules.

This is local-only demo software, not a production admin portal. It binds to loopback, restricts hosts, blocks cross-origin writes, and uses a dedicated demo DB. It has no user login or production authentication. Do not expose it with real customer data. It does not inherit `.env` credentials or call live integrations. Use one server worker: a process-local lock serializes demonstration mutations. The 2,000-event limit keeps the in-memory dashboard calculations bounded. Existing production-readiness issues documented in the root README remain open.

## Test

```bash
python -m pip install -r 09-dashboard/requirements-dev.txt
python -m pytest -q
```

The new tests exercise signup/failure/retry/cancellation, status changes, revenue, offline AI tools, cross-origin protection, reset, static assets and database persistence. They need pytest fixtures, so the suite's dependency-free runner skips them.
