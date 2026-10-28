---
description: Find where a customer's data diverged between Stripe, the CRM, and community access
argument-hint: <stripe customer id or email>
---
Investigate customer `$ARGUMENTS`. Work from the payment outward and stop at the first seam that is wrong.

1. Stripe: what is their subscription status and plan right now?
2. Our event log: call `GET /trace/<stripe_customer_id>` (needs the admin token) or query `stripe_events`. List events in `created` order with status and attempts. Look for `failed` or `dead`, and for an older event processed after a newer one.
3. CRM: do `subscription_status` and `subscription_plan` on the contact match Stripe?
4. Access: is their email a member, and should it be (see `GRANTS_ACCESS` in `01-lifecycle-engine/app/reconcile.py`)?

Report in this shape: **What is true now** (per system), **Where it first diverges**, **Why** (the likely cause), **Safe fix** (retry an event, or a specific manual correction), and **How to check this yourself next time** in two sentences a non-developer can follow. Do not change anything; propose the fix.
