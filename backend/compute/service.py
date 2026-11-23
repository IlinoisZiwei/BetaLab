"""Persistent task operations. Every user-facing read rechecks source access."""
import hashlib
import json
from uuid import UUID, uuid4
from fastapi import HTTPException
from psycopg.types.json import Jsonb
from backend.database import database
from .contracts import Task, Result, Error
from . import storage

ACCESS = "(v.owner_id=t.owner_id OR v.visibility='public')"
SELECT = 'SELECT t.*, r.payload AS result FROM compute_tasks t LEFT JOIN compute_results r ON r.task_id=t.id '

def task_payload(row):
    keys = ('id','owner_id','source_video_id','kind','state','stage','is_mock','attempt','retry_of',
            'created_at','updated_at','started_at','finished_at','error','result')
    data = {k: row.get(k) for k in keys}
    for key in ('id','owner_id','source_video_id','retry_of'):
        if data[key] is not None:
            data[key] = str(data[key])
    for key in ('created_at','updated_at','started_at','finished_at'):
        data[key] = data[key].isoformat() if data[key] else None
    return Task.model_validate(data).model_dump(mode='json')

def source(db, video_id, user_id, lock=False):
    try:
        video_id = UUID(str(video_id))
    except ValueError:
        raise HTTPException(422, 'Invalid video ID')
    row = db.execute('SELECT * FROM user_videos WHERE id=%s' + (' FOR SHARE' if lock else ''), (video_id,)).fetchone()
    if not row or (str(row['owner_id']) != str(user_id) and row['visibility'] != 'public'):
        raise HTTPException(404, 'Source unavailable')
    return row

def check_request(db, request, owner_id):
    video = source(db, request['video_id'], owner_id, lock=True)
    if request['kind'] == 'analyze':
        if request['route_id'] != video['route_id']:
            raise HTTPException(422, 'Route does not match video')
    else:
        try:
            analysis_id = UUID(request['source_analysis_id'])
        except ValueError:
            raise HTTPException(422, 'Invalid source analysis ID')
        # Public source analysis can seed another user's private generation.
        row = db.execute(SELECT + 'WHERE t.id=%s FOR SHARE OF t', (analysis_id,)).fetchone()
        if not row or str(row['source_video_id']) != request['video_id'] or row['kind'] != 'analyze':
            raise HTTPException(404, 'Source analysis unavailable')
        if row['state'] != 'succeeded' or row['result']['quality']['evidence'] == 'insufficient':
            raise HTTPException(409, 'Source analysis is not usable')
        if not row['is_mock'] and row['result']['algorithm_version'] != storage.ENGINE:
            raise HTTPException(409,'Source algorithm version changed; analyze the recording again')
        if row['result']['source_analysis_version'] != request['source_analysis_version']:
            raise HTTPException(409, 'Source analysis version changed')

    return video

def submit(request, owner_id, key, retry_of=None):
    if not key or not 1 <= len(key) <= 128:
        raise HTTPException(422, 'Provide Idempotency-Key (1–128 characters)')
    fingerprint = hashlib.sha256(json.dumps(dict(request=request, retry_of=str(retry_of) if retry_of else None), sort_keys=True).encode()).hexdigest()
    with database() as db:
        video = check_request(db, request, owner_id)
        if db.execute('SELECT 1 FROM demo_previews WHERE video_id=%s', (video['id'],)).fetchone():
            raise HTTPException(409, 'Prepared demonstration: live computation is disabled; use the demo preview')
        # Serialize same user's key so concurrent retries cannot insert duplicates.
        db.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', (str(owner_id)+':'+key,))
        old = db.execute(SELECT + 'WHERE t.owner_id=%s AND t.idempotency_key=%s', (owner_id,key)).fetchone()
        if old:
            if old['request_hash'] != fingerprint:
                raise HTTPException(409, 'Idempotency key already used for a different request')
            return task_payload(old), False
        execution = storage.execution_config(video,request)
        if execution['mode']=='real' and request['kind']=='analyze' and str(video['owner_id'])!=str(owner_id):
            raise HTTPException(404,'Only the uploader can create or correct the real source analysis')
        if request['kind']=='generate':
            analysis = db.execute('SELECT is_mock FROM compute_tasks WHERE id=%s', (request['source_analysis_id'],)).fetchone()
            if analysis['is_mock'] != (execution['mode']=='mock'):
                raise HTTPException(409,'Source analysis and requested engine modes differ; create a new source analysis')
        attempt = 1
        if retry_of:
            previous = db.execute('SELECT * FROM compute_tasks WHERE id=%s AND owner_id=%s FOR UPDATE', (retry_of,owner_id)).fetchone()
            if not previous:
                raise HTTPException(404, 'Task not found')
            if previous['state'] != 'failed' or not previous['error']['retryable']:
                raise HTTPException(409, 'Task is not retryable')
            attempt = previous['attempt'] + 1
        task_id = uuid4()
        row = db.execute('INSERT INTO compute_tasks(id,owner_id,source_video_id,kind,request,request_hash,idempotency_key,attempt,retry_of,is_mock,execution) '
            'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *',
            (task_id,owner_id,request['video_id'],request['kind'],Jsonb(request),fingerprint,key,attempt,retry_of,execution['mode']=='mock',Jsonb(execution))).fetchone()
        return task_payload(row), True

def source_analysis(video_id, owner_id, *, current_only=True):
    """Expose only a usable source reference, not another user's private task."""
    with database() as db:
        source(db, video_id, owner_id, lock=True)
        row = db.execute(SELECT + "WHERE t.source_video_id=%s AND t.kind='analyze' AND t.state='succeeded' "
            "AND r.payload->'quality'->>'evidence'<>'insufficient' ORDER BY t.created_at DESC,t.id DESC LIMIT 1",
            (video_id,)).fetchone()
        if not row:
            raise HTTPException(409, 'Source analysis not ready')
        result = row['result']
        if current_only and not row['is_mock'] and result['algorithm_version'] != storage.ENGINE:
            raise HTTPException(409, 'Source analysis is outdated; the uploader must analyze it again')
        return dict(source_analysis_id=str(row['id']), source_analysis_version=result['source_analysis_version'],
                    calibration_version=result['calibration_version'], is_mock=row['is_mock'], quality=result['quality'],
                    baseline_status=result['baseline_status'], original_body=result.get('original_body'),
                    algorithm_version=result['algorithm_version'])


def get_task(task_id, owner_id):
    with database() as db:
        row = db.execute(SELECT + f'JOIN user_videos v ON v.id=t.source_video_id WHERE t.id=%s AND t.owner_id=%s AND {ACCESS}', (task_id,owner_id)).fetchone()
        if not row:
            raise HTTPException(404, 'Task not found')
        return task_payload(row)

def retry(task_id, owner_id, key):
    get_task(task_id, owner_id)
    with database() as db:
        row = db.execute('SELECT request FROM compute_tasks WHERE id=%s AND owner_id=%s', (task_id,owner_id)).fetchone()
    return submit(row['request'], owner_id, key, retry_of=task_id)

def list_tasks(owner_id, cursor, limit):
    with database() as db:
        rows = db.execute(SELECT + f'JOIN user_videos v ON v.id=t.source_video_id WHERE t.owner_id=%s AND {ACCESS} '
            'AND (%s::uuid IS NULL OR (t.created_at,t.id)<(SELECT created_at,id FROM compute_tasks WHERE id=%s AND owner_id=%s)) '
            'ORDER BY t.created_at DESC,t.id DESC LIMIT %s', (owner_id,cursor,cursor,owner_id,limit+1)).fetchall()
    return dict(items=[task_payload(r) for r in rows[:limit]], next_cursor=str(rows[limit-1]['id']) if len(rows)>limit else None)

def notification_payload(row):
    return {k: (v.isoformat() if hasattr(v,'isoformat') else str(v) if isinstance(v,UUID) else v) for k,v in row.items()}

def notifications(owner_id, cursor, limit):
    with database() as db:
        rows = db.execute('SELECT * FROM compute_notifications WHERE owner_id=%s '
            'AND (%s::uuid IS NULL OR (created_at,id)<(SELECT created_at,id FROM compute_notifications WHERE id=%s AND owner_id=%s)) '
            'ORDER BY created_at DESC,id DESC LIMIT %s', (owner_id,cursor,cursor,owner_id,limit+1)).fetchall()
        count = db.execute('SELECT count(*) AS n FROM compute_notifications WHERE owner_id=%s AND read_at IS NULL', (owner_id,)).fetchone()['n']
    return dict(items=[notification_payload(r) for r in rows[:limit]], next_cursor=str(rows[limit-1]['id']) if len(rows)>limit else None, unread_count=count)

def mark_read(notification_id, owner_id):
    with database() as db:
        row = db.execute('UPDATE compute_notifications SET read_at=COALESCE(read_at,now()) WHERE id=%s AND owner_id=%s RETURNING *', (notification_id,owner_id)).fetchone()
        if not row:
            raise HTTPException(404, 'Notification not found')
        return notification_payload(row)

def finish(db, task, result=None, error=None):
    """Terminal task + result + unique notification commit in one transaction."""
    if (result is None) == (error is None):
        raise ValueError('Exactly one of result or error is required')
    if result is not None:
        result = Result.model_validate(result).model_dump(mode='json')
        if result['source_video_id'] != str(task['source_video_id']) or result['kind'] != task['kind'] or result['is_mock'] != task['is_mock']:
            raise ValueError('Result identity mismatch')
    if error is not None:
        error = Error.model_validate(error).model_dump()
    state = 'failed' if error else 'succeeded'
    changed = db.execute('UPDATE compute_tasks SET state=%s,stage=%s,error=%s,updated_at=now(),finished_at=now() WHERE id=%s AND state=\'running\' RETURNING id',
        (state,'failed' if error else 'complete',Jsonb(error) if error else None,task['id'])).fetchone()
    if not changed:
        return
    if result:
        db.execute('INSERT INTO compute_results(task_id,payload) VALUES (%s,%s)', (task['id'],Jsonb(result)))
    db.execute('INSERT INTO compute_notifications(id,task_id,owner_id,event,is_mock) VALUES (%s,%s,%s,%s,%s) ON CONFLICT(task_id,event) DO NOTHING',
        (uuid4(),task['id'],task['owner_id'],'task_'+state,task['is_mock']))
