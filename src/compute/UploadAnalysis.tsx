import { TaskProgress } from './TaskProgress'
import { useEffect, useRef, useState } from 'react'
import { api, type Session, type UserVideo } from '../api'
import type { Task } from './results'

type Status = { task: Task | null; can_start: boolean; reason: string | null }
type Props = { video: UserVideo; session: Session; submissionPending: boolean; onStatus: (label: string) => void; onTask: (task: Task | null) => void }
const labels: Record<string, string> = { queued: 'Analysis queued', running: 'Analyzing', succeeded: 'Ready', failed: 'Analysis failed' }

// Upload and analysis are separate operations: an analysis error never removes
// the saved video or asks the user to upload it again.
export function UploadAnalysis({ video, session, submissionPending, onStatus, onTask }: Props) {
  const [status, setStatus] = useState<Status | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [refresh, setRefresh] = useState(0)
  const callback = useRef(onStatus); callback.current = onStatus
  const taskCallback = useRef(onTask); taskCallback.current = onTask
  const alive = useRef(true)
  const lock = useRef(false)
  const path = '/tasks/upload-analysis/' + video.id
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  useEffect(() => {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    async function load() {
      try {
        const state = await api<Status>(path, { signal: controller.signal })
        if (controller.signal.aborted) return
        setStatus(state); setError(''); taskCallback.current(state.task)
        callback.current(state.task ? (state.task.result?.algorithm_version === 'video-inputs-v1' ? 'Review inputs' : labels[state.task.state]) : state.can_start ? 'Video saved' : 'Analysis unavailable')
        if (state.task && ['queued', 'running'].includes(state.task.state)) timer = setTimeout(load, document.hidden ? 15000 : 3000)
      } catch (e) {
        if (!controller.signal.aborted) { setError((e as Error).message); taskCallback.current(null); callback.current('Video saved') }
      }
    }
    void load()
    return () => { controller.abort(); clearTimeout(timer) }
  }, [path, session.csrf_token, submissionPending, refresh])

  async function startOrRetry() {
    if (lock.current) return
    lock.current = true; setBusy(true); setError('')
    try {
      const task = status?.task
      if (task?.state === 'failed' && task.error?.retryable) {
        await api('/tasks/' + task.id + '/retry', { method: 'POST', body: {}, csrf: session.csrf_token,
          headers: { 'Idempotency-Key': 'upload-retry:' + task.id } })
      } else await api(path, { method: 'POST', csrf: session.csrf_token })
      if (alive.current) setRefresh(n => n + 1)
    } catch (e) { if (alive.current) setError((e as Error).message) }
    finally { lock.current = false; if (alive.current) setBusy(false) }
  }
  const task = status?.task
  return <section className="process-status" aria-label="Upload analysis status">
    <strong>Video saved</strong>
    {!status && !error && <p>Checking analysis availability…</p>}
    {error && <p role="alert">Analysis request failed: {error} Your video is still saved.</p>}
    {task ? <>
      <p>{task.state === 'succeeded' ? (task.result?.algorithm_version === 'video-inputs-v1' ? 'Input preparation complete — review required' : 'Analysis completed') : labels[task.state]}{task.is_mock && ' · Mock task'}</p>
      {['queued', 'running'].includes(task.state) && <p>You can leave this page. Find the task in My Library; a notification will arrive when it finishes.</p>}
      {task.state === 'succeeded' && <p>Baseline: {task.result?.baseline_status}. Analysis completion does not certify a feasible climbing movement. Open My skeletons for the video and diagnostics.</p>}
      <TaskProgress task={task} />
      {task.error && <p role="alert">{task.error.message}</p>}
      {task.state === 'failed' && !task.error?.retryable && <p>This failure cannot be retried automatically. The source inputs or analysis version need correction.</p>}
      {task.state === 'failed' && task.error?.retryable && <button className="btn btn-outline" disabled={busy || submissionPending} onClick={() => void startOrRetry()}>Retry analysis</button>}
    </> : status?.can_start ? <>
      <p>{busy || submissionPending ? 'Submitting source analysis…' : 'Source analysis has not been queued.'}</p>
      <button className="btn btn-outline" disabled={busy || submissionPending} onClick={() => void startOrRetry()}>{error ? 'Retry analysis submission' : 'Start analysis'}</button>
    </> : status && <p role="status">Analysis unavailable: {status.reason} You can still play and manage your saved video.</p>}
    {error && <button className="btn btn-outline" disabled={busy || submissionPending} onClick={() => setRefresh(n => n + 1)}>Check analysis status</button>}
  </section>
}
