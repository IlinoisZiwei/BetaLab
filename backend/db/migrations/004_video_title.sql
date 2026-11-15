ALTER TABLE user_videos ADD COLUMN title text;
UPDATE user_videos SET title = regexp_replace(original_name, '\\.[^.]+$', '');
ALTER TABLE user_videos ALTER COLUMN title SET NOT NULL;
ALTER TABLE user_videos ADD CONSTRAINT user_videos_title_length CHECK (char_length(title) BETWEEN 1 AND 120);
