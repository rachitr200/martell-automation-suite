"""Observed run outcomes, with separately labelled operator-supplied baseline estimates."""
import math


def summarize_outcomes(runs, manual_minutes=None):
    unique_recoveries=set()
    failures=0
    for run in runs:
        execution=(run.result or {}).get('execution') or {}
        if run.status=='completed' and (run.result or {}).get('action')=='retry_event' and execution.get('status')=='processed':
            unique_recoveries.add((run.result or {}).get('event_id'))
        failures+=run.status=='failed'
    unique_recoveries.discard(None)
    baseline=None
    try:
        value=float(manual_minutes)
        if math.isfinite(value) and value>=0:baseline=value
    except (TypeError,ValueError):pass
    return {'recorded_runs':len(runs),'unique_recovered_events':len(unique_recoveries),
            'failed_runs':failures,'run_failure_rate':failures/len(runs) if runs else None,
            'rejected_runs':sum(r.status=='rejected' for r in runs),
            'manual_minutes_per_recovery':baseline,
            'estimated_manual_work_minutes':len(unique_recoveries)*baseline if baseline is not None else None,
            'measurement_note':'Observed outcomes cover up to 1000 recent runs on synthetic demo data. Manual work estimate = unique recovered events × configured manual baseline; it is not measured time saved or production ROI.'}
