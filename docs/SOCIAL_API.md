# Social API contract (B · N1.3)

Owner: B (Comment, Follow, author page). Code: `backend/routes/social.py`, `src/features/community/`.
Migrations: `012_social_interactions.sql`, `013_follows.sql`, `014_social_sample_videos.sql`.
Tests: `tests/compute/test_social.py`.

All paths are under `/api`. Every endpoint requires a signed-in session cookie; writes (`POST`, `PUT`, `PATCH`, `DELETE`) also need `X-CSRF-Token` and an allowed `Origin`, like the rest of the API.

## Video ids and access

A social video id is either:

- an uploaded video's UUID, readable by its owner, or by anyone signed in while it is public; or
- a bundled sample registered in `sample_videos`: `sample-a1`–`sample-a3` (sample attempts) and `preset-beta-b1`–`preset-beta-b3` (preset Community Beta). Samples are public demo content.

The app maps page-level ids to social ids with `socialVideoKey`: `a1` becomes `sample-a1` and `b1` becomes `preset-beta-b1`.

The service never reveals whether something exists that the caller may not see:

| Situation | Response |
| --- | --- |
| Unknown id, malformed id, or another user's private video | `404` |
| Valid target, but the action is not allowed (deleting someone else's comment) | `403` |
| Invalid body, bad pagination (`limit` 1–100, `offset` ≥ 0), following yourself | `422` |
| No session | `401` |

Errors use the API's shared shape (`backend/app.py`): `{"error": {"message": "Video not found"}}`. Invalid fields return `{"error": {"message": "Invalid request fields"}}` without echoing input.

When a video turns private, its social rows are kept but hidden from everyone except the owner. They come back if it becomes public again. Deleting a video deletes its comments, likes, saves and shares (trigger `user_videos_social_cleanup`).

## Comments

| Method and path | Purpose |
| --- | --- |
| `GET /videos/{id}/comments?limit=20&offset=0` | Top-level comments, oldest first |
| `POST /videos/{id}/comments` | Body `{body, time_s?, parent_id?}`; returns `201` with the comment |
| `GET /comments/{id}/replies?limit=20&offset=0` | Replies to a top-level comment |
| `DELETE /comments/{id}` | Author only (`204`). Deleting a top-level comment removes its replies |
| `PUT` / `DELETE /comments/{id}/like` | `{liked, like_count}`; idempotent |

Rules:

- `body` is trimmed and must be 1–500 characters.
- `time_s` is the playback second, from 0 to 3600, clamped to the video's length. Top-level comments with a `time_s` appear as live comments (danmaku).
- Threads go one level deep. A reply to a reply attaches to the same top-level comment and sets `reply_to` (shown as @name).

Example `GET /videos/preset-beta-b1/comments`:

```json
{
  "items": [{
    "id": "4c1e…", "video_id": "preset-beta-b1", "parent_id": null,
    "body": "Great heel hook", "time_s": 2.4, "created_at": "2026-11-19T22:10:00+00:00",
    "author": {"id": "9a0d…", "username": "bob", "display_name": "Bob"},
    "reply_to": null, "like_count": 1, "liked": false, "reply_count": 2, "can_delete": false
  }],
  "total": 1, "total_with_replies": 3, "limit": 20, "offset": 0
}
```

## Reactions

| Method and path | Response |
| --- | --- |
| `PUT` / `DELETE /videos/{id}/like` | `{liked, like_count}` |
| `PUT` / `DELETE /videos/{id}/save` | `{saved}`; unsaving works even after the video turned private |
| `POST /videos/{id}/share` | `{share_count}`; counts people, not clicks |
| `GET /videos/{id}/danmaku` | `{items: [{id, body, time_s, author, mine}]}`, in playback order, at most 500 |
| `GET /social/videos?ids=a,b,…` | `{items: {id: {like_count, comment_count, share_count, liked, saved}}}`; up to 100 ids; ids the caller cannot see are omitted |
| `GET /me/saved-videos?limit=50&offset=0` | Newest first; only videos still visible |

`saved-videos` returns uploads with full video fields. `height_cm` and `arm_span_cm` are included only for Beta shares. Samples come back short: `{id, title, duration_seconds, is_preset_sample: true, saved_at}`. The app fills in their media.

## Routes and people

| Method and path | Response |
| --- | --- |
| `GET /me/wanted-routes` | `{items: [{route_id, created_at}]}` |
| `PUT` / `DELETE /routes/{id}/want` | `{wanted}`; `404` for unknown routes |
| `PUT` / `DELETE` / `GET /users/{id}/follow` | `{following, follower_count}`; idempotent; `422` for yourself |
| `GET /me/following` | `{items: [{id, username, display_name, followed_at}]}` |
| `GET /me/social-stats` | `{likes_received, saves_received, followers, following}` for My Page |
| `GET /videos?owned=false&following=true` | Newest public uploads from accounts the current user follows; pagination uses the normal `limit` / `offset` parameters |
| `GET /users/{id}/profile?limit=20&offset=0` | Author page, described below |

Following someone never unlocks their private videos.

`/me/social-stats` counts persistent likes and saves received by the signed-in
user's uploaded videos, plus their follower/following rows. Received counts are
owner-only lifetime statistics: making a video private hides it from other
people but does not erase its existing interactions from the owner's My Page.

### Author page (N2.8): `GET /users/{id}/profile`

The response is always the public view, even when you open your own page:

- It includes identity, follow counts and public videos.
- It never includes private videos, saved items, Want to Try, skeletons or notifications.
- It includes body measurements only on Beta shares.

```json
{
  "id": "1f2e…", "username": "sonia_demo", "display_name": "sonia_demo",
  "joined_at": "2026-11-10T15:00:00+00:00", "account_visibility": "public", "is_me": false,
  "follower_count": 3, "following_count": 1, "following": true, "public_video_count": 1,
  "videos": [{"id": "af4c…", "title": "Blue 7518 first try", "share_as_beta": true,
              "content_url": "/api/videos/af4c…/content", "height_cm": 165, "arm_span_cm": 168, "…": "…"}],
  "limit": 20, "offset": 0
}
```

**Merged with A (N2.5):** this endpoint honors `account_visibility` and `library_visible`. A private profile returns username/ID, a private-account marker and no videos or profile statistics; a public profile with Library hidden returns no profile videos. This is the public preview even for its owner. Individually Public videos remain accessible in Community. Extended body/calendar/collection preferences use A’s `/users/{id}/page` endpoint; collection display and My Page social statistics still need integration. Follow-approval rules remain pending N1.2.

Frontend entry points:

- Tap the author's avatar or name in the Community viewer.
- Swipe right on the video. With a mouse, drag right.
- Left swipe stays "back", and vertical swipes still move between videos.
- Sample videos have no author, so a swipe on one shows a short notice instead.

## Proposed decisions for N1.2 (B items, pending team confirmation)

These are recommendations, not settled rules. The checklist row stays open until A and B agree.

1. **Private accounts and follows.** Recommended: follow requests that need approval, using a `follows.status` of `pending` or `accepted`. A pending request shows as "Requested". Approval still never grants access to private videos; videos keep their own visibility. Rejected alternative: open follows on private accounts, because they would reveal that the account exists and is active.
2. **Follower and following lists.** Recommended: show counts only for the demo. Show lists to the owner only. Public lists can wait until account visibility exists.
3. **Following feed.** Implemented as an All / Following switch. Following is a server-filtered list of public uploads only; it excludes bundled presets and never grants access to private videos.
4. **Self-view.** Your own author page shows the public view, with a link to My Library (implemented).
