"""B: Community interactions - comments and replies, comment likes, danmaku,
shares, video likes, saved Beta, want-to-try routes and follows.

Every rule follows the video's own access rule (videos.video_for_access): the
owner, or any signed-in user while the video is public. Bundled sample and
preset Beta videos (table sample_videos, ids such as "sample-a1") are public
demo content and accept the same interactions. Anything a user may not see is
reported as 404, so private videos never leak through these endpoints.
Contract: README section "Social interactions".
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


def sample_video(video_id):
    with database() as db:
        return db.execute('SELECT id, title, duration_seconds FROM sample_videos WHERE id = %s',
                          (video_id,)).fetchone()


def video_for_access(video_id, user):
    """The video row (uploaded or sample) the user may see; otherwise 404."""
    sample = sample_video(video_id)
    if sample:
        return {**sample, 'is_sample': True}
    parse_uuid(video_id, 'Video not found')
    return _video_for_access(video_id, user)


COMMENT_MAX = 500


def accessible_key(column):
    """SQL condition: the social key in `column` is a sample, or an uploaded video the user may read."""
    return (f"(EXISTS (SELECT 1 FROM sample_videos sv WHERE sv.id = {column}) OR EXISTS ("
            f"SELECT 1 FROM user_videos v WHERE v.id = social_video_uuid({column}) "
            "AND (v.owner_id = %(user)s OR v.visibility = 'public')))")


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
    row = db.execute(f'SELECT c.* FROM video_comments c WHERE c.id = %(id)s AND {accessible_key("c.video_id")}',
                     {'id': comment_id, 'user': user['id']}).fetchone()
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
    video_id = str(video_for_access(video_id, session)['id'])  # canonical key
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
    video_id = str(video['id'])
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
    video_id = str(video_for_access(video_id, session)['id'])  # canonical key
    with database() as db:
        rows = db.execute('SELECT c.id, c.body, c.time_s, c.author_id, u.display_name FROM video_comments c '
                          'JOIN users u ON u.id = c.author_id WHERE c.video_id = %s AND c.time_s IS NOT NULL '
                          'AND c.parent_id IS NULL ORDER BY c.time_s, c.created_at LIMIT 500', (video_id,)).fetchall()
    return {'items': [{'id': str(r['id']), 'body': r['body'], 'time_s': r['time_s'], 'author': r['display_name'],
                       'mine': r['author_id'] == session['id']} for r in rows]}


@router.post('/api/videos/{video_id}/share')
def share_video(video_id: str, session=Depends(current_session)):
    """Records that the caller shared the video; counts people, so repeats do not inflate it."""
    video_id = str(video_for_access(video_id, session)['id'])  # canonical key
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
    video_id = str(video_for_access(video_id, session)['id'])  # canonical key
    with database() as db:
        db.execute('INSERT INTO video_likes(user_id, video_id) VALUES (%s, %s) ON CONFLICT DO NOTHING',
                   (session['id'], video_id))
        return {'liked': True, 'like_count': _like_count(db, video_id)}


@router.delete('/api/videos/{video_id}/like')
def unlike_video(video_id: str, session=Depends(current_session)):
    video_id = str(video_for_access(video_id, session)['id'])  # canonical key
    with database() as db:
        db.execute('DELETE FROM video_likes WHERE user_id = %s AND video_id = %s', (session['id'], video_id))
        return {'liked': False, 'like_count': _like_count(db, video_id)}


@router.put('/api/videos/{video_id}/save')
def save_video(video_id: str, session=Depends(current_session)):
    video_id = str(video_for_access(video_id, session)['id'])  # canonical key
    with database() as db:
        db.execute('INSERT INTO saved_videos(user_id, video_id) VALUES (%s, %s) ON CONFLICT DO NOTHING',
                   (session['id'], video_id))
    return {'saved': True}


@router.delete('/api/videos/{video_id}/save')
def unsave_video(video_id: str, session=Depends(current_session)):
    # Unsaving needs no access check: it only removes the caller's own row,
    # so a video that went private can still be cleared from "Saved".
    try:
        video_id = str(UUID(video_id))
    except ValueError:
        pass  # sample ids are stored as given
    with database() as db:
        db.execute('DELETE FROM saved_videos WHERE user_id = %s AND video_id = %s', (session['id'], video_id))
    return {'saved': False}


@router.get('/api/me/saved-videos')
def saved_videos(limit: int = 50, offset: int = 0, session=Depends(current_session)):
    """Saved videos the caller can still see, newest first.

    Uploaded videos come with their full video fields. Samples come as
    {id, title, duration_seconds, is_preset_sample: true, saved_at}; the app
    already holds their media and fills in the rest.
    """
    page_args(limit, offset)
    with database() as db:
        keys = db.execute(
            f'SELECT s.video_id, s.created_at FROM saved_videos s WHERE s.user_id = %(user)s '
            f'AND {accessible_key("s.video_id")} ORDER BY s.created_at DESC, s.video_id '
            'LIMIT %(limit)s OFFSET %(offset)s',
            {'user': session['id'], 'limit': limit, 'offset': offset}).fetchall()
        ids = [k['video_id'] for k in keys]
        uploads = {str(r['id']): r for r in db.execute(
            'SELECT v.*, u.username, u.display_name, '
            'CASE WHEN v.share_as_beta THEN u.height_cm ELSE NULL END AS height_cm, '
            'CASE WHEN v.share_as_beta THEN u.arm_span_cm ELSE NULL END AS arm_span_cm '
            'FROM user_videos v JOIN users u ON u.id = v.owner_id '
            'WHERE v.id = ANY(SELECT social_video_uuid(k) FROM unnest(%s::text[]) k)', (ids,)).fetchall()}
        samples = {r['id']: r for r in db.execute(
            'SELECT * FROM sample_videos WHERE id = ANY(%s)', (ids,)).fetchall()}
    items = []
    for key in keys:
        saved_at = key['created_at'].isoformat()
        if key['video_id'] in samples:
            sample = samples[key['video_id']]
            items.append({'id': sample['id'], 'title': sample['title'], 'duration_seconds': sample['duration_seconds'],
                          'is_preset_sample': True, 'saved_at': saved_at})
            continue
        row = uploads[key['video_id']]
        item = video_dict(row)
        item.update(username=row['username'], display_name=row['display_name'], height_cm=row['height_cm'],
                    arm_span_cm=row['arm_span_cm'], saved_at=saved_at)
        items.append(item)
    return {'items': items, 'limit': limit, 'offset': offset}


@router.get('/api/social/videos')
def social_summary(ids: str = Query(..., max_length=4000), session=Depends(current_session)):
    """Counts and the caller's own state for up to 100 videos in one request.

    Samples are included. IDs the caller may not see, or that name nothing, are
    simply absent from the result, so lists can pass every visible card's id.
    """
    wanted = list(dict.fromkeys(part.strip() for part in ids.split(',') if part.strip()))
    if len(wanted) > 100:
        raise HTTPException(422, 'At most 100 ids per request')
    if not wanted:
        return {'items': {}}
    with database() as db:
        rows = db.execute(
            'SELECT k.id, '
            '(SELECT count(*) FROM video_likes l WHERE l.video_id = k.id) AS like_count, '
            '(SELECT count(*) FROM video_comments c WHERE c.video_id = k.id) AS comment_count, '
            '(SELECT count(*) FROM video_shares sh WHERE sh.video_id = k.id) AS share_count, '
            'EXISTS (SELECT 1 FROM video_likes l WHERE l.video_id = k.id AND l.user_id = %(user)s) AS liked, '
            'EXISTS (SELECT 1 FROM saved_videos s WHERE s.video_id = k.id AND s.user_id = %(user)s) AS saved '
            f'FROM unnest(%(ids)s::text[]) AS k(id) WHERE {accessible_key("k.id")}',
            {'user': session['id'], 'ids': wanted}).fetchall()
    return {'items': {r['id']: {'like_count': r['like_count'], 'comment_count': r['comment_count'],
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


# ------------------------------------------------------------------ follows (N2.7)

def _follow_state(db, followee_id, follower_id):
    row = db.execute('SELECT count(*) AS followers, '
                     'bool_or(follower_id = %s) AS following FROM follows WHERE followee_id = %s',
                     (follower_id, followee_id)).fetchone()
    return {'following': bool(row['following']), 'follower_count': row['followers']}


def _existing_user(db, user_id):
    parse_uuid(user_id, 'User not found')
    if not db.execute('SELECT 1 FROM users WHERE id = %s', (user_id,)).fetchone():
        raise HTTPException(404, 'User not found')


@router.put('/api/users/{user_id}/follow')
def follow_user(user_id: str, session=Depends(current_session)):
    """Idempotent. Following someone does not unlock any of their private content."""
    with database() as db:
        _existing_user(db, user_id)
        if str(session['id']) == str(parse_uuid(user_id)):
            raise HTTPException(422, 'You cannot follow yourself')
        db.execute('INSERT INTO follows(follower_id, followee_id) VALUES (%s, %s) ON CONFLICT DO NOTHING',
                   (session['id'], user_id))
        return _follow_state(db, user_id, session['id'])


@router.delete('/api/users/{user_id}/follow')
def unfollow_user(user_id: str, session=Depends(current_session)):
    with database() as db:
        _existing_user(db, user_id)
        db.execute('DELETE FROM follows WHERE follower_id = %s AND followee_id = %s', (session['id'], user_id))
        return _follow_state(db, user_id, session['id'])


@router.get('/api/users/{user_id}/follow')
def follow_status(user_id: str, session=Depends(current_session)):
    with database() as db:
        _existing_user(db, user_id)
        return _follow_state(db, user_id, session['id'])


@router.get('/api/me/following')
def following(session=Depends(current_session)):
    """Accounts the caller follows (public identity only), newest first."""
    with database() as db:
        rows = db.execute('SELECT u.id, u.username, u.display_name, f.created_at FROM follows f '
                          'JOIN users u ON u.id = f.followee_id WHERE f.follower_id = %s ORDER BY f.created_at DESC',
                          (session['id'],)).fetchall()
    return {'items': [{'id': str(r['id']), 'username': r['username'], 'display_name': r['display_name'],
                       'followed_at': r['created_at'].isoformat()} for r in rows]}


# --------------------------------------------------------- author page (N2.8)

@router.get('/api/users/{user_id}/profile')
def public_profile(user_id: str, limit: int = 20, offset: int = 0, session=Depends(current_session)):
    """What anyone signed in may see of an account: identity, follow counts and public videos.

    Interim contract until A's account visibility (N2.5) lands: every account is
    treated as public. Never includes private videos, saved items, Want to Try,
    skeletons, notifications or body measurements outside Beta shares, even for
    the owner, so the page always shows the public view.
    """
    page_args(limit, offset)
    with database() as db:
        _existing_user(db, user_id)
        user = db.execute('SELECT id, username, display_name, created_at FROM users WHERE id = %s',
                          (user_id,)).fetchone()
        counts = db.execute(
            'SELECT (SELECT count(*) FROM follows WHERE followee_id = %(u)s) AS followers, '
            '(SELECT count(*) FROM follows WHERE follower_id = %(u)s) AS following, '
            'EXISTS (SELECT 1 FROM follows WHERE followee_id = %(u)s AND follower_id = %(me)s) AS followed, '
            "(SELECT count(*) FROM user_videos WHERE owner_id = %(u)s AND visibility = 'public') AS videos",
            {'u': user_id, 'me': session['id']}).fetchone()
        rows = db.execute(
            'SELECT v.*, u.username, u.display_name, '
            'CASE WHEN v.share_as_beta THEN u.height_cm ELSE NULL END AS height_cm, '
            'CASE WHEN v.share_as_beta THEN u.arm_span_cm ELSE NULL END AS arm_span_cm '
            "FROM user_videos v JOIN users u ON u.id = v.owner_id WHERE v.owner_id = %s AND v.visibility = 'public' "
            'ORDER BY v.created_at DESC, v.id LIMIT %s OFFSET %s', (user_id, limit, offset)).fetchall()
    videos = []
    for row in rows:
        item = video_dict(row)
        item.update(username=row['username'], display_name=row['display_name'],
                    height_cm=row['height_cm'], arm_span_cm=row['arm_span_cm'])
        videos.append(item)
    return {
        'id': str(user['id']), 'username': user['username'], 'display_name': user['display_name'],
        'joined_at': user['created_at'].isoformat(), 'account_visibility': 'public',
        'is_me': user['id'] == session['id'],
        'follower_count': counts['followers'], 'following_count': counts['following'],
        'following': counts['followed'], 'public_video_count': counts['videos'],
        'videos': videos, 'limit': limit, 'offset': offset,
    }
