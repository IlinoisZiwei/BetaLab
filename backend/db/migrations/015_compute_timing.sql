-- Keep historical unknown timings null; never infer a worker start from creation.
ALTER TABLE compute_tasks ADD COLUMN started_at timestamptz;
ALTER TABLE compute_tasks ADD COLUMN finished_at timestamptz;
