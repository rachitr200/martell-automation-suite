from sqlalchemy import select
from app.models import Customer, CustomerStatus, StripeEvent
from app.processor import retry_failed
from tests.helpers import checkout_completed, make_event, post_event


def customer(factory):
    with factory() as s:return s.scalar(select(Customer).where(Customer.stripe_customer_id=='cus_1'))


def test_late_checkout_hydrates_identity_and_grants_access(client,session_factory,integrations):
    post_event(client,make_event('evt_paid','invoice.paid',200,{'customer':'cus_1'}))
    post_event(client,checkout_completed(created=100))
    row=customer(session_factory)
    assert row.email=='a@example.com' and row.status==CustomerStatus.ACTIVE
    assert integrations.access.granted==[('a@example.com','pro')]


def test_equal_timestamp_update_cannot_resurrect_cancellation(client,session_factory,integrations):
    post_event(client,checkout_completed(created=100))
    post_event(client,make_event('evt_del','customer.subscription.deleted',200,{'customer':'cus_1'}))
    post_event(client,make_event('evt_up','customer.subscription.updated',200,{'customer':'cus_1','status':'active'}))
    assert customer(session_factory).status==CustomerStatus.CANCELED
    assert integrations.access.revoked==['a@example.com']


def test_received_event_is_recovered_after_crash(session_factory,integrations,settings):
    event=checkout_completed()
    with session_factory() as s:
        s.add(StripeEvent(id=event['id'],type=event['type'],created=event['created'],payload=event));s.commit()
        assert retry_failed(s,integrations,settings.max_attempts)==1
    assert customer(session_factory).status==CustomerStatus.ACTIVE
    assert len(integrations.access.granted)==1


def test_cancellation_in_updated_event_revokes_access(client,session_factory,integrations):
    post_event(client,checkout_completed(created=100))
    post_event(client,make_event('evt_up','customer.subscription.updated',200,{'customer':'cus_1','status':'canceled'}))
    assert customer(session_factory).status==CustomerStatus.CANCELED
    assert integrations.access.revoked==['a@example.com']


def test_unpaid_checkout_does_not_grant_access(client,session_factory,integrations):
    event=checkout_completed();event['data']['object']['payment_status']='unpaid'
    post_event(client,event)
    assert customer(session_factory) is None
    assert integrations.access.granted==[]
