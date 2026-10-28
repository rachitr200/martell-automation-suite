---
description: Add handling for a new Stripe event type, with tests
argument-hint: <stripe event type, e.g. invoice.upcoming>
---
Add support for the Stripe event `$ARGUMENTS` in `01-lifecycle-engine`.

1. Read `app/processor.py`. Follow the existing handlers: look up the customer, apply the out-of-order guard (`_is_stale`, `_mark_applied`), change state, then call integrations.
2. Write the handler, register it in `HANDLERS`, and keep every side effect idempotent.
3. Add tests in `tests/test_webhook.py` (happy path, duplicate delivery, out-of-order, and a failing integration that is then retried).
4. Run `python run_tests.py 01` and, with dependencies installed, `uv run pytest`.
5. Summarise the change in three lines for a non-developer: what now happens, what could go wrong, how to check it worked.
