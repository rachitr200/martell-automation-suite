# Martell Automation Suite

Eight focused projects plus a connected visual dashboard, demonstrating selected areas of the **AI Automation Developer** job description at
Martell Group. Each is built so you can explain *what it is for, which tools it uses, and why*.

> Deployed portfolio demonstration using synthetic customer data; it has not served real customers.
> The Render dashboard has completed a live Anthropic Claude investigation and produced a retry
> proposal awaiting administrator approval. This does not verify execution of that proposal or
> live Stripe, HubSpot, community-access, Slack, or Anthropic Batch integrations.
> See "What is verified" below.

## Visual dashboard — start here

**Hosted demo:** [Martell Operations Demo](https://martell-operations-demo.onrender.com).

The interface and API are served by the same Render service. The commands below run it locally.

The suite includes a full **frontend connected to a FastAPI backend** in [`09-dashboard`](09-dashboard/README.md).

```bash
# Python 3.12+, from this repository's root
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r 09-dashboard/requirements.txt
python run_dashboard.py
```

Open **http://127.0.0.1:8000**. The dashboard has customer search and timelines, event payload inspection,
access status, failure/retry simulations, revenue charts and four offline AI tools. The offline demo requires no API keys.
Authenticated live Claude investigations require server-side Anthropic configuration; never put API keys in frontend code.
All customer data is synthetic; the portfolio demonstration is available locally and on Render. See the dashboard README for a
five-minute walkthrough, Windows activation, test commands and deployment boundaries.

## Hosting and deployment

[Deploy frontend + Python API on Render](https://render.com/deploy?repo=https://github.com/rachitr200/martell-automation-suite).
The root `render.yaml` configures one Free web service serving both the interface and `/api`.
[Deployment guide](09-dashboard/DEPLOY.md). Free hosting uses ephemeral sample data that reseeds on restart.
The hosted demo above has already been deployed. This deployment link is for creating your own instance.
SQLite data and checkpoints on ephemeral hosting may be lost on redeploy; configure PostgreSQL for durable storage.
A repository update does not establish that the hosted service has deployed that commit.

## Job description -> project

| JD responsibility | Project | Core tools |
| --- | --- | --- |
| Stripe -> CRM -> access pipeline (onboard, upgrade, renew, offboard) | `01-lifecycle-engine` | FastAPI, SQLAlchemy, Alembic, Postgres, Docker, GitHub Actions |
| Daily revenue reporting; customer renewal monitoring | `02-revenue-reporting` | Python, Slack webhook, optional Claude summary |
| Conversation classification via the Anthropic Batch API | `03-ai-batch-classifier` | Anthropic Message Batches, evals, deterministic baseline |
| Dan AI coaching context system "and the evals that keep it honest" | `04-coaching-evals` | Retrieval, citations, guardrails, eval harness |
| HubSpot ops; post-migration cleanup; marketing contact tiers | `05-hubspot-ops` | HubSpot exports, CRM v3 client (in 01) |
| Compliance + deliverability: A2P 10DLC, DKIM/SPF/DMARC | `06-deliverability-compliance` | DNS records, Twilio/SalesMsg registration rules |
| Chrome-extension sales copilot grounded in closed-won patterns | `07-sales-copilot` | Chrome MV3 extension, local API, pattern mining |
| Multiply the team's leverage; prevent the next question | `08-team-leverage` + `CLAUDE.md` + `.claude/commands/` | Claude Code slash commands, request-log ranking |

**Not built** (be upfront): donation/renewal page backends, Vimeo/Zoom/Telegram integrations,
Zapier/Relay.app workflows, MySQL, a GCP deployment, and live Twilio sending.
The webhook + idempotent-handler pattern in project 01 is the template you would reuse for the
video/event integrations.

## Run it

```bash
python run_tests.py          # every dependency-free test (Python 3.12+, standard library only)
python run_tests.py 05       # one project

# Project 01 needs its dependencies:
cd 01-lifecycle-engine && uv sync && uv run pytest
```

Each project has a CLI, for example:
```bash
PYTHONPATH=02-revenue-reporting/src python -m revenue_report.cli \
  --subs 02-revenue-reporting/sample_data/subscriptions.json \
  --invoices 02-revenue-reporting/sample_data/invoices.json --date 2026-10-28
```

## What is verified

| Project | Verified here | Not verified here |
| --- | --- | --- |
| 01 | FastAPI webhook tests, SQLite model behaviour, event processing, signatures, fake integration clients, reconciliation and tracing | Live Stripe/HubSpot/access APIs, PostgreSQL concurrency and standalone lifecycle-service deployment |
| 02 to 06, 08 | All logic and CLIs, through `run_tests.py` | Live Slack delivery, Anthropic Batch processing and live coaching-quality evaluation |
| 07 | Pattern mining, suggestions, a real local HTTP round trip; extension JS syntax and its thread-reading logic against a fake DOM | The extension inside Chrome, and against the real CRM page (selectors are placeholders) |
| 09 | Render-hosted frontend/API; successful live Claude investigation with tool trace, token usage and an approval-pending retry proposal; local approval/recovery and evaluation tests | Execution of that observed live proposal, real customer outcomes, end-to-end external integrations and production capacity |

Documents: `docs/INTERVIEW_GUIDE.md` (how to explain each project), `docs/COMPANY_ANALYSIS.md`
(what the company does and where you could add value).

## Review and validation

An independent local review on October 28, 2026 ran the full supplied pytest suite:
**102 tests passed**, including the lifecycle service and local copilot HTTP round trip.
These tests use fake external integrations and do not establish production capacity.
The original lifecycle module's Ruff check reported 39 findings; lint cleanup remains open.

The initial dashboard update passed **108 tests** (102 existing + 6 dashboard integration tests).
The dashboard tests cover local UI assets, state changes, recovery, revenue, offline AI tools,
request validation, cross-origin protection, reset and persistence. A DOM interaction smoke check
also exercised all six views, simulation/retry and all four tools against the running backend.
A pixel-level browser layout review has not been performed.

The latest recorded local validation for the operations-platform update passed **132 tests**, plus frontend
smoke checks for approval, evaluation and outcome screens. Recovered source also passed Python compilation
and JavaScript syntax checks. These are local results, not a claim of CI success or live-model accuracy.
The seven copilot regression cases run without model calls or external actions.
See [capabilities and evidence](09-dashboard/CAPABILITIES.md) for implementation boundaries.

## Production-readiness priorities

- Configure durable PostgreSQL hosting and verify backups, restores and concurrent processing.
- Extend the existing received-event recovery and retry/backoff logic with durable distributed workers and alerts.
- Verify lifecycle ordering and reconciliation against authoritative provider state.
- Replace the generic access API and placeholder CRM selectors with verified integrations.
- Run live-model evaluations and expand the small evaluation datasets.
- Add load tests, deployment monitoring and verified sandbox integration runs.
- Verify CI results and the deployed commit separately from local test results.

## Project status

Independent portfolio prototype inspired by the published Martell Group role.
Not affiliated with, endorsed by, or deployed for Martell Group.
Sample data and demonstration coaching material are used throughout.

## Operations platform

See [platform setup](09-dashboard/PLATFORM_SETUP.md) for authentication, Claude investigations, durable approvals, knowledge search, MCP, n8n, sandbox connectors and persistence limits.
