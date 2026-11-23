-- Prepared demonstrations are not compute tasks or personalized generation results.
CREATE TABLE demo_previews (
    video_id uuid PRIMARY KEY REFERENCES user_videos(id) ON DELETE CASCADE,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE saved_demo_previews (
    owner_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    video_id uuid NOT NULL REFERENCES demo_previews(video_id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (owner_id, video_id)
);
