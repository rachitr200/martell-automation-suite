import importlib.util
import json
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

MODULE=Path(__file__).resolve().parents[1]/'dashboard.py'
# Use the already-imported module to avoid re-declaring shared SQLAlchemy tables.
if 'operations_dashboard' in sys.modules:
    module=sys.modules['operations_dashboard']
else:
    spec=importlib.util.spec_from_file_location('operations_dashboard',MODULE)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
HEADERS={'X-Demo-Action':'1'}


@pytest.fixture
def env(tmp_path,monkeypatch):
    monkeypatch.setenv('DEMO_DATA_DIR',str(tmp_path))
    monkeypatch.setenv('ADMIN_EMAIL','admin@example.com')
    monkeypatch.setenv('ADMIN_PASSWORD','test-password-12345')
    monkeypatch.setenv('OPERATOR_EMAIL','operator@example.com')
    monkeypatch.setenv('OPERATOR_PASSWORD','operator-password-12345')
    monkeypatch.delenv('ANTHROPIC_API_KEY',raising=False)
    monkeypatch.delenv('ANTHROPIC_MODEL',raising=False)
    monkeypatch.delenv('ALLOW_EXTERNAL_WRITES',raising=False)
    monkeypatch.delenv('LANGSMITH_TRACING',raising=False)
    return tmp_path


def make_client(env):
    return TestClient(module.create_app(f'sqlite:///{env/"platform.db"}'))


def sign_in(c,operator=False):
    r=c.post('/api/platform/login',json={'username':'operator@example.com' if operator else 'admin@example.com','password':'operator-password-12345' if operator else 'test-password-12345'},headers=HEADERS)
    assert r.status_code==200,r.text
    return r


def investigate(c,cid='cus_pending',mode='offline'):
    return c.post('/api/platform/investigate',json={'question':'Why is access missing?','customer_id':cid,'mode':mode},headers=HEADERS)


def test_viewer_permissions_and_session_logout(env):
    with make_client(env) as c:
        assert c.get('/api/platform/status').json()['identity']['role']=='viewer'
        assert investigate(c).status_code==403
        assert c.post('/api/simulate',json={'scenario':'checkout'},headers=HEADERS).status_code==403
        sign_in(c)
        assert c.get('/api/platform/status').json()['identity']['role']=='admin'
        assert c.post('/api/platform/logout',json={},headers=HEADERS).status_code==200
        assert c.get('/api/platform/runs').status_code==403


def test_approval_checkpoint_survives_restart_and_retries_once(env):
    with make_client(env) as c:
        sign_in(c);response=investigate(c)
        assert response.status_code==200,response.text
        run=response.json();assert run['status']=='awaiting_approval'
        assert not any(x['id']=='cus_pending' for x in c.get('/api/dashboard').json()['customers'])
    with make_client(env) as c:
        sign_in(c)
        assert c.get('/api/platform/runs').json()[0]['status']=='awaiting_approval'
        decision=c.post(f'/api/platform/runs/{run["id"]}/decision',json={'approved':True,'reason':'Provider is healthy; approve the failed delivery retry.'},headers=HEADERS)
        assert decision.status_code==200,decision.text
        assert decision.json()['status']=='completed'
        pending=next(x for x in c.get('/api/dashboard').json()['customers'] if x['id']=='cus_pending')
        assert pending['access'] and pending['crm_synced']
        assert c.post(f'/api/platform/runs/{run["id"]}/decision',json={'approved':True,'reason':'Repeat'},headers=HEADERS).status_code==409
        assert any(x['action']=='approve' for x in c.get('/api/platform/audit').json())


def test_reject_does_not_change_customer(env):
    with make_client(env) as c:
        sign_in(c);run=investigate(c).json()
        response=c.post(f'/api/platform/runs/{run["id"]}/decision',json={'approved':False,'reason':'Investigate first'},headers=HEADERS)
        assert response.json()['status']=='rejected'
        assert not any(x['id']=='cus_pending' for x in c.get('/api/dashboard').json()['customers'])


def test_operator_can_investigate_but_not_approve_or_ingest(env):
    with make_client(env) as c:
        sign_in(c,operator=True);run=investigate(c).json()
        assert run['status']=='awaiting_approval'
        assert c.post(f'/api/platform/runs/{run["id"]}/decision',json={'approved':True,'reason':'Please retry'},headers=HEADERS).status_code==403
        assert c.post('/api/platform/documents',json={'title':'X','content':'Unauthorized operational note'},headers=HEADERS).status_code==403
        assert c.get('/api/platform/audit').status_code==403


def test_knowledge_ingest_search_and_idempotence(env):
    with make_client(env) as c:
        sign_in(c)
        body={'title':'Access policy','content':'Eligible membership access is restored only after successful retry and administrator approval.'}
        for _ in range(2):assert c.post('/api/platform/documents',json=body,headers=HEADERS).status_code==200
        docs=c.get('/api/platform/documents').json()
        assert next(x for x in docs if x['title']=='Access policy')['chunks']==1
        result=c.post('/api/platform/search',json={'query':'Eligible membership retry'},headers=HEADERS).json()
        assert any(x['title']=='Access policy' for x in result['results'])
        assert c.post('/api/platform/search',json={'query':'retry','semantic':True},headers=HEADERS).status_code==503


def test_live_mode_missing_key_is_explicit_no_offline_fallback(env):
    with make_client(env) as c:
        sign_in(c);r=investigate(c,mode='claude')
        assert r.status_code==503
        run=c.get('/api/platform/runs').json()[0]
        assert run['status']=='failed' and run['mode']=='claude'


def test_live_structured_output_and_usage_with_mocked_provider(env,monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY','fake-test-key')
    monkeypatch.setenv('ANTHROPIC_MODEL','test-model')
    import platform_copilot
    class Response:
        is_error=False
        def json(self):
            return {'content':[{'type':'tool_use','id':'tool_1','name':'finish_analysis','input':{'summary':'No failed event for this active customer','event_id':None,'action':'none','evidence_ids':[]}}],'usage':{'input_tokens':100,'output_tokens':20}}
    monkeypatch.setattr(platform_copilot.httpx,'post',lambda *a,**kw:Response())
    with make_client(env) as c:
        sign_in(c);r=investigate(c,'cus_a','claude')
        assert r.status_code==200,r.text
        assert r.json()['status']=='completed'
        metrics=c.get('/api/platform/metrics').json()
        assert metrics['input_tokens']==100 and metrics['output_tokens']==20
        assert metrics['estimated_cost_usd'] is None


def test_untrusted_model_action_is_blocked(env,monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY','fake-test-key');monkeypatch.setenv('ANTHROPIC_MODEL','test-model')
    import platform_copilot
    class Response:
        is_error=False
        def json(self):return {'content':[{'type':'tool_use','id':'bad','name':'finish_analysis','input':{'summary':'Retry another customer','event_id':'evt_not_authorized','action':'retry_event','evidence_ids':['invented']}}]}
    monkeypatch.setattr(platform_copilot.httpx,'post',lambda *a,**kw:Response())
    with make_client(env) as c:
        sign_in(c);assert investigate(c,'cus_a','claude').status_code==502
        assert c.get('/api/platform/runs').json()[0]['status']=='failed'


def test_hubspot_dry_run_then_block_external_write(env):
    with make_client(env) as c:
        sign_in(c)
        r=c.post('/api/platform/hubspot-proposal',json={'customer_id':'cus_a'},headers=HEADERS)
        assert r.status_code==200,r.text
        run=r.json();assert run['result']['preview']['dry_run'] is True
        r=c.post(f'/api/platform/runs/{run["id"]}/decision',json={'approved':True,'reason':'Test account preview reviewed'},headers=HEADERS)
        assert r.status_code==503
        assert c.get('/api/platform/runs').json()[0]['status']=='failed'


def test_mcp_and_automation_tokens_fail_closed(env,monkeypatch):
    monkeypatch.setenv('AUTOMATION_TOKEN','automation-test-secret')
    monkeypatch.setenv('MCP_READ_TOKEN','mcp-test-secret')
    with make_client(env) as c:
        assert c.post('/mcp/',json={}).status_code==401
        message={'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'test','version':'1'}}}
        r=c.post('/mcp/',json=message,headers={'Authorization':'Bearer mcp-test-secret','Accept':'application/json, text/event-stream'})
        assert r.status_code==200,r.text
        assert r.json()['result']['serverInfo']['name']=='Martell Operations'
        assert c.post('/api/automation/classify',json={'text':'cancel'},headers=HEADERS).status_code==401
        r=c.post('/api/automation/classify',json={'text':'cancel'},headers={'Authorization':'Bearer automation-test-secret'})
        assert r.status_code==200 and r.json()['label']=='churn_risk'


def test_reset_preserves_login_and_audit(env):
    with make_client(env) as c:
        sign_in(c);investigate(c)
        assert c.post('/api/reset',json={'confirm':True},headers=HEADERS).status_code==200
        assert c.get('/api/platform/runs').status_code==200
        assert c.get('/api/platform/audit').json()


def test_test_stripe_webhook_signature_and_duplicate_guard(env,monkeypatch):
    import hmac,hashlib,time
    secret='whsec_test';monkeypatch.setenv('STRIPE_TEST_WEBHOOK_SECRET',secret)
    with make_client(env) as c:
        timestamp=int(time.time())
        payload=json.dumps({'id':'evt_sandbox','type':'invoice.paid','livemode':False}).encode()
        signature=hmac.new(secret.encode(),str(timestamp).encode()+b'.'+payload,hashlib.sha256).hexdigest()
        headers={'stripe-signature':f't={timestamp},v1={signature}'}
        assert c.post('/api/connectors/stripe/webhook',content=payload).status_code==400
        assert c.post('/api/connectors/stripe/webhook',content=payload,headers=headers).json()['status']=='recorded_test_event'
        assert c.post('/api/connectors/stripe/webhook',content=payload,headers=headers).json()['status']=='duplicate'
        assert len(c.get('/api/dashboard').json()['customers'])==6


def test_evaluations_and_settings_do_not_leak_keys(env,monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY','sensitive-test-value')
    with make_client(env) as c:
        assert 'sensitive-test-value' not in c.get('/api/platform/status').text
        sign_in(c);r=c.post('/api/platform/evaluate',json={},headers=HEADERS).json()
        assert r['passed']==r['total']==10 and not r['live_model_evaluated']


def test_recovery_scheduler_waits_backs_off_and_removes_completed_jobs(env):
    import threading
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import Base, StripeEvent, EventStatus
    from platform_models import RecoveryJob
    from platform_worker import tick
    engine=create_engine(f'sqlite:///{env/"worker.db"}')
    Base.metadata.create_all(engine);sessions=sessionmaker(engine)
    with sessions() as s:
        s.add(StripeEvent(id='evt_worker',type='invoice.paid',created=1,payload={},status=EventStatus.RECEIVED,attempts=0));s.commit()
    calls=[]
    def retry(event_id):
        calls.append(event_id)
        with sessions() as s:
            event=s.get(StripeEvent,event_id);event.attempts+=1
            event.status=EventStatus.FAILED if len(calls)<3 else EventStatus.PROCESSED
            result={'status':event.status.value};s.commit();return result
    lock=threading.RLock()
    assert tick(sessions,lock,retry,now=100)==0
    assert tick(sessions,lock,retry,now=104)==0 and not calls
    assert tick(sessions,lock,retry,now=105)==1
    assert tick(sessions,lock,retry,now=110)==1
    assert tick(sessions,lock,retry,now=119)==0
    assert tick(sessions,lock,retry,now=120)==1
    with sessions() as s:assert s.get(RecoveryJob,'evt_worker') is None
    assert tick(sessions,lock,retry,now=500)==0 and len(calls)==3
    engine.dispose()



def test_live_auto_tool_choice_and_text_only_followup(env,monkeypatch):
    import platform_copilot
    monkeypatch.setenv('ANTHROPIC_API_KEY','fake-test-key')
    monkeypatch.setenv('ANTHROPIC_MODEL','claude-sonnet-5-5')
    calls=[]
    def provider(*args,**kwargs):
        body=kwargs['json'];assert body['tool_choice']=={'type':'auto'}
        calls.append(len(body['messages']))
        content=[{'type':'text','text':'I will inspect the records.'}] if len(calls)==1 else [{'type':'tool_use','id':'finish','name':'finish_analysis','input':{'summary':'No retry needed','action':'none','event_id':None,'evidence_ids':[]}}]
        class Response:
            is_error=False
            def json(self):return {'content':content,'usage':{'input_tokens':10,'output_tokens':5}}
        return Response()
    monkeypatch.setattr(platform_copilot.httpx,'post',provider)
    with make_client(env) as c:
        sign_in(c);r=investigate(c,'cus_a','claude')
        assert r.status_code==200,r.text
        assert r.json()['status']=='completed' and r.json()['input_tokens']==20
        assert calls==[1,3]


def test_provider_billing_error_is_actionable_without_raw_details(env,monkeypatch):
    import platform_copilot
    monkeypatch.setenv('ANTHROPIC_API_KEY','fake-test-key')
    monkeypatch.setenv('ANTHROPIC_MODEL','claude-sonnet-5-5')
    class Response:
        is_error=True
        status_code=400
        def json(self):return {'error':{'message':'Your credit balance is too low. private-provider-data'}}
    monkeypatch.setattr(platform_copilot.httpx,'post',lambda *a,**kw:Response())
    with make_client(env) as c:
        sign_in(c);r=investigate(c,'cus_a','claude')
        assert r.status_code==502 and 'credits and billing' in r.text
        assert 'private-provider-data' not in r.text
