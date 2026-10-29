"""Test-mode connectors. External writes default to preview-only."""
import hashlib
import hmac
import os
import httpx
from fastapi import HTTPException
from app.integrations.hubspot import HubSpotCRM


def stripe_get(path):
    key = os.getenv('STRIPE_TEST_SECRET_KEY','')
    if not key.startswith('sk_test_'):
        raise HTTPException(503,'Configure STRIPE_TEST_SECRET_KEY with a test-mode key.')
    response = httpx.get('https://api.stripe.com/v1/'+path,auth=(key,''),timeout=15)
    if response.is_error:
        raise HTTPException(502,f'Stripe test API returned HTTP {response.status_code}.')
    data = response.json()
    if data.get('livemode') is True:
        raise HTTPException(409,'Live-mode resources are not allowed.')
    return data


def hubspot_check():
    token = os.getenv('HUBSPOT_TEST_TOKEN','')
    if not token or os.getenv('HUBSPOT_TEST_ACCOUNT') != '1':
        raise HTTPException(503,'Configure a HubSpot test account and HUBSPOT_TEST_TOKEN.')
    response = httpx.get('https://api.hubapi.com/crm/v3/objects/contacts',params={'limit':1},headers={'Authorization':'Bearer '+token},timeout=15)
    if response.is_error:
        raise HTTPException(502,f'HubSpot API returned HTTP {response.status_code}.')
    return {'connected':True,'contact_count_sample':len(response.json().get('results',[]))}


def sync_hubspot(customer, dry_run=True):
    preview = {'stripe_customer_id':customer['id'],'email':customer['email'],'plan':customer['plan'],'status':customer['status']}
    if dry_run:
        return {'dry_run':True,'preview':preview}
    if os.getenv('ALLOW_EXTERNAL_WRITES') != '1' or os.getenv('HUBSPOT_TEST_ACCOUNT') != '1' or not os.getenv('HUBSPOT_TEST_TOKEN'):
        raise HTTPException(503,'External writes are disabled. Configure an explicitly selected HubSpot test account first.')
    HubSpotCRM(os.environ['HUBSPOT_TEST_TOKEN']).upsert_contact(**preview)
    return {'dry_run':False,'synced':True}


def notify(text, dry_run=True):
    if dry_run:
        return {'dry_run':True,'preview':text[:1000]}
    url = os.getenv('SLACK_TEST_WEBHOOK_URL','')
    if os.getenv('ALLOW_EXTERNAL_WRITES') != '1' or not url.startswith('https://hooks.slack.com/services/'):
        raise HTTPException(503,'Test Slack webhook missing or external writes disabled.')
    response = httpx.post(url,json={'text':text[:1000]},timeout=15)
    if response.is_error:
        raise HTTPException(502,'Slack notification failed.')
    return {'sent':True}
