"""Prepared demonstrations, separate from personalized scientific computation."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from backend.auth import current_session
from backend.database import database
from . import service
from .media import stream_artifact

router = APIRouter(prefix='/api/demo-previews', tags=['demo'])


def lookup(db, video_id, user_id):
    service.source(db, video_id, user_id, lock=True)
    row = db.execute('SELECT payload FROM demo_previews WHERE video_id=%s', (video_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'No prepared demonstration for this video')
    return row['payload']


def public_payload(payload, video_id):
    return {**{k: v for k, v in payload.items() if k != 'artifacts'},
            'video_id': str(video_id), 'precomputed': True,
            'live_generation_enabled': False,
            'video_url': f'/api/demo-previews/{video_id}/media/video'}


@router.get('/saved')
def saved(session=Depends(current_session)):
    with database() as db:
        rows = db.execute("SELECT d.video_id,d.payload FROM saved_demo_previews s "
            "JOIN demo_previews d ON d.video_id=s.video_id JOIN user_videos v ON v.id=d.video_id "
            "WHERE s.owner_id=%s AND (v.owner_id=%s OR v.visibility='public') ORDER BY s.created_at DESC",
            (session['id'], session['id'])).fetchall()
    return {'items': [public_payload(r['payload'], r['video_id']) for r in rows]}


@router.get('/route/{route_id}/wall')
def wall(route_id: str, request: Request, session=Depends(current_session)):
    with database() as db:
        row = db.execute("SELECT d.payload FROM demo_previews d JOIN user_videos v ON v.id=d.video_id "
            "WHERE v.route_id=%s AND (v.owner_id=%s OR v.visibility='public') ORDER BY d.created_at LIMIT 1",
            (route_id, session['id'])).fetchone()
        if not row:
            raise HTTPException(404, 'Demo wall unavailable')
    return stream_artifact(row['payload'], 'wall', request)


@router.get('/{video_id}')
def preview(video_id: UUID, session=Depends(current_session)):
    with database() as db:
        return public_payload(lookup(db, video_id, session['id']), video_id)


@router.post('/{video_id}/save')
def save(video_id: UUID, session=Depends(current_session)):
    with database() as db:
        payload = lookup(db, video_id, session['id'])
        db.execute('INSERT INTO saved_demo_previews(owner_id,video_id) VALUES (%s,%s) ON CONFLICT DO NOTHING',
                   (session['id'], video_id))
    return public_payload(payload, video_id)


@router.get('/{video_id}/media/{name}')
def media(video_id: UUID, name: str, request: Request, session=Depends(current_session)):
    if name not in ('video', 'wall'):
        raise HTTPException(404, 'Demo media unavailable')
    with database() as db:
        payload = lookup(db, video_id, session['id'])
    return stream_artifact(payload, name, request)
