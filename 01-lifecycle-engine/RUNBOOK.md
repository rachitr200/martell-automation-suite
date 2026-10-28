# Runbook

## A customer paid but has no access

1. Find their events:
   `SELECT id, type, status, attempts, last_error FROM stripe_events
    WHERE payload->'data'->'object'->>'customer' = 'cus_XXX' ORDER BY created;`
2. Read `status` and `last_error`:
   - `processed`: our side succeeded. Check the access provider directly.
   - `failed`: it will be retried. Fix the cause (usually a downstream outage), then
     `curl -X POST -H "x-admin-token: $ADMIN_TOKEN" https://<host>/admin/retry`.
   - `dead`: out of attempts. Fix the cause, then reset it:
     `UPDATE stripe_events SET status='failed', attempts=0 WHERE id='evt_XXX';` and call retry.
   - no row: Stripe never reached us. Check the endpoint in the Stripe dashboard and its delivery
     log, then resend the event from there.
3. If `last_error` mentions "no email", the checkout had no customer email; fix the customer in
   Stripe and resend the event.

## Stripe says deliveries are failing

- HTTP 400: signature problem. Confirm `STRIPE_WEBHOOK_SECRET` matches the endpoint's secret
  (each endpoint and each Stripe CLI listener has its own).
- HTTP 500 "Webhook secret not configured": the env var is missing.

## An event was processed but state looks wrong

Out-of-order protection can drop an older event on purpose. Compare the event's `created` with
`customers.last_event_created`: if the event is older, it was correctly skipped.
