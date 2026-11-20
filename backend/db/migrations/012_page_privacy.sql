ALTER TABLE users ADD COLUMN account_visibility text NOT NULL DEFAULT 'public' CHECK (account_visibility IN ('private','public'));
ALTER TABLE users ADD COLUMN calendar_visible boolean NOT NULL DEFAULT false;
