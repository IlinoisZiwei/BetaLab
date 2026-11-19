"""Account and profile endpoints; session mechanics live in backend.auth."""
import os
from uuid import uuid4
import psycopg
from ..auth import throttle, public_user, create_session, passwords, dummy_hash, COOKIE, SECURE
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from ..database import database
from ..auth import current_session

router = APIRouter()

class Credentials(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=3, max_length=32, pattern=r'^[A-Za-z0-9_]+$')
    password: str = Field(min_length=8, max_length=128)


class Profile(BaseModel):
    model_config = ConfigDict(extra='forbid')
    display_name: str = Field(min_length=1, max_length=80)
    height_cm: float | None = Field(default=None, ge=100, le=230, allow_inf_nan=False)
    arm_span_cm: float | None = Field(default=None, ge=80, le=260, allow_inf_nan=False)


@router.post('/api/auth/register', status_code=201)
def register(body: Credentials, request: Request, response: Response):
    throttle(request)
    if os.getenv('REGISTRATION_ENABLED', 'true').lower() != 'true':
        raise HTTPException(403, 'Registration is closed')
    try:
        with database() as db:
            user = db.execute('INSERT INTO users(id,username,password_hash,display_name) VALUES (%s,%s,%s,%s) RETURNING *',
                              (uuid4(), body.username.lower(), passwords.hash(body.password), body.username)).fetchone()
            return create_session(db, user, response, request.cookies.get(COOKIE))
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, 'Username already exists')


@router.post('/api/auth/login')
def login(body: Credentials, request: Request, response: Response):
    throttle(request)
    with database() as db:
        user = db.execute('SELECT * FROM users WHERE username=%s', (body.username.lower(),)).fetchone()
        valid = passwords.verify(body.password, user['password_hash'] if user else dummy_hash)
        if not user or not valid:
            raise HTTPException(401, 'Invalid username or password')
        return create_session(db, user, response, request.cookies.get(COOKIE))


@router.get('/api/auth/me')
def me(session=Depends(current_session)):
    return {'user': public_user(session), 'csrf_token': session['csrf_token']}


@router.post('/api/auth/logout', status_code=204)
def logout(response: Response, session=Depends(current_session)):
    with database() as db:
        db.execute('DELETE FROM sessions WHERE token_hash=%s', (session['token_hash'],))
    response.delete_cookie(COOKIE, path='/', secure=SECURE, httponly=True, samesite='lax')


@router.put('/api/profile')
def profile(body: Profile, session=Depends(current_session)):
    if not body.display_name.strip():
        raise HTTPException(422, 'Display name cannot be blank')
    with database() as db:
        user = db.execute('UPDATE users SET display_name=%s,height_cm=%s,arm_span_cm=%s,updated_at=now() '
                          'WHERE id=%s RETURNING *', (body.display_name.strip(), body.height_cm, body.arm_span_cm, session['id'])).fetchone()
    return {'user': public_user(user)}
