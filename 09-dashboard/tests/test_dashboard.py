import importlib.util
import sys
from pathlib import Path

from fastapi.testclient import TestClient

MODULE = Path(__file__).resolve().parents[1] / 'dashboard.py'
spec = importlib.util.spec_from_file_location('operations_dashboard', MODULE)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
HEADERS = {'X-Demo-Action': '1'}


def client_for(tmp_path):
    return TestClient(module.create_app(f'sqlite:///{tmp_path / "test.db"}'))


def test_page_assets_snapshot_and_seeded_recovery(tmp_path):
    with client_for(tmp_path) as c:
        assert c.get('/').status_code == 200
        assert c.get('/static/app.js').status_code == 200
        assert c.get('/static/styles.css').status_code == 200
        state = c.get('/api/dashboard').json()
        assert len(state['customers']) == 6
        assert state['mode'] == 'synthetic_demo'
        failed = next(e for e in state['events'] if e['status'] == 'failed')
        assert failed['customer_id'] == 'cus_pending'
        assert c.post(f'/api/events/{failed["id"]}/retry', json={}, headers=HEADERS).json()['status'] == 'processed'
        state = c.get('/api/dashboard').json()
        recovered = next(x for x in state['customers'] if x['id'] == 'cus_pending')
        assert recovered['access'] and recovered['crm_synced']
        assert c.post(f'/api/events/{failed["id"]}/retry', json={}, headers=HEADERS).status_code == 409


def test_signup_failure_retry_replay_cancel_and_revenue(tmp_path):
    with client_for(tmp_path) as c:
        before = c.get('/api/dashboard').json()
        failed = c.post('/api/simulate', json={'scenario':'access_failure','plan':'basic'}, headers=HEADERS).json()
        assert failed['status'] == 'failed'
        mid = c.get('/api/dashboard').json()
        assert len(mid['customers']) == len(before['customers'])
        assert c.post(f'/api/events/{failed["event_id"]}/retry', json={}, headers=HEADERS).json()['status'] == 'processed'
        after = c.get('/api/dashboard').json()
        new = next(x for x in after['customers'] if x['id'] not in {x['id'] for x in before['customers']})
        assert after['revenue']['mrr_cents'] == before['revenue']['mrr_cents'] + 9700
        assert new['access'] and new['crm_synced']
        assert c.post(f'/api/events/{failed["event_id"]}/replay', json={}, headers=HEADERS).json()['status'] == 'duplicate'
        assert len(c.get('/api/dashboard').json()['customers']) == len(after['customers'])
        result = c.post('/api/simulate', json={'scenario':'cancel','customer_id':new['id']}, headers=HEADERS)
        assert result.json()['status'] == 'processed'
        final = c.get('/api/dashboard').json()
        canceled = next(x for x in final['customers'] if x['id'] == new['id'])
        assert canceled['status'] == 'canceled' and not canceled['access']
        assert final['revenue']['mrr_cents'] == before['revenue']['mrr_cents']
        assert not final['issues']


def test_payment_failure_recovery_and_input_validation(tmp_path):
    with client_for(tmp_path) as c:
        for scenario, expected in [('payment_failed','past_due'), ('payment_recovered','active')]:
            assert c.post('/api/simulate', json={'scenario':scenario,'customer_id':'cus_a'}, headers=HEADERS).status_code == 200
            state = c.get('/api/dashboard').json()
            customer = next(x for x in state['customers'] if x['id'] == 'cus_a')
            assert customer['status'] == expected and customer['access']
        assert c.post('/api/simulate', json={'scenario':'bad'}, headers=HEADERS).status_code == 422
        assert c.post('/api/simulate', json={'scenario':'cancel','customer_id':'missing'}, headers=HEADERS).status_code == 404
        assert c.get('/api/events/missing').status_code == 404
        assert c.post('/api/events/missing/retry', json={}, headers=HEADERS).status_code == 404


def test_ai_tools_are_offline_and_evaluation_skips_live_cases(tmp_path):
    with client_for(tmp_path) as c:
        result = c.post('/api/tools/classify', json={'text':'I want to cancel'}, headers=HEADERS).json()
        assert result['label'] == 'churn_risk' and 'Offline' in result['mode']
        answer = c.post('/api/tools/coach', json={'text':'How do I decide what to delegate?'}, headers=HEADERS).json()
        assert answer['retrieved'] and answer['cited']
        assert not answer['invalid_citations']
        refusal = c.post('/api/tools/coach', json={'text':'quantum particle collider'}, headers=HEADERS).json()
        assert refusal['refused']
        reply = c.post('/api/tools/copilot', json={'text':'This is too expensive'}, headers=HEADERS).json()
        assert reply['objection'] == 'price' and reply['suggestions']
        scores = c.post('/api/tools/evaluate', json={}, headers=HEADERS).json()
        assert scores['total'] > 0 and scores['skipped'] > 0
        assert scores['passed'] == scores['total']
        assert c.post('/api/tools/coach', json={'text':''}, headers=HEADERS).status_code == 422


def test_cross_origin_mutations_blocked_and_reset_reseeds(tmp_path):
    with client_for(tmp_path) as c:
        assert c.post('/api/reset', json={'confirm':True}).status_code == 403
        assert c.post('/api/reset', json={'confirm':True}, headers={**HEADERS,'Origin':'https://other.example'}).status_code == 403
        assert c.post('/api/reset', json={'confirm':False}, headers=HEADERS).status_code == 422
        assert c.post('/api/simulate', json={'scenario':'checkout'}, headers=HEADERS).status_code == 200
        assert len(c.get('/api/dashboard').json()['customers']) == 7
        assert c.post('/api/reset', json={'confirm':True}, headers=HEADERS).status_code == 200
        assert len(c.get('/api/dashboard').json()['customers']) == 6
        assert c.get('/api/health').json()['live_integrations'] is False
        assert c.get('/api/dashboard').headers['cache-control'] == 'no-store'


def test_data_survives_restart(tmp_path):
    with client_for(tmp_path) as c:
        c.post('/api/simulate', json={'scenario':'checkout'}, headers=HEADERS)
    with client_for(tmp_path) as c:
        assert len(c.get('/api/dashboard').json()['customers']) == 7
