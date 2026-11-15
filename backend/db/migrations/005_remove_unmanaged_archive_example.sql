-- Old Slab was a one-off mock archive without an admin workflow; keep archive
-- support in the schema, but remove this misleading sample route from the demo.
DELETE FROM route_media WHERE route_id = 'r3';
DELETE FROM routes WHERE id = 'r3';
