from fastapi import Request

from app.config import get_settings
from app.integrations import Integrations, NoopAccess, NoopCRM


async def raw_body(request: Request) -> bytes:
    # Signature verification needs the exact bytes Stripe sent, not re-serialised JSON.
    return await request.body()


def get_integrations() -> Integrations:
    settings = get_settings()
    crm = NoopCRM()
    access = NoopAccess()
    if settings.hubspot_token:
        from app.integrations.hubspot import HubSpotCRM

        crm = HubSpotCRM(settings.hubspot_token)
    if settings.access_api_base:
        from app.integrations.rest_access import RestAccessProvider

        access = RestAccessProvider(settings.access_api_base, settings.access_api_token)
    return Integrations(crm=crm, access=access)
