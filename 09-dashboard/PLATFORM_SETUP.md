# Operations platform setup

Render → martell-operations-demo → Environment. Save variables and redeploy. Never commit credentials or put them in frontend JavaScript.

| Variable | Purpose |
| --- | --- |
| ADMIN_EMAIL | Administrator login email |
| ADMIN_PASSWORD | Unique password, at least 12 characters |
| ANTHROPIC_API_KEY | Claude credential for live investigations |
| ANTHROPIC_MODEL | Exact model ID enabled in your account |
| OPERATOR_EMAIL / OPERATOR_PASSWORD | Optional investigator account, password at least 12 characters |
| DATABASE_URL | PostgreSQL URL for durable data; otherwise SQLite |
| OPENAI_API_KEY | Optional embeddings; lexical search needs no key |
| EMBEDDING_MODEL | Defaults to text-embedding-3-small; must support 1536 dimensions |
| MCP_READ_TOKEN | Random bearer token for read-only MCP |
| AUTOMATION_TOKEN | Different random bearer token for n8n classification |
| MAX_LIVE_RUNS_PER_DAY | Global live investigation limit, default 20 |
| INPUT_PRICE_PER_MILLION / OUTPUT_PRICE_PER_MILLION | Optional model prices for cost estimates |
| LANGSMITH_TRACING / LANGSMITH_API_KEY | Optional true plus key enables metadata-only export |
| RECOVERY_WORKER_ENABLED | Optional 1 enables scheduled retries; disabled by default |

Open Setup & access and sign in. Readiness reports key presence, not verified connectivity. Start with an offline investigation of cus_pending. Claude mode makes billed provider requests explicitly; failures appear as failed runs rather than substituted offline answers.

## Roles and approvals

Viewers see synthetic dashboard data. Operators investigate, search documents and propose actions. Administrators also ingest documents, inspect audit history and approve/reject proposals with a reason. ADMIN_PASSWORD protects the original simulation/reset/retry controls. Without it, those legacy synthetic controls remain public; new platform operations still require login.

Models cannot directly change money or access. Deterministic execution revalidates approved proposals. Repeated decisions are rejected. Reset clears demo customers/events while preserving sessions, audit history, documents and runs.

## Persistence

The existing Render free filesystem is ephemeral. SQLite data and LangGraph checkpoints can disappear on redeployment. Provision PostgreSQL separately and set DATABASE_URL for durability. No paid resource is created automatically. Startup runs Alembic; the initial revision adopts existing tables. Future schema changes need explicit migrations. Run a single application worker; the scheduler is not a distributed queue.

Optional pgvector: the database owner runs pgvector.sql before setting PGVECTOR_ENABLED=1. Reingest documents with semantic indexing selected. Without pgvector, optional embeddings use JSON storage and Python scoring. Lexical retrieval is the default. Embeddings incur API usage. Sample notes are fictional portfolio policies.

## Sandbox connectors

STRIPE_TEST_SECRET_KEY must start sk_test_ and is used for a read-only check. STRIPE_TEST_WEBHOOK_SECRET verifies /api/connectors/stripe/webhook. Only signed test-mode events are recorded in a sandbox inbox; they do not change demo entitlements.

HUBSPOT_TEST_TOKEN and HUBSPOT_TEST_ACCOUNT=1 must identify a dedicated test account. Proposals have dry-run previews. An approved write additionally requires ALLOW_EXTERNAL_WRITES=1; leave it unset until reviewed. Connection checks read one contact. Before an approved HubSpot sync, create contact properties stripe_customer_id, subscription_plan and subscription_status in the test account. Slack has a preview endpoint; dashboard actions do not send messages.

## MCP and n8n

Streamable HTTP endpoint: https://martell-operations-demo.onrender.com/mcp/.
Use Authorization: Bearer <MCP_READ_TOKEN> in a client supporting custom headers. Tools: get_customer, list_failed_events, search_operations_knowledge; all read-only. OAuth discovery/registration is not implemented, so OAuth-only client compatibility is not claimed.

Import integrations/n8n/customer-triage.json into n8n. It is inactive and contains no credentials. Assign Header Auth credentials to both the inbound webhook and outbound HTTP Request node. Outbound header: Authorization; value: Bearer <AUTOMATION_TOKEN>. The workflow calls /api/automation/classify and returns a human-review item. It does not send messages or update CRM records. Test before activating.

## Validation limits

The evaluation button runs ten deterministic classification cases, not a live-model accuracy benchmark. Mocked-provider tests cover structured output and invalid evidence. Recorded token usage and optional cost estimates are not a billing ledger. Real provider calls and PostgreSQL operation require separate credentialed validation. Production still needs managed identity, monitoring, backups and distributed workers.

For local use, export variables before starting uvicorn; .env files are not automatically loaded.
