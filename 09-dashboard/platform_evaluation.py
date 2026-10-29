"""Isolated deterministic workflow regression; never calls a provider or executes actions."""
import json
from pathlib import Path
from platform_copilot import Workflow


def evaluate_workflow():
    cases=json.loads((Path(__file__).parent/'evals/copilot.json').read_text())
    results=[]
    for case in cases:
        workflow=Workflow.__new__(Workflow)
        workflow.snapshot=lambda: {'customers':[], 'events':case['events']}
        output=workflow.investigate({'customer_id':case['customer_id'],'mode':'offline','question':'Investigate access'})
        result=output['result']
        checks={
            'action':result['action']==case['expected_action'],
            'event':result['event_id']==case['expected_event'],
            'evidence_scope':set(result['evidence_ids']) <= {e['id'] for e in case['events'] if e['customer_id']==case['customer_id']},
            'read_tools': [t['tool'] for t in output['trace']]==['get_customer','list_failed_events'],
        }
        results.append({'id':case['id'],'checks':checks,'passed':all(checks.values())})
    return {'kind':'offline_copilot_regression','passed':sum(c['passed'] for c in results),'total':len(results),'cases':results,'live_model_evaluated':False,'actions_executed':0}
