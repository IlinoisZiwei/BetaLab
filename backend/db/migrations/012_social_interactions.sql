-- B: persistent Community interactions (backend/routes/social.py).
-- Access always follows the video: its owner, or any signed-in user while it
-- is public; the API reports everything else as 404. Rows of a video that
-- becomes private are kept but hidden until it is public again. Deleting a
-- video removes all of its rows.

-- One level of threads: replies always hang off a top-level comment;
-- reply_to_user_id records whom a reply-to-a-reply answers (@name).
-- time_s is the playback second when a top-level comment was posted (danmaku).
CREATE TABLE video_comments (
    id uuid PRIMARY KEY,
    video_id uuid NOT NULL REFERENCES user_videos(id) ON DELETE CASCADE,
    author_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parent_id uuid REFERENCES video_comments(id) ON DELETE CASCADE,
    reply_to_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    body text NOT NULL CHECK (char_length(btrim(body)) BETWEEN 1 AND 500),
    time_s double precision CHECK (time_s IS NULL OR time_s >= 0),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX video_comments_video_created_idx ON video_comments(video_id, created_at, id);
CREATE INDEX video_comments_parent_created_idx ON video_comments(parent_id, created_at, id) WHERE parent_id IS NOT NULL;
CREATE INDEX video_comments_video_time_idx ON video_comments(video_id, time_s) WHERE time_s IS NOT NULL;

-- One row per user and target, so repeating an action is idempotent.
CREATE TABLE comment_likes (
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    comment_id uuid NOT NULL REFERENCES video_comments(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, comment_id)
);
CREATE INDEX comment_likes_comment_idx ON comment_likes(comment_id);

CREATE TABLE video_likes (
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    video_id uuid NOT NULL REFERENCES user_videos(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, video_id)
);
CREATE INDEX video_likes_video_idx ON video_likes(video_id);

CREATE TABLE saved_videos (
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    video_id uuid NOT NULL REFERENCES user_videos(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, video_id)
);
CREATE INDEX saved_videos_user_created_idx ON saved_videos(user_id, created_at DESC);

-- Counts people who shared, not clicks.
CREATE TABLE video_shares (
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    video_id uuid NOT NULL REFERENCES user_videos(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, video_id)
);
CREATE INDEX video_shares_video_idx ON video_shares(video_id);

CREATE TABLE wanted_routes (
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    route_id text NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, route_id)
);
