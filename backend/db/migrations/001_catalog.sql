CREATE TABLE gyms (
    id text PRIMARY KEY,
    name text NOT NULL,
    location_label text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE routes (
    id text PRIMARY KEY,
    gym_id text NOT NULL REFERENCES gyms(id) ON DELETE RESTRICT,
    name text NOT NULL,
    grade text NOT NULL,
    set_label text NOT NULL DEFAULT '',
    archived boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX routes_gym_archive_idx ON routes(gym_id, archived, id);

-- Catalog examples are separate from future user-owned uploads.
-- Keys are relative to the selected storage backend, never absolute paths.
CREATE TABLE route_media (
    id text PRIMARY KEY,
    route_id text NOT NULL REFERENCES routes(id) ON DELETE RESTRICT,
    kind text NOT NULL CHECK (kind IN ('reference_video', 'poster', 'wall_image', 'pose_video')),
    storage_backend text NOT NULL DEFAULT 'bundled' CHECK (storage_backend IN ('bundled', 'local', 'object')),
    storage_key text NOT NULL CHECK (storage_key <> '' AND storage_key !~ '(^/|(^|/)\.\.(/|$))'),
    is_example boolean NOT NULL DEFAULT true,
    is_primary boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX route_media_route_idx ON route_media(route_id, kind);
CREATE UNIQUE INDEX route_media_primary_idx ON route_media(route_id, kind) WHERE is_primary;
