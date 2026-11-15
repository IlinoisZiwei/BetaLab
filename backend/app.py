"""A's account/catalog API. Run from repository root; see backend/README.md."""
from collections import defaultdict, deque
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
import psycopg
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict, Field
from pwdlib import PasswordHash

load_dotenv(Path(__file__).resolve().parents[1] / '.env')
app = FastAPI(title='BetaLab API', version='0.1.0')
passwords = PasswordHash.recommended()
dummy_hash = passwords.hash(secrets.token_urlsafe(24))
COOKIE = 'betalab_session'
SECURE = os.getenv('COOKIE_SECURE', 'false').lower() == 'true'
ORIGINS = set(os.getenv('APP_ORIGINS', 'http://localhost:8443,http://127.0.0.1:8443').split(','))
attempts = defaultdict(deque)
attempt_lock = threading.Lock()
UPLOAD_DIR = Path(os.getenv('UPLOAD_DIR', './data/uploads')).resolve()
MAX_UPLOAD_BYTES = int(os.getenv('MAX_UPLOAD_BYTES', 209715200))
MAX_VIDEO_SECONDS = float(os.getenv('MAX_VIDEO_SECONDS', '90'))
CHUNK_SIZE = 1024 * 1024
UPLOAD_TYPES = {'video/mp4': '.mp4', 'video/quicktime': '.mov'}
RANGE_RE = re.compile(r'^bytes=(\d*)-(\d*)$')


@contextmanager
def database():
    with psycopg.connect(host=os.getenv('POSTGRES_HOST', '127.0.0.1'),
                          port=os.getenv('POSTGRES_PORT', '5433'),
                          dbname=os.getenv('POSTGRES_DB', 'betalab'),
                          user=os.getenv('POSTGRES_USER', 'betalab'),
                          password=os.environ['POSTGRES_PASSWORD'], row_factory=dict_row) as conn:
        yield conn


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return JSONResponse(status_code=exc.status_code, content={'error': {'message': str(exc.detail)}}, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Do not echo input values (especially passwords).
    return JSONResponse(status_code=422, content={'error': {'message': 'Invalid request fields'}})


@app.middleware('http')
async def csrf_origin(request: Request, call_next):
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        # Explicit browser origin allowlist: no trusting client-controlled Host.
        if request.headers.get('origin') not in ORIGINS:
            return JSONResponse(status_code=403, content={'error': {'message': 'Origin not allowed'}})
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    return response


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


class Credentials(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=3, max_length=32, pattern=r'^[A-Za-z0-9_]+$')
    password: str = Field(min_length=8, max_length=128)


class Profile(BaseModel):
    model_config = ConfigDict(extra='forbid')
    display_name: str = Field(min_length=1, max_length=80)
    height_cm: float | None = Field(default=None, ge=100, le=230, allow_inf_nan=False)
    arm_span_cm: float | None = Field(default=None, ge=80, le=260, allow_inf_nan=False)


@app.get('/api/health')
def health():
    with database() as db:
        db.execute('SELECT 1')
    return {'ready': True}


@app.post('/api/auth/register', status_code=201)
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


@app.post('/api/auth/login')
def login(body: Credentials, request: Request, response: Response):
    throttle(request)
    with database() as db:
        user = db.execute('SELECT * FROM users WHERE username=%s', (body.username.lower(),)).fetchone()
        valid = passwords.verify(body.password, user['password_hash'] if user else dummy_hash)
        if not user or not valid:
            raise HTTPException(401, 'Invalid username or password')
        return create_session(db, user, response, request.cookies.get(COOKIE))


@app.get('/api/auth/me')
def me(session=Depends(current_session)):
    return {'user': public_user(session), 'csrf_token': session['csrf_token']}


@app.post('/api/auth/logout', status_code=204)
def logout(response: Response, session=Depends(current_session)):
    with database() as db:
        db.execute('DELETE FROM sessions WHERE token_hash=%s', (session['token_hash'],))
    response.delete_cookie(COOKIE, path='/', secure=SECURE, httponly=True, samesite='lax')


@app.put('/api/profile')
def profile(body: Profile, session=Depends(current_session)):
    if not body.display_name.strip():
        raise HTTPException(422, 'Display name cannot be blank')
    with database() as db:
        user = db.execute('UPDATE users SET display_name=%s,height_cm=%s,arm_span_cm=%s,updated_at=now() '
                          'WHERE id=%s RETURNING *', (body.display_name.strip(), body.height_cm, body.arm_span_cm, session['id'])).fetchone()
    return {'user': public_user(user)}


@app.get('/api/gyms')
def gyms(session=Depends(current_session)):
    with database() as db:
        items = db.execute('SELECT g.*,count(r.id) FILTER (WHERE NOT r.archived) AS active_route_count '
                           'FROM gyms g LEFT JOIN routes r ON r.gym_id=g.id GROUP BY g.id ORDER BY g.id').fetchall()
    return {'items': items}


@app.get('/api/routes')
def routes(gym_id: str | None = None, include_archived: bool = False,
           limit: int = 50, offset: int = 0, session=Depends(current_session)):
    if not 1 <= limit <= 100 or offset < 0:
        raise HTTPException(422, 'Invalid pagination')
    with database() as db:
        items = db.execute('SELECT * FROM routes WHERE (%s::text IS NULL OR gym_id=%s) '
                           'AND (%s OR NOT archived) ORDER BY id LIMIT %s OFFSET %s',
                           (gym_id, gym_id, include_archived, limit, offset)).fetchall()
    return {'items': items, 'limit': limit, 'offset': offset}


@app.get('/api/routes/{route_id}')
def route(route_id: str, session=Depends(current_session)):
    with database() as db:
        item = db.execute('SELECT * FROM routes WHERE id=%s', (route_id,)).fetchone()
        if not item:
            raise HTTPException(404, 'Route not found')
        item['media'] = db.execute('SELECT * FROM route_media WHERE route_id=%s ORDER BY id', (route_id,)).fetchall()
    return item


def video_dict(row):
    return {'id': str(row['id']), 'owner_id': str(row['owner_id']), 'route_id': row['route_id'],
            'visibility': row['visibility'], 'share_as_beta': row['share_as_beta'], 'original_name': row['original_name'], 'title': row['title'], 'description': row['description'],
            'media_type': row['media_type'], 'size_bytes': row['size_bytes'],
            'duration_seconds': row['duration_seconds'], 'storage_backend': row.get('storage_backend', 'local'), 'created_at': row['created_at'].isoformat(),
            'content_url': f"/api/videos/{row['id']}/content"}


def video_for_access(video_id, user):
    with database() as db:
        row = db.execute('SELECT * FROM user_videos WHERE id=%s', (video_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Video not found')
    if row['owner_id'] != user['id'] and row['visibility'] != 'public':
        raise HTTPException(404, 'Video not found')
    return row


@app.post('/api/videos', status_code=201)
async def upload_video(request: Request, route_id: str = Form(...), visibility: str = Form('private'),
                       title: str = Form(''), description: str = Form(''), share_as_beta: bool = Form(False),
                       video: UploadFile = File(...), session=Depends(current_session)):
    visibility = visibility.strip().lower()
    if visibility not in ('private', 'public'):
        raise HTTPException(422, 'Visibility must be private or public')
    if share_as_beta and visibility != 'public':
        raise HTTPException(422, 'Community Beta sharing requires a public video')
    cleaned_title = title.strip() or Path(video.filename or 'Climbing video').stem
    if not cleaned_title or len(cleaned_title) > 120:
        raise HTTPException(422, 'Title must be 1–120 characters')
    if len(description.strip()) > 500:
        raise HTTPException(422, 'Description must be 500 characters or fewer')
    if not video.filename or Path(video.filename).suffix.lower() not in ('.mp4', '.mov'):
        raise HTTPException(415, 'Choose an MP4 or MOV video')
    media_type = video.content_type
    if media_type not in UPLOAD_TYPES:
        raise HTTPException(415, 'The browser must identify this file as MP4 or MOV')
    with database() as db:
        if not db.execute('SELECT 1 FROM routes WHERE id=%s', (route_id,)).fetchone():
            raise HTTPException(404, 'Route not found')
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    video_id = uuid4()
    temp_path = None
    stored_path = UPLOAD_DIR / str(session['id']) / f'{video_id}{UPLOAD_TYPES[media_type]}'
    stored_path.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    try:
        with tempfile.NamedTemporaryFile(prefix='.upload-', suffix='.part', dir=stored_path.parent, delete=False) as target:
            temp_path = Path(target.name)
            while chunk := await video.read(CHUNK_SIZE):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, 'Video must be 200 MB or smaller')
                target.write(chunk)
        if size == 0:
            raise HTTPException(422, 'The selected file is empty')
        try:
            probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                    '-show_entries', 'stream=codec_type:format=duration', '-of', 'json', str(temp_path)],
                                   capture_output=True, text=True, timeout=15, check=True)
            import json
            metadata = json.loads(probe.stdout)
            duration = float(metadata['format']['duration'])
            streams = metadata.get('streams', [])
            if not streams or any(stream.get('codec_type') != 'video' for stream in streams):
                raise ValueError('No video stream')
        except (FileNotFoundError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
            raise HTTPException(422, 'Could not verify this video. Install ffprobe and choose a valid MP4 or MOV.')
        if duration <= 0 or duration > MAX_VIDEO_SECONDS:
            raise HTTPException(422, 'Video must be 90 seconds or shorter')
        with temp_path.open('rb') as source:
            signature = source.read(16)
        if media_type == 'video/mp4' and len(signature) < 8 or media_type == 'video/mp4' and signature[4:8] != b'ftyp':
            raise HTTPException(415, 'File contents do not match an MP4 video')
        if media_type == 'video/quicktime' and (len(signature) < 8 or signature[4:8] != b'ftyp'):
            raise HTTPException(415, 'File contents do not match a MOV video')
        os.replace(temp_path, stored_path)
        with database() as db:
            row = db.execute('INSERT INTO user_videos(id,owner_id,route_id,visibility,share_as_beta,original_name,title,description,storage_key,media_type,size_bytes,duration_seconds) '
                             'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *',
                             (video_id, session['id'], route_id, visibility, share_as_beta, Path(video.filename).name[:255], cleaned_title, description.strip(),
                              stored_path.relative_to(UPLOAD_DIR).as_posix(), media_type, size, duration)).fetchone()
        return video_dict(row)
    except Exception:
        stored_path.unlink(missing_ok=True)
        raise
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)
        await video.close()


@app.get('/api/videos')
def list_videos(owned: bool = True, route_id: str | None = None, share_as_beta: bool | None = None,
                limit: int = 50, offset: int = 0, session=Depends(current_session)):
    if not 1 <= limit <= 100 or offset < 0:
        raise HTTPException(422, 'Invalid pagination')
    with database() as db:
        if owned:
            rows = db.execute('SELECT * FROM user_videos WHERE owner_id=%s AND (%s::text IS NULL OR route_id=%s) '
                              'AND (%s::boolean IS NULL OR share_as_beta=%s) ORDER BY created_at DESC LIMIT %s OFFSET %s',
                              (session['id'], route_id, route_id, share_as_beta, share_as_beta, limit, offset)).fetchall()
        else:
            rows = db.execute('SELECT v.*,u.username,u.display_name,'
                              'CASE WHEN v.share_as_beta THEN u.height_cm ELSE NULL END AS height_cm,'
                              'CASE WHEN v.share_as_beta THEN u.arm_span_cm ELSE NULL END AS arm_span_cm '
                              'FROM user_videos v JOIN users u ON u.id=v.owner_id '
                              'WHERE v.visibility=\'public\' AND (%s::text IS NULL OR v.route_id=%s) '
                              'AND (%s::boolean IS NULL OR v.share_as_beta=%s) ORDER BY v.created_at DESC LIMIT %s OFFSET %s',
                              (route_id, route_id, share_as_beta, share_as_beta, limit, offset)).fetchall()
    items = []
    for row in rows:
        item = video_dict(row)
        if 'username' in row:
            item['username'] = row['username']
            item['display_name'] = row['display_name']
            item['height_cm'] = row['height_cm']
            item['arm_span_cm'] = row['arm_span_cm']
        items.append(item)
    return {'items': items, 'limit': limit, 'offset': offset}


@app.get('/api/videos/{video_id}')
def get_video(video_id: str, session=Depends(current_session)):
    return video_dict(video_for_access(video_id, session))


@app.get('/api/videos/{video_id}/content')
def video_content(video_id: str, request: Request, session=Depends(current_session)):
    row = video_for_access(video_id, session)
    path = (UPLOAD_DIR / row['storage_key']).resolve()
    if not path.is_relative_to(UPLOAD_DIR) or not path.is_file():
        raise HTTPException(404, 'Stored video not found')
    size = path.stat().st_size
    range_header = request.headers.get('range')
    start, end, status = 0, size - 1, 200
    if range_header:
        match = RANGE_RE.fullmatch(range_header)
        if not match:
            return Response(status_code=416, headers={'Content-Range': f'bytes */{size}'})
        first, last = match.groups()
        if first:
            start = int(first)
            end = min(int(last), size - 1) if last else size - 1
        elif last:
            start = max(0, size - int(last))
        if start >= size or end < start:
            return Response(status_code=416, headers={'Content-Range': f'bytes */{size}'})
        status = 206
    length = end - start + 1
    def chunks():
        with path.open('rb') as f:
            f.seek(start)
            remaining = length
            while remaining:
                data = f.read(min(CHUNK_SIZE, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data
    headers = {'Accept-Ranges': 'bytes', 'Content-Length': str(length),
               'Cache-Control': 'private, no-store', 'Content-Disposition': 'inline',
               'X-Content-Type-Options': 'nosniff'}
    if status == 206:
        headers['Content-Range'] = f'bytes {start}-{end}/{size}'
    return StreamingResponse(chunks(), status_code=status, media_type=row['media_type'], headers=headers)


class VisibilityUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    visibility: str
    share_as_beta: bool = False


@app.patch('/api/videos/{video_id}')
def update_video(video_id: str, body: VisibilityUpdate, session=Depends(current_session)):
    visibility = body.visibility
    if visibility not in ('private', 'public'):
        raise HTTPException(422, 'Visibility must be private or public')
    with database() as db:
        if body.share_as_beta and visibility != 'public':
            raise HTTPException(422, 'Community Beta sharing requires a public video')
        row = db.execute('UPDATE user_videos SET visibility=%s,share_as_beta=%s WHERE id=%s AND owner_id=%s RETURNING *',
                         (visibility, body.share_as_beta, video_id, session['id'])).fetchone()
    if not row:
        raise HTTPException(404, 'Video not found')
    return video_dict(row)


@app.delete('/api/videos/{video_id}', status_code=204)
def delete_video(video_id: str, session=Depends(current_session)):
    with database() as db:
        row = db.execute('DELETE FROM user_videos WHERE id=%s AND owner_id=%s RETURNING storage_key',
                         (video_id, session['id'])).fetchone()
    if not row:
        raise HTTPException(404, 'Video not found')
    path = (UPLOAD_DIR / row['storage_key']).resolve()
    if path.is_relative_to(UPLOAD_DIR):
        path.unlink(missing_ok=True)
