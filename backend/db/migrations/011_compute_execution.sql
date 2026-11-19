-- Snapshot server-selected execution settings; clients cannot request mock/real mode.
ALTER TABLE compute_tasks ADD COLUMN execution jsonb NOT NULL DEFAULT '{"mode":"mock"}'::jsonb;
