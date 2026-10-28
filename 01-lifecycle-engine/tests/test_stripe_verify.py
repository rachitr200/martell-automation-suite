from app.stripe_verify import SignatureError, verify_signature
from tests.helpers import SECRET, sign

BODY = b'{"id":"evt_1"}'


def rejects(exc, fn):
    try:
        fn()
    except exc:
        return True
    return False


def test_valid_signature_passes():
    verify_signature(BODY, sign(BODY, 1_000), SECRET, now=1_000)


def test_wrong_secret_rejected():
    assert rejects(SignatureError, lambda: verify_signature(BODY, sign(BODY, 1_000, secret="other"), SECRET, now=1_000))


def test_tampered_body_rejected():
    assert rejects(SignatureError, lambda: verify_signature(b'{"id":"evt_2"}', sign(BODY, 1_000), SECRET, now=1_000))


def test_stale_timestamp_rejected():
    assert rejects(SignatureError, lambda: verify_signature(BODY, sign(BODY, 1_000), SECRET, tolerance_seconds=300, now=2_000))


def test_malformed_header_rejected():
    assert rejects(SignatureError, lambda: verify_signature(BODY, "garbage", SECRET))


def test_unconfigured_secret_is_an_error_not_a_pass():
    assert rejects(ValueError, lambda: verify_signature(BODY, sign(BODY), ""))
