-- B: bundled sample and preset Beta videos in Community can be liked, saved,
-- shared and commented on, like uploaded videos.
-- Social rows now key videos by text: an uploaded video's UUID, or the id of a
-- registered sample below. Samples are public demo content, visible to every
-- signed-in user. Uploaded videos keep their owner/public rule.

CREATE TABLE sample_videos (
    id text PRIMARY KEY CHECK (id ~ '^(sample|preset-beta)-[a-z0-9-]+$'),
    title text NOT NULL,
    duration_seconds double precision NOT NULL CHECK (duration_seconds >= 0)
);
-- Ids match the app (src/features/community/social.ts, SAMPLE_SOCIAL_IDS).
INSERT INTO sample_videos(id, title, duration_seconds) VALUES
    ('sample-a1', 'Attempt 1', 18),
    ('sample-a2', 'Attempt 2', 21),
    ('sample-a3', 'Attempt 3', 16),
    ('preset-beta-b1', 'Nora P.''s beta', 32),
    ('preset-beta-b2', 'Sam K.''s beta', 19),
    ('preset-beta-b3', 'Jo M.''s beta', 16);

ALTER TABLE video_comments DROP CONSTRAINT video_comments_video_id_fkey;
ALTER TABLE video_comments ALTER COLUMN video_id TYPE text USING video_id::text;
ALTER TABLE video_likes DROP CONSTRAINT video_likes_video_id_fkey;
ALTER TABLE video_likes ALTER COLUMN video_id TYPE text USING video_id::text;
ALTER TABLE saved_videos DROP CONSTRAINT saved_videos_video_id_fkey;
ALTER TABLE saved_videos ALTER COLUMN video_id TYPE text USING video_id::text;
ALTER TABLE video_shares DROP CONSTRAINT video_shares_video_id_fkey;
ALTER TABLE video_shares ALTER COLUMN video_id TYPE text USING video_id::text;

-- The uploaded video a social key names, or NULL for sample ids.
CREATE FUNCTION social_video_uuid(key text) RETURNS uuid
LANGUAGE sql IMMUTABLE STRICT AS $fn$
    SELECT CASE WHEN key ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                THEN key::uuid END
$fn$;

-- Replaces the old ON DELETE CASCADE: deleting a video removes its social rows.
CREATE FUNCTION social_forget_user_video() RETURNS trigger
LANGUAGE plpgsql AS $fn$
BEGIN
    DELETE FROM video_comments WHERE video_id = OLD.id::text;
    DELETE FROM video_likes WHERE video_id = OLD.id::text;
    DELETE FROM saved_videos WHERE video_id = OLD.id::text;
    DELETE FROM video_shares WHERE video_id = OLD.id::text;
    RETURN OLD;
END
$fn$;
CREATE TRIGGER user_videos_social_cleanup AFTER DELETE ON user_videos
    FOR EACH ROW EXECUTE FUNCTION social_forget_user_video();
