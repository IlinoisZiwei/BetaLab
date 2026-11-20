ALTER TABLE users ADD COLUMN bio text NOT NULL DEFAULT '' CHECK (length(bio) <= 500);
ALTER TABLE users ADD COLUMN measurements_visible boolean NOT NULL DEFAULT false;
ALTER TABLE users ADD COLUMN library_visible boolean NOT NULL DEFAULT false;
ALTER TABLE users ADD COLUMN likes_visible boolean NOT NULL DEFAULT false;
ALTER TABLE users ADD COLUMN saves_visible boolean NOT NULL DEFAULT false;
ALTER TABLE users ADD COLUMN skeletons_visible boolean NOT NULL DEFAULT false;
