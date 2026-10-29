"""Opt-in durable retry scheduler. One process; use a dedicated worker at scale."""
import time
from sqlalchemy import select
from app.models import StripeEvent, EventStatus
from platform_models import RecoveryJob


def tick(sessions, lock, retry, now=None):
    now=int(time.time()) if now is None else now
    done=0
    with lock,sessions() as s:
        events=s.scalars(select(StripeEvent).where(StripeEvent.status.in_([EventStatus.FAILED,EventStatus.RECEIVED])).limit(100)).all()
        for e in events:
            job=s.get(RecoveryJob,e.id)
            if job is None:
                s.add(RecoveryJob(event_id=e.id,available_at=now+min(300,5*2**max(0,e.attempts-1))));s.commit();continue
            if job.available_at>now:continue
            result=retry(e.id)
            if result['status'] in ('failed','received'):
                s.expire_all();event=s.get(StripeEvent,e.id)
                job.available_at=now+min(300,5*2**max(0,event.attempts-1));s.commit()
            else:s.delete(job);s.commit()
            done+=1
    return done
