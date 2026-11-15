CREATE TABLE user_videos (
    id uuid PRIMARY KEY,
    owner_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    route_id text NOT NULL REFERENCES routes(id) ON DELETE RESTRICT,
    visibility text NOT NULL DEFAULT 'private' CHECK (visibility IN ('private', 'public')),
    original_name text NOT NULL,
    description text NOT NULL DEFAULT '' CHECK (char_length(description) <= 500),
    storage_key text NOT NULL UNIQUE CHECK (storage_key <> '' AND storage_key !~ '(^/|(^|/)\.\.(/|$))'),
    media_type text NOT NULL CHECK (media_type IN ('video/mp4', 'video/quicktime')),
    size_bytes bigint NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 209715200),
    duration_seconds double precision NOT NULL CHECK (duration_seconds > 0 AND duration_seconds <= 90),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX user_videos_owner_created_idx ON user_videos(owner_id, created_at DESC);
CREATE INDEX user_videos_public_created_idx ON user_videos(created_at DESC) WHERE visibility='public';
