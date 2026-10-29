# AI automation capability map

This maps requested job requirements to implementation, not independently verified job listings.

| Capability | Implementation | Limits |
| --- | --- | --- |
| Python APIs and JavaScript UI | FastAPI, same-origin dashboard, Pydantic | Frontend is JavaScript, not TypeScript |
| Stateful agents | LangGraph investigation, approval, execution and verification | ADK, Temporal and Inngest are alternatives, not installed dependencies |
| Checkpointing | SQLite or PostgreSQL checkpointer; restart/approval tests | Render ephemeral SQLite can disappear on redeploy; configure PostgreSQL for durable hosting |
| Structured tools and human override | Validated evidence, customer-scoped tools, administrator approval/rejection | Models cannot directly change money or entitlements |
| Knowledge retrieval | Ingestion, source references, lexical and optional hybrid embeddings/pgvector | Embeddings/database require configuration; copilot search uses lexical retrieval |
| Evaluation | Seven isolated copilot cases; ten classifier cases; mocked-provider contract tests | Not a live-model accuracy benchmark |
| Monitoring | Run history, traces, token counts, latency, optional cost and LangSmith export | Prices need configuration; failed calls may have unrecorded provider usage |
| Business outcomes | Unique recoveries, run failure rate, rejected proposals, manual-baseline estimate | Synthetic data; estimates are not measured production savings |
| Recovery | Idempotency, retry/backoff scheduler, dead events and explicit errors | Single-process scheduler, no silent live-to-offline fallback |
| Business connectors | Signed Stripe test inbox and HubSpot test checks/approved previews | Credentials required; Stripe inbox does not modify entitlements |
| MCP | Authenticated Streamable HTTP read tools | Static bearer token, no OAuth discovery |
| n8n | Importable authenticated triage workflow | Import, credential binding and activation required |
| Async handling | Async webhook body handling and optional background retry loop | Model handlers use the thread pool; durable asynchronous investigation jobs are not implemented |

## Demo

Investigate the seeded failed customer. Review cited events, approve or reject, and verify event/access state. Open Runs & approvals to review Workflow outcomes and click Evaluate copilot workflow. Evaluations use isolated fixtures, make no paid provider calls and do not change customer data.

Optionally set MANUAL_RECOVERY_MINUTES to a documented manual baseline. The estimate multiplies unique recovered events by that baseline; it is not measured time saved. No default fabricated savings are displayed.

## Production work remaining

Managed identity, backups, distributed workers, durable asynchronous investigation jobs, TypeScript migration and held-out live-model evaluations remain separate work. PostgreSQL, semantic embeddings, LangSmith and external connectors need account-specific configuration and validation. See PLATFORM_SETUP.md.
