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
    username: str | None = Field(default=None, min_length=3, max_length=32, pattern=r'^[A-Za-z0-9_]+$')
    bio: str | None = Field(default=None, max_length=500)
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
    try:
        with database() as db:
            user = db.execute('UPDATE users SET display_name=%s,height_cm=%s,arm_span_cm=%s,'
                              'username=COALESCE(%s,username),bio=COALESCE(%s,bio),updated_at=now() '
                              'WHERE id=%s RETURNING *', (body.display_name.strip(), body.height_cm, body.arm_span_cm,
                              body.username.lower() if body.username else None, body.bio.strip() if body.bio is not None else None, session['id'])).fetchone()
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, 'Username already exists')
    return {'user': public_user(user)}



class Privacy(BaseModel):
    model_config = ConfigDict(extra='forbid')
    account_visibility: str = Field(pattern=r'^(public|private)$')
    calendar_visible: bool
    measurements_visible: bool | None = None
    library_visible: bool | None = None
    likes_visible: bool | None = None
    saves_visible: bool | None = None
    skeletons_visible: bool | None = None


@router.patch('/api/profile/privacy')
def privacy(body: Privacy, session=Depends(current_session)):
    fields = body.model_dump(exclude_none=True)
    assignments = ','.join(key + '=%s' for key in fields)
    with database() as db:
        user = db.execute('UPDATE users SET '+assignments+',updated_at=now() WHERE id=%s RETURNING *',
                          (*fields.values(), session['id'])).fetchone()
    return {'user': public_user(user)}


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


@router.post('/api/profile/password', status_code=204)
def change_password(body: PasswordChange, request: Request, session=Depends(current_session)):
    throttle(request)
    with database() as db:
        user = db.execute('SELECT * FROM users WHERE id=%s FOR UPDATE', (session['id'],)).fetchone()
        if not passwords.verify(body.current_password, user['password_hash']):
            raise HTTPException(400, 'Current password is incorrect')
        if body.current_password == body.new_password:
            raise HTTPException(422, 'Choose a different new password')
        db.execute('UPDATE users SET password_hash=%s,updated_at=now() WHERE id=%s', (passwords.hash(body.new_password), session['id']))
        db.execute('DELETE FROM sessions WHERE user_id=%s AND token_hash<>%s', (session['id'], session['token_hash']))


@router.get('/api/users/{user_id}/page')
def public_page(user_id: str, session=Depends(current_session)):
    from uuid import UUID
    try:
        target = UUID(user_id)
    except ValueError:
        raise HTTPException(404, 'User not found')
    with database() as db:
        user = db.execute('SELECT * FROM users WHERE id=%s', (target,)).fetchone()
        if not user:
            raise HTTPException(404, 'User not found')
        owner = str(session['id']) == str(target)
        identity = {key: user[key] for key in ('id','username','account_visibility')}
        if user['account_visibility'] == 'private' and not owner:
            return {'user': identity, 'videos': [], 'calendar': None, 'likes': None, 'saves': None, 'skeletons': None}
        identity['display_name'] = user['display_name']
        identity['bio'] = user['bio']
        if owner or user['measurements_visible']:
            identity.update(height_cm=user['height_cm'], arm_span_cm=user['arm_span_cm'])
        videos = db.execute("SELECT id,title,route_id,created_at FROM user_videos WHERE owner_id=%s AND (%s OR visibility='public') ORDER BY created_at DESC", (target, owner)).fetchall()
        if not owner and not user['library_visible']:
            videos = []
        calendar = None
        if owner or user['calendar_visible']:
            calendar = db.execute("SELECT (v.created_at AT TIME ZONE 'UTC')::date AS day,g.name AS gym,count(*) AS attempts,count(DISTINCT v.route_id) AS routes FROM user_videos v JOIN routes r ON r.id=v.route_id JOIN gyms g ON g.id=r.gym_id WHERE v.owner_id=%s AND (%s OR v.visibility='public') GROUP BY day,g.name ORDER BY day", (target, owner)).fetchall()
        skeletons = None
        if owner or (user['library_visible'] and user['skeletons_visible']):
            skeletons = db.execute("SELECT t.id,t.created_at,t.is_mock FROM compute_tasks t JOIN user_videos v ON v.id=t.source_video_id JOIN compute_results r ON r.task_id=t.id WHERE t.owner_id=%s AND t.kind='generate' AND t.state='succeeded' AND (v.owner_id=t.owner_id OR v.visibility='public') AND (%s OR v.visibility='public') ORDER BY t.created_at DESC", (target,owner)).fetchall()
            for task in skeletons:
                task['content_url'] = f"/api/users/{target}/skeletons/{task['id']}/video"
        # B will populate likes/saves when persistent social collections are implemented.
        return {'user': identity, 'videos': videos, 'calendar': calendar,
                'likes': [] if owner or (user['library_visible'] and user['likes_visible']) else None,
                'saves': [] if owner or (user['library_visible'] and user['saves_visible']) else None,
                'skeletons': skeletons}


@router.get('/api/users/{user_id}/skeletons/{task_id}/video')
def shared_skeleton(user_id: str, task_id: str, request: Request, session=Depends(current_session)):
    from uuid import UUID
    from ..compute.media import stream_artifact
    try:
        target, task = UUID(user_id), UUID(task_id)
    except ValueError:
        raise HTTPException(404, 'Skeleton not found')
    with database() as db:
        row = db.execute("SELECT r.payload FROM compute_tasks t JOIN compute_results r ON r.task_id=t.id JOIN users u ON u.id=t.owner_id JOIN user_videos v ON v.id=t.source_video_id WHERE t.id=%s AND t.owner_id=%s AND t.kind='generate' AND t.state='succeeded' AND (v.owner_id=t.owner_id OR v.visibility='public') AND (t.owner_id=%s OR (u.account_visibility='public' AND u.library_visible AND u.skeletons_visible AND v.visibility='public'))", (task,target,session['id'])).fetchone()
        if not row:
            raise HTTPException(404, 'Skeleton not found')
    # Share only the preview; task details, measurements and input artifacts remain private.
    return stream_artifact(row['payload'], 'video', request)
