-- Remove the Long Reach sample without deleting any user-owned videos.
UPDATE routes SET archived = true, updated_at = now() WHERE id = 'r2';
DELETE FROM route_media WHERE route_id = 'r2'
  AND NOT EXISTS (SELECT 1 FROM user_videos WHERE route_id = 'r2');
DELETE FROM routes WHERE id = 'r2'
  AND NOT EXISTS (SELECT 1 FROM user_videos WHERE route_id = 'r2');
