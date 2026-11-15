ALTER TABLE user_videos ADD COLUMN share_as_beta boolean NOT NULL DEFAULT false;
ALTER TABLE user_videos ADD CONSTRAINT beta_requires_public CHECK (visibility = 'public' OR NOT share_as_beta);
CREATE INDEX user_videos_beta_route_idx ON user_videos(route_id, created_at DESC)
    WHERE visibility = 'public' AND share_as_beta;
