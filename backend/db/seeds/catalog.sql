-- Match current frontend IDs. Rerunning never overwrites edited catalog data.
INSERT INTO gyms (id, name, location_label) VALUES
('gym-a', 'Movement Fishtown', 'North District'),
('gym-b', 'Gym B', 'West District')
ON CONFLICT (id) DO NOTHING;

INSERT INTO routes (id, gym_id, name, grade, set_label, archived) VALUES
('r1', 'gym-a', 'Corner Study', 'V3', 'Set 02', false)
ON CONFLICT (id) DO NOTHING;

INSERT INTO route_media (id, route_id, kind, storage_key, is_primary) VALUES
('r1-video', 'r1', 'reference_video', 'media/trial2.mp4', true),
('r1-poster', 'r1', 'poster', 'media/trial2-poster.jpg', true),
('r1-wall', 'r1', 'wall_image', 'media/wall2.jpg', true),
('r1-pose', 'r1', 'pose_video', 'media/pose2.mp4', true)
ON CONFLICT (id) DO NOTHING;
