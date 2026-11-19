"""Gym and route catalog endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from ..database import database
from ..auth import current_session

router = APIRouter()

@router.get('/api/gyms')
def gyms(session=Depends(current_session)):
    with database() as db:
        items = db.execute('SELECT g.*,count(r.id) FILTER (WHERE NOT r.archived) AS active_route_count '
                           'FROM gyms g LEFT JOIN routes r ON r.gym_id=g.id GROUP BY g.id ORDER BY g.id').fetchall()
    return {'items': items}


@router.get('/api/routes')
def routes(gym_id: str | None = None, include_archived: bool = False,
           limit: int = 50, offset: int = 0, session=Depends(current_session)):
    if not 1 <= limit <= 100 or offset < 0:
        raise HTTPException(422, 'Invalid pagination')
    with database() as db:
        items = db.execute('SELECT * FROM routes WHERE (%s::text IS NULL OR gym_id=%s) '
                           'AND (%s OR NOT archived) ORDER BY id LIMIT %s OFFSET %s',
                           (gym_id, gym_id, include_archived, limit, offset)).fetchall()
    return {'items': items, 'limit': limit, 'offset': offset}


@router.get('/api/routes/{route_id}')
def route(route_id: str, session=Depends(current_session)):
    with database() as db:
        item = db.execute('SELECT * FROM routes WHERE id=%s', (route_id,)).fetchone()
        if not item:
            raise HTTPException(404, 'Route not found')
        item['media'] = db.execute('SELECT * FROM route_media WHERE route_id=%s ORDER BY id', (route_id,)).fetchall()
    return item
