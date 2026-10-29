"""Server-side sessions and scoped bearer tokens; public access is viewer-only."""
import hashlib
import hmac
import os
import secrets
import time
from fastapi import HTTPException
from platform_models import UserSession

COOKIE = 'martell_session'


def configured():
    return bool(os.getenv('ADMIN_PASSWORD'))


def role_for(request, sessions):
    token = request.cookies.get(COOKIE, '')
    if not token:
        return {'actor':'public-viewer', 'role':'viewer'}
    with sessions() as s:
        record = s.get(UserSession, hashlib.sha256(token.encode()).hexdigest())
        if record and record.expires > time.time():
            return {'actor':record.actor, 'role':record.role}
    return {'actor':'public-viewer', 'role':'viewer'}


def require_role(request, sessions, roles=('admin','operator')):
    identity = role_for(request, sessions)
    if identity['role'] not in roles:
        raise HTTPException(403, 'Sign in with an authorized role to use this operation.')
    return identity


def bearer(request, variable):
    expected = os.getenv(variable, '')
    actual = request.headers.get('authorization', '')
    return bool(expected) and hmac.compare_digest(actual, 'Bearer '+expected)


def login(username, password, sessions):
    email = os.getenv('ADMIN_EMAIL','admin@example.com')
    role = None
    if len(password) >= 12 and os.getenv('ADMIN_PASSWORD') and hmac.compare_digest(username,email) and hmac.compare_digest(password,os.environ['ADMIN_PASSWORD']):
        role = 'admin'
    elif len(password) >= 12 and os.getenv('OPERATOR_PASSWORD') and hmac.compare_digest(username,os.getenv('OPERATOR_EMAIL','operator@example.com')) and hmac.compare_digest(password,os.environ['OPERATOR_PASSWORD']):
        role = 'operator'
    if not role:
        raise HTTPException(401,'Invalid credentials, or account not configured. Passwords must contain at least 12 characters.')
    token = secrets.token_urlsafe(32)
    with sessions() as s:
        s.add(UserSession(token_hash=hashlib.sha256(token.encode()).hexdigest(),actor=username,role=role,expires=int(time.time())+8*3600))
        s.commit()
    return token, {'actor':username,'role':role}
