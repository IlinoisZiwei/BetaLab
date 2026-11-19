"""Pure policy for A integration; HTTP handlers must still call current_session.

Derived-result rule proposed for team review: owner-only AND live source access.
Do not use a cached public flag or treat a UUID as authorization.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class VideoAccess:
    owner_id: str
    visibility: str
    deleted: bool = False

def source_access(user_id: str | None, video: VideoAccess) -> bool:
    return bool(user_id) and not video.deleted and (user_id == video.owner_id or video.visibility == 'public')

def task_access(user_id: str | None, task_owner_id: str, video: VideoAccess) -> bool:
    return user_id == task_owner_id and source_access(user_id, video)
