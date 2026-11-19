"""Single PostgreSQL-backed worker for real jobs and explicit test mocks.

The session advisory lock is held for the entire worker lifetime, not only
claiming a row. A second process cannot run another compute job concurrently.
"""
import argparse
import signal
import time
from fastapi import HTTPException
from backend.database import connect, database
from . import service
from .mock import MockExecutor
from . import runner

LOCK_ID = 73114002

class Worker:
    def __init__(self, outcome='success', delay=0):
        self.outcome, self.delay = outcome, delay
        self.lock = None
        self.stopping = False

    def __enter__(self):
        self.lock = connect(autocommit=True)
        if not self.lock.execute('SELECT pg_try_advisory_lock(%s) AS acquired', (LOCK_ID,)).fetchone()['acquired']:
            self.lock.close()
            raise RuntimeError('Another compute worker already holds the singleton lock')
        # Only the sole worker can recover abandoned running jobs.
        with database() as db:
            for task in db.execute("SELECT * FROM compute_tasks WHERE state='running' FOR UPDATE").fetchall():
                runner.discard(task['id'])
                service.finish(db, task, error=dict(code='INTERRUPTED', message='Worker stopped before completion; retry is available.', retryable=True))
        return self

    def __exit__(self, *args):
        self.lock.close()

    def run_one(self):
        self.lock.execute('SELECT 1')  # Fail closed if our lock connection was lost.
        with database() as db:
            task = db.execute("SELECT * FROM compute_tasks WHERE state='queued' ORDER BY created_at,id FOR UPDATE SKIP LOCKED LIMIT 1").fetchone()
            if not task:
                return False
            db.execute("UPDATE compute_tasks SET state='running',stage='checking_source',updated_at=now() WHERE id=%s", (task['id'],))
        result = error = None
        try:
            with database() as db:
                service.check_request(db, task['request'], task['owner_id'])
            if not task['is_mock']:
                result = runner.execute(task,self)
            else:
                executor = MockExecutor()
                mock_task = executor.submit(task['request'], str(task['owner_id']))
                executor.advance(mock_task.id, self.outcome)
                with database() as db:
                    db.execute("UPDATE compute_tasks SET stage=%s,updated_at=now() WHERE id=%s AND state='running'",
                               ('mock_analysis' if task['kind']=='analyze' else 'mock_baseline',task['id']))
                deadline = time.monotonic() + self.delay
                while time.monotonic() < deadline and not self.stopping:
                    time.sleep(min(.1, max(0,deadline-time.monotonic())))
                if self.stopping:
                    error = dict(code='INTERRUPTED',message='Worker stopped; retry is available.',retryable=True)
                else:
                    final = executor.advance(mock_task.id, self.outcome)
                    if final.error:
                        error = final.error.model_dump()
                    else:
                        result = final.result.model_dump(mode='json')
                        if task['kind'] == 'analyze':
                            result['source_analysis_version'] = 'mock-v1-' + str(task['id'])
                        else:
                            with database() as db:
                                original = db.execute('SELECT payload FROM compute_results WHERE task_id=%s',
                                    (task['request']['source_analysis_id'],)).fetchone()['payload']
                            result.update(calibration_version=original['calibration_version'],
                                          original_body=original['original_body'],
                                          frame_count=original['frame_count'],fps=original['fps'])
        except runner.Interrupted:
            error = dict(code='INTERRUPTED',message='Worker stopped; retry is available.',retryable=True)
        except HTTPException as exc:
            error = dict(code='SOURCE_UNAVAILABLE' if exc.status_code==404 else 'STALE_ANALYSIS',
                         message='Source unavailable or analysis no longer usable.',retryable=False)
        except Exception:
            error = dict(code='WORKER_FAILED',message='Worker failed; inspect local worker logs.',retryable=True)
            import logging
            logging.exception('Compute task %s failed',task['id'])
        self.lock.execute('SELECT 1')
        with database() as db:
            # A video privacy change/deletion waits for this source row lock.
            try:
                service.check_request(db, task['request'], task['owner_id'])
            except HTTPException:
                result = None
                error = dict(code='SOURCE_UNAVAILABLE',message='Source unavailable or analysis no longer usable.',retryable=False)
            service.finish(db, task, result=None if error else result, error=error)
        if error:
            runner.discard(task['id'])
        return True

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true', help='Process at most one queued task')
    parser.add_argument('--outcome', choices=['success','failure','insufficient'], default='success', help='Mock-only test scenario')
    parser.add_argument('--delay', type=float, default=0, help='Mock-only delay in seconds for interruption tests')
    args = parser.parse_args()
    if args.delay < 0:
        parser.error('--delay must be nonnegative')
    with Worker(args.outcome,args.delay) as worker:
        def stop(*_):
            worker.stopping = True
        signal.signal(signal.SIGTERM,stop)
        signal.signal(signal.SIGINT,stop)
        print('Compute worker ready (mode is pinned per task)', flush=True)
        while not worker.stopping:
            worked = worker.run_one()
            if args.once:
                break
            if not worked:
                time.sleep(.5)

if __name__ == '__main__':
    main()
