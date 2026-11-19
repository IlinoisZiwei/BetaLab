CREATE TABLE compute_tasks (
    id uuid PRIMARY KEY,
    owner_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_video_id uuid NOT NULL,
    kind text NOT NULL CHECK (kind IN ('analyze','generate')),
    request jsonb NOT NULL,
    request_hash text NOT NULL,
    idempotency_key text NOT NULL,
    state text NOT NULL DEFAULT 'queued' CHECK (state IN ('queued','running','succeeded','failed')),
    stage text NOT NULL DEFAULT 'queued',
    is_mock boolean NOT NULL DEFAULT true,
    attempt integer NOT NULL DEFAULT 1 CHECK (attempt > 0),
    retry_of uuid REFERENCES compute_tasks(id) ON DELETE SET NULL,
    error jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (owner_id, idempotency_key),
    CHECK ((state = 'failed') = (error IS NOT NULL))
);
-- Keep task history on source deletion, but always join the live source for access.
CREATE INDEX compute_tasks_queue ON compute_tasks(created_at,id) WHERE state='queued';
CREATE INDEX compute_tasks_owner ON compute_tasks(owner_id,created_at DESC,id DESC);
CREATE TABLE compute_results (
    task_id uuid PRIMARY KEY REFERENCES compute_tasks(id) ON DELETE CASCADE,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE compute_notifications (
    id uuid PRIMARY KEY,
    task_id uuid NOT NULL REFERENCES compute_tasks(id) ON DELETE CASCADE,
    owner_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event text NOT NULL CHECK (event IN ('task_succeeded','task_failed')),
    is_mock boolean NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    read_at timestamptz,
    UNIQUE(task_id,event)
);
CREATE INDEX compute_notifications_owner ON compute_notifications(owner_id,created_at DESC,id DESC);
