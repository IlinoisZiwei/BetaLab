import { useEffect, useState } from 'react'
import type { Task } from './results'

const stages: Record<string, string> = {
  preparing_input_video: 'Sampling the recording', detecting_body_pose: 'Tracking body pose',
  detecting_wall_holds: 'Detecting wall holds', predicting_contacts: 'Predicting contact candidates',
  verifying_input_artifacts: 'Verifying input files', rendering_preview: 'Rendering the preview',
  queued: 'Waiting for the worker', checking_source: 'Checking source access and inputs',
  starting_algorithm: 'Starting the analysis environment', source_skeleton: 'Fitting movement across frames',
  target_skeleton: 'Adapting movement to your measurements', preparing_inputs: 'Preparing video inputs',
  extracting_inputs: 'Finding holds, body pose and contact candidates', rendering: 'Rendering the preview',
  validating: 'Checking output quality', publishing: 'Saving results', complete: 'Finished',
}
export function elapsedLabel(created: string, end: string | number) {
  const seconds = Math.floor((new Date(end).getTime() - new Date(created).getTime()) / 1000)
  if (!Number.isFinite(seconds) || seconds < 0) return 'Unavailable'
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
}
export function TaskProgress({ task }: { task: Task }) {
  const [now, setNow] = useState(Date.now())
  const active = task.state === 'queued' || task.state === 'running'
  useEffect(() => {
    if (!active) return
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [active, task.id])
  return <div className="task-progress" aria-label="Task progress">
    {active && <p>{stages[task.stage] ?? 'Processing video'}. You can keep browsing.</p>}
    <p>{active ? 'Elapsed' : 'Total time'}: {elapsedLabel(task.created_at, active ? now : task.finished_at ?? task.updated_at ?? task.created_at)} · includes queue time</p>
    {task.started_at && <p>Queue: {elapsedLabel(task.created_at, task.started_at)} · Processing: {elapsedLabel(task.started_at, task.finished_at ?? (active ? now : task.updated_at ?? task.started_at))}</p>}
    {!task.started_at && !active && <p>Separate queue and processing timings were not recorded for this task.</p>}
    {task.updated_at && <p>Last server update: {new Date(task.updated_at).toLocaleTimeString()}</p>}
    {task.state === 'failed' && <p>{task.error?.retryable
      ? 'Your upload is saved. Retry this task after the connection or worker is available.'
      : 'Your upload is saved. Check the source video, input versions and calibration before submitting again.'}</p>}
  </div>
}
