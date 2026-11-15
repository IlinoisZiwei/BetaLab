ALTER TABLE user_videos ADD COLUMN storage_backend text NOT NULL DEFAULT 'local'
    CHECK (storage_backend IN ('local', 'object'));
