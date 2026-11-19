"""Session authentication and login throttling shared by all routers."""
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
import hashlib
import os
import secrets
import threading
import time
from fastapi import HTTPException, Request
from pwdlib import PasswordHash
from .database import database

passwords = PasswordHash.recommended()
dummy_hash = passwords.hash(secrets.token_urlsafe(24))
COOKIE = 'betalab_session'
SECURE = os.getenv('COOKIE_SECURE', 'false').lower() == 'true'
attempts = defaultdict(deque)
attempt_lock = threading.Lock()

def throttle(request):
    key = request.client.host if request.client else 'unknown'
    now = time.monotonic()
    with attempt_lock:
        for old in list(attempts):
            while attempts[old] and attempts[old][0] <= now - 60:
                attempts[old].popleft()
            if not attempts[old]:
                del attempts[old]
        if len(attempts[key]) >= 10:
            raise HTTPException(429, 'Too many attempts; try again in a minute', headers={'Retry-After': '60'})
        attempts[key].append(now)


def public_user(user):
    return {key: user[key] for key in ('id', 'username', 'display_name', 'height_cm', 'arm_span_cm')}


def current_session(request: Request):
    token = request.cookies.get(COOKIE)
    if not token or len(token) > 200:
        raise HTTPException(401, 'Login required')
    digest = hashlib.sha256(token.encode()).hexdigest()
    with database() as db:
        row = db.execute('SELECT u.*, s.csrf_token, s.token_hash FROM sessions s JOIN users u ON u.id=s.user_id '
                         'WHERE s.token_hash=%s AND s.expires_at>now()', (digest,)).fetchone()
    if not row:
        raise HTTPException(401, 'Session expired')
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        if not secrets.compare_digest(request.headers.get('x-csrf-token', ''), row['csrf_token']):
            raise HTTPException(403, 'Invalid CSRF token')
    return row


def create_session(db, user, response, old_token):
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    db.execute('DELETE FROM sessions WHERE expires_at<=now()')
    if old_token:
        db.execute('DELETE FROM sessions WHERE token_hash=%s', (hashlib.sha256(old_token.encode()).hexdigest(),))
    db.execute('INSERT INTO sessions(token_hash,user_id,csrf_token,expires_at) VALUES (%s,%s,%s,%s)',
               (hashlib.sha256(token.encode()).hexdigest(), user['id'], csrf,
                datetime.now(timezone.utc) + timedelta(days=7)))
    response.set_cookie(COOKIE, token, max_age=604800, httponly=True, secure=SECURE, samesite='lax', path='/')
    return {'user': public_user(user), 'csrf_token': csrf}
