# How to explain each project

For each: the 30-second version, the tools and *why those tools*, one design decision worth
defending, and the honest limit. Lead with the problem, not the technology.

## 01 Lifecycle engine (the centrepiece)
**30 seconds.** "Payments are the source of truth for who is a customer, but Stripe delivers
events at least once and out of order. This service verifies each webhook, stores it once, applies
it to a customer record, then updates the CRM and community access. If a downstream system is down,
the event is recorded as failed and retried, and a nightly reconciliation compares Stripe, the CRM
and access to catch drift."

**Tools and why.** FastAPI (typed, async-capable web layer, easy tests); Pydantic settings (config
validated at start); SQLAlchemy + Alembic (portable models and versioned schema changes); Postgres
(transactions are what make "state change and event status commit together" true); Docker and
GitHub Actions (same build locally and in CI).

**Decisions to defend.**
- *Event id as primary key* gives idempotency for free: a replay hits the constraint.
- *Out-of-order guard*: each customer stores the newest Stripe `created` applied; older events are dropped, so a late "active" update cannot resurrect a cancelled customer.
- *Always return 200 once stored.* Retries are owned by us; letting Stripe also retry would duplicate work.
- *Integrations behind interfaces*: handlers never know HubSpot exists, so tests need no network.

**Honest limits.** Side effects (HubSpot, access) are not inside the database transaction, so
they must be idempotent (they are: "already a member" counts as success). Two simultaneous first
events for a new customer can race on the unique row; one fails, is recorded, and succeeds on retry.
The community-platform client is written against an assumed REST shape and must be mapped to the real API.

## 02 Revenue reporting and renewal monitoring
**30 seconds.** "A daily message for the CEO: MRR, new, churned, collected, failed, plus the
renewals coming up and the subscriptions set to cancel, and plain-language flags when something
moved abnormally."
**Why this design.** All numbers come from tested pure functions; the optional LLM paragraph only
*describes* them and is told not to add figures, so it cannot change a number. Annual plans are
normalised to monthly; trials are excluded from MRR.
**Limit.** It works on snapshots, so it cannot see expansion or contraction revenue unless you also supply plan-change history.

## 03 Batch classification
**30 seconds.** "Classify a backlog of conversations into intent labels using the Message Batches
API, which processes asynchronously at lower cost, and score it against a labelled set."
**Why.** Batch suits bulk, non-urgent work. The pipeline depends on a small backend interface, so tests use a fake and production swaps in the real client. Results are never silently dropped: errors, expiries and missing results become visible statuses.
**The point to make.** The keyword baseline scores 79% on the eval set and fails in instructive ways (it reads "is the *book* included?" as a booking intent). That is what justifies the LLM, and it is the "when to use a script versus a model" answer in numbers.
**Limit.** The Anthropic backend was not run against the live API here; try a 3-conversation batch first.

## 04 Coaching assistant with evals
**30 seconds.** "An assistant that answers only from a coaching knowledge base, cites every claim, and refuses when it has nothing relevant, with an eval suite that gates changes."
**Decisions.** Guardrails in code, not just in the prompt (an irrelevant question never reaches the model). Citations are validated: an id the model cites that was not retrieved is flagged. Evals are split: deterministic ones (retrieval, citations, fabrication tripwires) run in CI; model-behaviour ones (does it decline?) run with `--live`, because they cost money and vary.
**An honest finding to share.** My first relevance gate looked fine but failed on two out-of-scope questions; a single shared generic word scored as high as real matches. I measured it, concluded lexical overlap cannot cleanly separate scope on a small corpus, and moved that judgement to the live evals instead of tuning a threshold to fit ten examples.
**Limit.** The knowledge base is invented sample content; retrieval is TF-IDF, which is the first thing to swap for embeddings.

## 05 HubSpot ops
**30 seconds.** "After a CRM migration you inherit sprawl: unused and duplicated properties, dead workflows, and marketing contacts you pay for but never email. These read-only tools find them and estimate the saving."
**Decision.** It recommends and exports; it does not write. It never recommends demoting customers or contacts with open deals. Tier size and price are inputs because contracts differ.
**Limit.** Works on exports; I did not assume an API for changing marketing status.

## 06 Deliverability and A2P compliance
**30 seconds.** "Checks SPF, DKIM and DMARC records and validates an SMS campaign registration before submission, because a rejected 10DLC campaign costs days."
**Details to know.** SPF allows 10 DNS lookups (includes, a, mx, ptr, exists, redirect), and `+all` or a bare `all` authorises anyone; DMARC `p=none` only monitors; a DKIM key's strength can be estimated from its decoded length. The A2P rules are common review criteria, not a guarantee; check Twilio's current docs.
**Limit.** SPF lookup counting is top-level only; nested includes also count toward the limit.

## 07 Sales copilot
**30 seconds.** "Mines closed-won versus closed-lost conversations for phrases and objection replies that actually preceded wins, then suggests replies in the CRM inbox, with a person always choosing what to send."
**Decisions.** Suggestions without an LLM are real replies from won deals (auditable). With an LLM, it drafts from those examples and is told not to invent prices or guarantees. The service makes the network call from the extension's background worker, and the panel renders text with `textContent`, never `innerHTML`.
**Limits.** Selectors are placeholders for the real CRM's DOM. Mined patterns are correlation, not causation, and small samples mislead; the support floor helps but does not remove that. The API has no auth and binds to localhost; add authentication before hosting it, since threads are customer data.

## 08 Team leverage
**30 seconds.** "The role is not a help desk. Log every request, rank by total time, and match the fix to the pattern: FAQ, how-to, or a tool/slash command. `CLAUDE.md` and the slash commands give colleagues' own Claude sessions the rules."

## Questions to expect, and short answers
- *How do you know a webhook wasn't missed?* Reconciliation compares systems nightly; the event log shows gaps; Stripe's dashboard can resend.
- *Where would an agent be wrong here?* Anywhere money or access changes. Agents draft and classify; code and people decide.
- *What would you do in your first month?* Read the event and failure history, run reconciliation, and fix the highest-cost seam before adding features.
