---
description: Review failed and dead webhook events and recommend what to do with each
---
List events in `stripe_events` with status `failed` or `dead`, newest first. Group them by `last_error`.

For each group say: how many events, which customers, the probable root cause (downstream outage, missing CRM property, missing email, bad credentials), and the action:
- transient (timeouts, 429, 5xx): call `POST /admin/retry` once the dependency is healthy
- data problem (missing email, unknown property): fix the data, then reset the event with `UPDATE stripe_events SET status='failed', attempts=0 WHERE id='...'` and retry
- code bug: write a failing test first, then fix it

Never retry in a loop, and never mark an event processed by hand.
