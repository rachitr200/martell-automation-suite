# Publish the frontend and Python API

Deploy both in one Render web service. FastAPI serves `/` and `/static/*`; the browser calls that same service at `/api/*`. No localhost URL, separate API domain or CORS setting needs to be added to the frontend. Python still owns the business logic.

## Deploy

1. Open https://render.com/deploy?repo=https://github.com/rachitr200/martell-automation-suite
2. Sign in to Render and authorize this repository if asked.
3. Review the Blueprint: one Python web service named `martell-operations-demo`, on the Free plan. Deploy the Blueprint.
4. Wait for the build and for the service to show **Live**. Open the exact URL shown by Render; the name can gain a suffix if already in use.
5. Visit `/api/health` at that URL and check for `status: ok`. Test simulation, recovery and AI tools on the main dashboard before sharing its URL.

No API keys or paid AI calls are required. The root `render.yaml` supplies the build/start commands, Python version and health check. Keep the repository root as the service root: the dashboard imports the other project modules.

## Manual service creation

| Setting | Value |
| --- | --- |
| Repository | `rachitr200/martell-automation-suite` |
| Branch | `main` |
| Language | Python 3 |
| Root Directory | Leave blank |
| Build command | `pip install -r 09-dashboard/requirements.txt` |
| Start command | `uvicorn dashboard:app --app-dir 09-dashboard --host 0.0.0.0 --port $PORT --workers 1 --proxy-headers --forwarded-allow-ips '*'` |
| Health check | `/api/health` |
| Environment | `PYTHON_VERSION=3.12.13` |
| Instance | Free |

Render automatically supplies `RENDER_EXTERNAL_HOSTNAME`, which the app adds to its trusted hosts. Proxy headers enable HTTPS-origin validation behind Render's proxy. Keep one worker: this is a small, serialized SQLite demo.

## Data and sharing

This public app contains only synthetic records. Visitors share its demo dataset and can reset it. It has no login and is not a private customer-management system. Do not enter real customer information or integration credentials.

Free Render services spin down after inactivity. Their SQLite data is lost on spin-down, restart or deploy; the app reseeds the sample dataset on startup. The first visit after idle may take around a minute to start. This configuration suits portfolio demos, not durable business records.

Persistent sample data is optional: choose a paid instance with an attached disk and set `DEMO_DATA_DIR` to its mount directory. That may incur charges. The supplied Blueprint provisions no paid disk or database.

## Troubleshooting

- **Invalid host header:** use Render's assigned URL. A custom domain needs an explicit trusted-host update.
- **Module not found:** leave Root Directory blank; install `09-dashboard/requirements.txt` from the repository root.
- **No open port:** use `$PORT` and host `0.0.0.0`.
- **API fails:** inspect `/api/health` and Render logs. The frontend and API must be served by the same FastAPI service.
- **Demo data disappears:** expected on Free hosting; see above.

Official references: https://render.com/docs/deploy-fastapi and https://render.com/docs/free

## Operations platform

See [platform setup](PLATFORM_SETUP.md) for authentication, Claude investigations, durable approvals, knowledge search, MCP, n8n, sandbox connectors and persistence limits.
