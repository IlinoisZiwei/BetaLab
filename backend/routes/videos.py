"""Private upload storage, visibility and protected video playback."""
import os
from pathlib import Path
import subprocess
import tempfile
from uuid import uuid4
from fastapi import File, Form, UploadFile
from ..media import ranged_file
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from ..database import database
from ..auth import current_session

router = APIRouter()

UPLOAD_DIR = Path(os.getenv('UPLOAD_DIR', './data/uploads')).resolve()
MAX_UPLOAD_BYTES = int(os.getenv('MAX_UPLOAD_BYTES', 209715200))
MAX_VIDEO_SECONDS = float(os.getenv('MAX_VIDEO_SECONDS', '90'))
CHUNK_SIZE = 1024 * 1024
UPLOAD_TYPES = {'video/mp4': '.mp4', 'video/quicktime': '.mov'}


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


@router.post('/api/videos', status_code=201)
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
    if media_type in ('', 'application/octet-stream'):
        media_type = 'video/quicktime' if Path(video.filename).suffix.lower() == '.mov' else 'video/mp4'
    if media_type not in UPLOAD_TYPES:
        raise HTTPException(415, 'Choose an MP4 or MOV video')
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
                                    '-show_entries', 'stream=codec_type,codec_name:format=duration', '-of', 'json', str(temp_path)],
                                   capture_output=True, text=True, timeout=15, check=True)
            import json
            metadata = json.loads(probe.stdout)
            duration = float(metadata['format']['duration'])
            streams = metadata.get('streams', [])
            if not streams or any(stream.get('codec_type') != 'video' for stream in streams):
                raise ValueError('No video stream')
        except (FileNotFoundError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
            raise HTTPException(422, 'Could not verify this video. Install ffprobe and choose a valid MP4 or MOV.')
        if streams[0].get('codec_name') not in ('h264', 'hevc', 'av1', 'vp9'):
            raise HTTPException(415, 'Unsupported video encoding. Export as an H.264 MP4 and try again.')
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


@router.get('/api/videos')
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


@router.get('/api/videos/{video_id}')
def get_video(video_id: str, session=Depends(current_session)):
    return video_dict(video_for_access(video_id, session))


@router.get('/api/videos/{video_id}/content')
def video_content(video_id: str, request: Request, session=Depends(current_session)):
    row = video_for_access(video_id, session)
    path = (UPLOAD_DIR / row['storage_key']).resolve()
    if not path.is_relative_to(UPLOAD_DIR) or not path.is_file():
        raise HTTPException(404, 'Stored video not found')
    return ranged_file(path, request, row['media_type'], upload_compatibility=True,
                       extra_headers={'Content-Disposition': 'inline'})


class VideoUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    visibility: str | None = Field(default=None, pattern=r'^(private|public)$')
    share_as_beta: bool | None = None

    @field_validator('title', 'description', mode='before')
    @classmethod
    def trim_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode='after')
    def require_changes(self):
        if not self.model_fields_set or any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError('Provide at least one non-null video field')
        return self


@router.patch('/api/videos/{video_id}')
def update_video(video_id: str, body: VideoUpdate, session=Depends(current_session)):
    changes = body.model_dump(exclude_unset=True)
    with database() as db:
        current = db.execute('SELECT * FROM user_videos WHERE id=%s AND owner_id=%s FOR UPDATE',
                             (video_id, session['id'])).fetchone()
        if not current:
            raise HTTPException(404, 'Video not found')
        visibility = changes.get('visibility', current['visibility'])
        if changes.get('share_as_beta') and visibility != 'public':
            raise HTTPException(422, 'Community Beta sharing requires a public video')
        if visibility == 'private':
            changes['share_as_beta'] = False
        assignments = ','.join(field + '=%s' for field in changes)
        row = db.execute('UPDATE user_videos SET '+assignments+' WHERE id=%s AND owner_id=%s RETURNING *',
                         (*changes.values(), video_id, session['id'])).fetchone()
    return video_dict(row)


@router.delete('/api/videos/{video_id}', status_code=204)
def delete_video(video_id: str, session=Depends(current_session)):
    with database() as db:
        row = db.execute('DELETE FROM user_videos WHERE id=%s AND owner_id=%s RETURNING storage_key',
                         (video_id, session['id'])).fetchone()
    if not row:
        raise HTTPException(404, 'Video not found')
    path = (UPLOAD_DIR / row['storage_key']).resolve()
    if path.is_relative_to(UPLOAD_DIR):
        path.unlink(missing_ok=True)
