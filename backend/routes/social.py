"""B: Community interactions - comments and replies, comment likes, danmaku,
shares, video likes, saved Beta and want-to-try routes.

Every rule follows the video's own access rule (videos.video_for_access): the
owner, or any signed-in user while the video is public. Anything a user may
not see is reported as 404, so private videos never leak through these
endpoints. Contract: README section "Social interactions".
"""
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from ..auth import current_session
from ..database import database
from .videos import video_dict, video_for_access as _video_for_access

router = APIRouter()


def parse_uuid(value, message='Not found'):
    """Path IDs that are not UUIDs (e.g. bundled samples) are reported as missing, never as a 500."""
    try:
        return UUID(str(value))
    except ValueError:
        raise HTTPException(404, message)


def video_for_access(video_id, user):
    parse_uuid(video_id, 'Video not found')
    return _video_for_access(video_id, user)

COMMENT_MAX = 500
# Readable by: the owner, or anyone while public.
ACCESSIBLE = "(v.owner_id = %(user)s OR v.visibility = 'public')"


def page_args(limit: int, offset: int):
    if not 1 <= limit <= 100 or offset < 0:
        raise HTTPException(422, 'Invalid pagination')


COMMENT_SELECT = (
    'SELECT c.*, u.username, u.display_name, ru.username AS reply_to_username, ru.display_name AS reply_to_display_name, '
    '(SELECT count(*) FROM comment_likes l WHERE l.comment_id = c.id) AS like_count, '
    'EXISTS (SELECT 1 FROM comment_likes l WHERE l.comment_id = c.id AND l.user_id = %(user)s) AS liked, '
    '(SELECT count(*) FROM video_comments r WHERE r.parent_id = c.id) AS reply_count '
    'FROM video_comments c JOIN users u ON u.id = c.author_id LEFT JOIN users ru ON ru.id = c.reply_to_user_id '
)


def comment_dict(row, user_id):
    reply_to = None
    if row['reply_to_user_id']:
        reply_to = {'id': str(row['reply_to_user_id']), 'username': row['reply_to_username'],
                    'display_name': row['reply_to_display_name']}
    return {
        'id': str(row['id']),
        'video_id': str(row['video_id']),
        'parent_id': str(row['parent_id']) if row['parent_id'] else None,
        'body': row['body'],
        'time_s': row['time_s'],
        'created_at': row['created_at'].isoformat(),
        'author': {'id': str(row['author_id']), 'username': row['username'], 'display_name': row['display_name']},
        'reply_to': reply_to,
        'like_count': row['like_count'],
        'liked': row['liked'],
        'reply_count': row['reply_count'],
        'can_delete': row['author_id'] == user_id,
    }


def accessible_comment(db, comment_id, user):
    """The comment row if its video is visible to the user; otherwise 404."""
    parse_uuid(comment_id, 'Comment not found')
    row = db.execute(f'SELECT c.* FROM video_comments c JOIN user_videos v ON v.id = c.video_id '
                     f'WHERE c.id = %(id)s AND {ACCESSIBLE}', {'id': comment_id, 'user': user['id']}).fetchone()
    if not row:
        raise HTTPException(404, 'Comment not found')
    return row


# ------------------------------------------------------------------ comments

class CommentCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    body: str = Field(max_length=2000)
    # Playback position when posted; drives danmaku. Ignored on replies.
    time_s: float | None = Field(default=None, ge=0, le=3600, allow_inf_nan=False)
    # Reply target. Replying to a reply attaches to the same top-level comment and @-mentions its author.
    parent_id: str | None = None


@router.get('/api/videos/{video_id}/comments')
def list_comments(video_id: str, limit: int = 20, offset: int = 0, session=Depends(current_session)):
    """Top-level comments, oldest first. `total` counts top-level comments; `total_with_replies` everything."""
    page_args(limit, offset)
    video_for_access(video_id, session)
    with database() as db:
        rows = db.execute(COMMENT_SELECT + 'WHERE c.video_id = %(video)s AND c.parent_id IS NULL '
                          'ORDER BY c.created_at, c.id LIMIT %(limit)s OFFSET %(offset)s',
                          {'user': session['id'], 'video': video_id, 'limit': limit, 'offset': offset}).fetchall()
        counts = db.execute('SELECT count(*) FILTER (WHERE parent_id IS NULL) AS top, count(*) AS total '
                            'FROM video_comments WHERE video_id = %s', (video_id,)).fetchone()
    return {'items': [comment_dict(r, session['id']) for r in rows], 'total': counts['top'],
            'total_with_replies': counts['total'], 'limit': limit, 'offset': offset}


@router.get('/api/comments/{comment_id}/replies')
def list_replies(comment_id: str, limit: int = 20, offset: int = 0, session=Depends(current_session)):
    page_args(limit, offset)
    with database() as db:
        parent = accessible_comment(db, comment_id, session)
        if parent['parent_id']:
            raise HTTPException(404, 'Comment not found')
        rows = db.execute(COMMENT_SELECT + 'WHERE c.parent_id = %(parent)s ORDER BY c.created_at, c.id '
                          'LIMIT %(limit)s OFFSET %(offset)s',
                          {'user': session['id'], 'parent': comment_id, 'limit': limit, 'offset': offset}).fetchall()
        total = db.execute('SELECT count(*) AS n FROM video_comments WHERE parent_id = %s', (comment_id,)).fetchone()['n']
    return {'items': [comment_dict(r, session['id']) for r in rows], 'total': total, 'limit': limit, 'offset': offset}


@router.post('/api/videos/{video_id}/comments', status_code=201)
def create_comment(video_id: str, body: CommentCreate, session=Depends(current_session)):
    text = body.body.strip()
    if not 1 <= len(text) <= COMMENT_MAX:
        raise HTTPException(422, f'Comments must be 1–{COMMENT_MAX} characters')
    video = video_for_access(video_id, session)
    parent_id, reply_to, time_s = None, None, body.time_s
    with database() as db:
        if body.parent_id:
            parent = accessible_comment(db, body.parent_id, session)
            if str(parent['video_id']) != str(video['id']):
                raise HTTPException(404, 'Comment not found')
            parent_id = parent['parent_id'] or parent['id']
            reply_to = parent['author_id'] if parent['parent_id'] else None
            time_s = None
        if time_s is not None:
            time_s = min(time_s, video['duration_seconds'])
        comment_id = uuid4()
        db.execute('INSERT INTO video_comments(id, video_id, author_id, body, parent_id, reply_to_user_id, time_s) '
                   'VALUES (%s, %s, %s, %s, %s, %s, %s)',
                   (comment_id, video_id, session['id'], text, parent_id, reply_to, time_s))
        row = db.execute(COMMENT_SELECT + 'WHERE c.id = %(id)s', {'user': session['id'], 'id': comment_id}).fetchone()
    return comment_dict(row, session['id'])


@router.delete('/api/comments/{comment_id}', status_code=204)
def delete_comment(comment_id: str, session=Depends(current_session)):
    """Author only. Deleting a top-level comment also removes its replies, as on TikTok."""
    with database() as db:
        row = accessible_comment(db, comment_id, session)
        if row['author_id'] != session['id']:
            raise HTTPException(403, 'You can only delete your own comments')
        db.execute('DELETE FROM video_comments WHERE id = %s', (comment_id,))
    return Response(status_code=204)


def _comment_like_count(db, comment_id):
    return db.execute('SELECT count(*) AS n FROM comment_likes WHERE comment_id = %s', (comment_id,)).fetchone()['n']


@router.put('/api/comments/{comment_id}/like')
def like_comment(comment_id: str, session=Depends(current_session)):
    with database() as db:
        accessible_comment(db, comment_id, session)
        db.execute('INSERT INTO comment_likes(user_id, comment_id) VALUES (%s, %s) ON CONFLICT DO NOTHING',
                   (session['id'], comment_id))
        return {'liked': True, 'like_count': _comment_like_count(db, comment_id)}


@router.delete('/api/comments/{comment_id}/like')
def unlike_comment(comment_id: str, session=Depends(current_session)):
    with database() as db:
        accessible_comment(db, comment_id, session)
        db.execute('DELETE FROM comment_likes WHERE user_id = %s AND comment_id = %s', (session['id'], comment_id))
        return {'liked': False, 'like_count': _comment_like_count(db, comment_id)}


@router.get('/api/videos/{video_id}/danmaku')
def danmaku(video_id: str, session=Depends(current_session)):
    """Timestamped top-level comments for the overlay, in playback order (at most 500)."""
    video_for_access(video_id, session)
    with database() as db:
        rows = db.execute('SELECT c.id, c.body, c.time_s, c.author_id, u.display_name FROM video_comments c '
                          'JOIN users u ON u.id = c.author_id WHERE c.video_id = %s AND c.time_s IS NOT NULL '
                          'AND c.parent_id IS NULL ORDER BY c.time_s, c.created_at LIMIT 500', (video_id,)).fetchall()
    return {'items': [{'id': str(r['id']), 'body': r['body'], 'time_s': r['time_s'], 'author': r['display_name'],
                       'mine': r['author_id'] == session['id']} for r in rows]}


@router.post('/api/videos/{video_id}/share')
def share_video(video_id: str, session=Depends(current_session)):
    """Records that the caller shared the video; counts people, so repeats do not inflate it."""
    video_for_access(video_id, session)
    with database() as db:
        db.execute('INSERT INTO video_shares(user_id, video_id) VALUES (%s, %s) ON CONFLICT DO NOTHING',
                   (session['id'], video_id))
        count = db.execute('SELECT count(*) AS n FROM video_shares WHERE video_id = %s', (video_id,)).fetchone()['n']
    return {'share_count': count}


# ------------------------------------------------------------- likes & saves

def _like_count(db, video_id):
    return db.execute('SELECT count(*) AS n FROM video_likes WHERE video_id = %s', (video_id,)).fetchone()['n']


@router.put('/api/videos/{video_id}/like')
def like_video(video_id: str, session=Depends(current_session)):
    video_for_access(video_id, session)
    with database() as db:
        db.execute('INSERT INTO video_likes(user_id, video_id) VALUES (%s, %s) ON CONFLICT DO NOTHING',
                   (session['id'], video_id))
        return {'liked': True, 'like_count': _like_count(db, video_id)}


@router.delete('/api/videos/{video_id}/like')
def unlike_video(video_id: str, session=Depends(current_session)):
    video_for_access(video_id, session)
    with database() as db:
        db.execute('DELETE FROM video_likes WHERE user_id = %s AND video_id = %s', (session['id'], video_id))
        return {'liked': False, 'like_count': _like_count(db, video_id)}


@router.put('/api/videos/{video_id}/save')
def save_video(video_id: str, session=Depends(current_session)):
    video_for_access(video_id, session)
    with database() as db:
        db.execute('INSERT INTO saved_videos(user_id, video_id) VALUES (%s, %s) ON CONFLICT DO NOTHING',
                   (session['id'], video_id))
    return {'saved': True}


@router.delete('/api/videos/{video_id}/save')
def unsave_video(video_id: str, session=Depends(current_session)):
    # Unsaving needs no access check: it only removes the caller's own row,
    # so a video that went private can still be cleared from "Saved".
    parse_uuid(video_id, 'Video not found')
    with database() as db:
        db.execute('DELETE FROM saved_videos WHERE user_id = %s AND video_id = %s', (session['id'], video_id))
    return {'saved': False}


@router.get('/api/me/saved-videos')
def saved_videos(limit: int = 50, offset: int = 0, session=Depends(current_session)):
    page_args(limit, offset)
    with database() as db:
        rows = db.execute(
            'SELECT v.*, u.username, u.display_name, s.created_at AS saved_at, '
            'CASE WHEN v.share_as_beta THEN u.height_cm ELSE NULL END AS height_cm, '
            'CASE WHEN v.share_as_beta THEN u.arm_span_cm ELSE NULL END AS arm_span_cm '
            'FROM saved_videos s JOIN user_videos v ON v.id = s.video_id JOIN users u ON u.id = v.owner_id '
            f'WHERE s.user_id = %(user)s AND {ACCESSIBLE} '
            'ORDER BY s.created_at DESC LIMIT %(limit)s OFFSET %(offset)s',
            {'user': session['id'], 'limit': limit, 'offset': offset}).fetchall()
    items = []
    for row in rows:
        item = video_dict(row)
        item.update(username=row['username'], display_name=row['display_name'], height_cm=row['height_cm'],
                    arm_span_cm=row['arm_span_cm'], saved_at=row['saved_at'].isoformat())
        items.append(item)
    return {'items': items, 'limit': limit, 'offset': offset}


@router.get('/api/social/videos')
def social_summary(ids: str = Query(..., max_length=4000), session=Depends(current_session)):
    """Counts and the caller's own state for up to 100 videos in one request.

    IDs the caller may not see (or that are not UUIDs, e.g. preset samples) are
    simply absent from the result, so lists can pass every visible card's id.
    """
    wanted = []
    for raw in dict.fromkeys(part.strip() for part in ids.split(',') if part.strip()):
        try:
            wanted.append(str(parse_uuid(raw)))
        except HTTPException:
            continue
    if len(wanted) > 100:
        raise HTTPException(422, 'At most 100 ids per request')
    if not wanted:
        return {'items': {}}
    with database() as db:
        rows = db.execute(
            'SELECT v.id, '
            '(SELECT count(*) FROM video_likes l WHERE l.video_id = v.id) AS like_count, '
            '(SELECT count(*) FROM video_comments c WHERE c.video_id = v.id) AS comment_count, '
            '(SELECT count(*) FROM video_shares sh WHERE sh.video_id = v.id) AS share_count, '
            'EXISTS (SELECT 1 FROM video_likes l WHERE l.video_id = v.id AND l.user_id = %(user)s) AS liked, '
            'EXISTS (SELECT 1 FROM saved_videos s WHERE s.video_id = v.id AND s.user_id = %(user)s) AS saved '
            f'FROM user_videos v WHERE v.id = ANY(%(ids)s::uuid[]) AND {ACCESSIBLE}',
            {'user': session['id'], 'ids': wanted}).fetchall()
    return {'items': {str(r['id']): {'like_count': r['like_count'], 'comment_count': r['comment_count'],
                                     'share_count': r['share_count'], 'liked': r['liked'], 'saved': r['saved']}
                      for r in rows}}


# ------------------------------------------------------------ wanted routes

@router.get('/api/me/wanted-routes')
def wanted_routes(session=Depends(current_session)):
    with database() as db:
        rows = db.execute('SELECT route_id, created_at FROM wanted_routes WHERE user_id = %s ORDER BY created_at DESC',
                          (session['id'],)).fetchall()
    return {'items': [{'route_id': r['route_id'], 'created_at': r['created_at'].isoformat()} for r in rows]}


@router.put('/api/routes/{route_id}/want')
def want_route(route_id: str, session=Depends(current_session)):
    with database() as db:
        if not db.execute('SELECT 1 FROM routes WHERE id = %s', (route_id,)).fetchone():
            raise HTTPException(404, 'Route not found')
        db.execute('INSERT INTO wanted_routes(user_id, route_id) VALUES (%s, %s) ON CONFLICT DO NOTHING',
                   (session['id'], route_id))
    return {'wanted': True}


@router.delete('/api/routes/{route_id}/want')
def unwant_route(route_id: str, session=Depends(current_session)):
    with database() as db:
        db.execute('DELETE FROM wanted_routes WHERE user_id = %s AND route_id = %s', (session['id'], route_id))
    return {'wanted': False}
