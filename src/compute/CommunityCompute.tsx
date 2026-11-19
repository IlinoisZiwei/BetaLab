import { useEffect, useRef, useState, type ReactNode } from 'react'
import { api, type Session } from '../api'
import { ResultInsights } from './ResultInsights'
import type { Body, Task, Note } from './results'
export type { Task } from './results'
import './community.css'

type Source = { source_analysis_id: string; source_analysis_version: string; is_mock: boolean;
  original_body?: Body; baseline_status: string; quality: { warnings: string[] } }
export type ComputeVideo = { id: string; title: string; display_name?: string; username?: string;
  is_preset_sample?: boolean; is_preset_beta?: boolean }
type Props = { session: Session; source: ComputeVideo | null; closeSource: () => void; library: boolean; openLibrary: () => void; renderLibrary?: (content: ReactNode) => ReactNode }
const stateLabel: Record<string, string> = { queued: 'Queued', running: 'Generating', succeeded: 'Completed', failed: 'Failed' }
const dimensions = (body?: Body) => body ? `${body.height_cm} cm height · ${body.arm_span_cm} cm arm span (${body.provenance === 'estimated' ? 'estimated' : 'provided'})` : 'Measurements unavailable'

// Mounted once per signed-in user. Tasks live on the server, independently of pages.
export function CommunityCompute({ session, source, closeSource, library, openLibrary, renderLibrary = content => content }: Props) {
  const [tasks, setTasks] = useState<Task[]>([])
  const [notes, setNotes] = useState<Note[]>([])
  const [unread, setUnread] = useState(0)
  const [taskCursor, setTaskCursor] = useState<string | null>(null)
  const [noteCursor, setNoteCursor] = useState<string | null>(null)
  const [selected, setSelected] = useState<Task | null>(null)
  const [showTasks, setShowTasks] = useState(false)
  const [showNotes, setShowNotes] = useState(false)
  const [reference, setReference] = useState<Source | null>(null)
  const [sourceError, setSourceError] = useState('')
  const [error, setError] = useState('')
  const [height, setHeight] = useState('')
  const [span, setSpan] = useState('')
  const [busy, setBusy] = useState(false)
  const alive = useRef(true)
  const actionLock = useRef(false)
  const submission = useRef({ fingerprint: '', key: '' })
  const selectedId = useRef<string | null>(null)
  const loadedPages = useRef({ tasks: 1, notifications: 1 })
  selectedId.current = selected?.id ?? null

  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  useEffect(() => {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    async function poll() {
      try {
        async function pages<T>(kind: 'tasks' | 'notifications') {
          const items: T[] = []; let cursor: string | null = null; let unread_count = 0
          for (let i = 0; i < loadedPages.current[kind]; i++) {
            const page: { items: T[]; next_cursor: string | null; unread_count?: number } = await api('/' + kind + '?limit=20' + (cursor ? '&cursor=' + cursor : ''), { signal: controller.signal })
            items.push(...page.items); cursor = page.next_cursor; unread_count = page.unread_count ?? 0
            if (!cursor) break
          }
          return { items, next_cursor: cursor, unread_count }
        }
        const [jobs, notifications] = await Promise.all([pages<Task>('tasks'), pages<Note>('notifications')])
        if (controller.signal.aborted) return
        setTasks(jobs.items); setTaskCursor(jobs.next_cursor)
        setNotes(notifications.items); setNoteCursor(notifications.next_cursor); setUnread(notifications.unread_count)
        if (selectedId.current) {
          const id = selectedId.current
          try {
            const task = await api<Task>('/tasks/' + id, { signal: controller.signal })
            if (!controller.signal.aborted && selectedId.current === id) setSelected(task)
          } catch (e) {
            if (!controller.signal.aborted && selectedId.current === id) { setSelected(null); setError((e as Error).message) }
          }
        }
      } catch (e) { if (!controller.signal.aborted) setError((e as Error).message) }
      if (!controller.signal.aborted) timer = setTimeout(poll, document.hidden ? 15000 : 5000)
    }
    void poll()
    return () => { controller.abort(); clearTimeout(timer) }
  }, [session.user.id])

  useEffect(() => {
    setReference(null); setSourceError('')
    setHeight(session.user.height_cm?.toString() ?? ''); setSpan(session.user.arm_span_cm?.toString() ?? '')
    if (!source) return
    if (source.is_preset_sample || source.is_preset_beta) {
      setSourceError('This is a browsing sample. It has no linked source analysis for personal generation.'); return
    }
    const controller = new AbortController()
    api<Source>('/tasks/source-analysis/' + source.id, { signal: controller.signal }).then(value => {
      if (!controller.signal.aborted) setReference(value)
    }).catch(e => { if (!controller.signal.aborted) setSourceError((e as Error).message + '. The uploader needs a supported source analysis before you can generate.') })
    return () => controller.abort()
  }, [source?.id, session.user.id])

  async function action(work: () => Promise<void>) {
    if (actionLock.current) return
    actionLock.current = true; setBusy(true); setError('')
    try { await work() } catch (e) { if (alive.current) setError((e as Error).message) }
    finally { actionLock.current = false; if (alive.current) setBusy(false) }
  }
  async function submit(path: string, body: unknown) {
    const fingerprint = JSON.stringify({ path, body })
    if (submission.current.fingerprint !== fingerprint) submission.current = { fingerprint, key: crypto.randomUUID() }
    // Keep the key after a lost response, so retrying does not queue duplicate work.
    return api<Task>(path, { method: 'POST', body, csrf: session.csrf_token, headers: { 'Idempotency-Key': submission.current.key } })
  }
  async function generate() {
    if (!source || !reference) return
    const task = await submit('/tasks/generate', { kind: 'generate', video_id: source.id,
      source_analysis_id: reference.source_analysis_id, source_analysis_version: reference.source_analysis_version,
      target_body: { height_cm: Number(height), arm_span_cm: Number(span), provenance: 'user_input' }, compare_techniques: false })
    if (!alive.current) return
    setTasks(old => [task, ...old.filter(t => t.id !== task.id)]); setSelected(task); setShowTasks(true); closeSource(); openLibrary()
  }
  async function openTask(id: string) {
    setSelected(null)
    const task = await api<Task>('/tasks/' + id)
    if (alive.current) { setSelected(task); setShowTasks(true); openLibrary() }
  }
  async function more(kind: 'tasks' | 'notifications') {
    const cursor = kind === 'tasks' ? taskCursor : noteCursor
    if (!cursor) return
    if (kind === 'tasks') {
      const page = await api<{ items: Task[]; next_cursor: string | null }>('/tasks?limit=20&cursor=' + cursor)
      if (alive.current) { loadedPages.current.tasks++; setTasks(old => [...old, ...page.items.filter(t => !old.some(o => o.id === t.id))]); setTaskCursor(page.next_cursor) }
    } else {
      const page = await api<{ items: Note[]; next_cursor: string | null }>('/notifications?limit=20&cursor=' + cursor)
      if (alive.current) { loadedPages.current.notifications++; setNotes(old => [...old, ...page.items.filter(n => !old.some(o => o.id === n.id))]); setNoteCursor(page.next_cursor) }
    }
  }
  const result = selected?.result
  const validBody = Number(height) >= 100 && Number(height) <= 230 && Number(span) >= 80 && Number(span) <= 260
  return <>
    {library && renderLibrary(<>
    <nav className="compute-nav" aria-label="Library tools">
      <button aria-expanded={showTasks} aria-controls="library-skeletons" onClick={() => setShowTasks(true)}>My skeletons</button>
      <button onClick={() => setShowNotes(true)}>Notifications{unread > 0 ? ` (${unread})` : ''}</button>
    </nav>
    {error && <p className="compute-error" role="alert">{error} <button onClick={() => setError('')}>Dismiss</button></p>}
    {showTasks && <section id="library-skeletons" className="compute-library" aria-label="My skeletons">
      <h2>My skeletons</h2><p>Personal results and background tasks. You can leave this page while generation runs.</p>
      {!tasks.length && <p>No tasks yet. Open a Community video to generate your own skeleton.</p>}
      {tasks.map(task => <button className="compute-row" key={task.id} onClick={() => void action(() => openTask(task.id))}>
        {task.kind === 'generate' ? 'Personal skeleton' : 'Source analysis'} · {task.state === 'running' && task.kind === 'analyze' ? 'Analyzing' : stateLabel[task.state]}{task.is_mock && ' · Mock'}<small>{new Date(task.created_at).toLocaleString()}</small>
      </button>)}
      {taskCursor && <button disabled={busy} onClick={() => void action(() => more('tasks'))}>Older tasks</button>}
      {selected && <article className="compute-result" aria-label="Selected skeleton task">
        <h3>{selected.kind === 'generate' ? 'Your skeleton' : 'Source analysis'}</h3>
        <p data-testid="main-task-state">{selected.state === 'running' && selected.kind === 'analyze' ? 'Analyzing' : stateLabel[selected.state]}{selected.is_mock && ' · Mock task'}</p>
        {['queued', 'running'].includes(selected.state) && <p>You can keep browsing. We will notify you when the task finishes.</p>}
        {selected.error && <p role="alert">{selected.error.message}</p>}
        {selected.state === 'failed' && selected.error?.retryable && <button disabled={busy} onClick={() => void action(async () => {
          const task = await submit('/tasks/' + selected.id + '/retry', {}); if (alive.current) { setSelected(task); setTasks(old => [task, ...old]) }
        })}>{selected.kind === 'analyze' ? 'Retry analysis' : 'Retry generation'}</button>}
        {result && <>
          <p>Original climber: {dimensions(result.original_body)}</p><p>Your proportions: {dimensions(result.target_body)}</p>
          <ResultInsights csrf={session.csrf_token} key={selected.id} task={selected} />
        </>}
      </article>}
    </section>}
    </>)}
    {source && <div className="modal-backdrop"><section className="modal compute-modal" role="dialog" aria-modal="true" aria-label="Generate personal skeleton">
      <h2>Generate your skeleton</h2>{error && <p role="alert">{error}</p>}<p>{source.title} · {source.display_name || source.username || 'Original climber'}</p>
      {sourceError ? <p role="status">{sourceError}</p> : !reference ? <p>Checking source analysis…</p> : <>
        <p>Original climber: {dimensions(reference.original_body)}</p>
        <p className="compute-warning">{reference.is_mock ? 'Mock analysis' : 'Diagnostic source'} · Baseline: {reference.baseline_status}. Your result will remain a diagnostic preview. Technique comparison is not enabled.</p>
        <label>Height (cm)<input type="number" min="100" max="230" value={height} onChange={e => setHeight(e.target.value)} /></label>
        <label>Arm span (cm)<input type="number" min="80" max="260" value={span} onChange={e => setSpan(e.target.value)} /></label>
        <p>Saved privately to My Library. Access also depends on the original video's visibility.</p>
        <button className="btn btn-solid" disabled={busy || !validBody} onClick={() => void action(generate)}>{busy ? 'Submitting…' : 'Generate my skeleton'}</button>
      </>}
      <button className="btn btn-outline" disabled={busy} onClick={closeSource}>Close</button>
    </section></div>}
    {showNotes && <div className="modal-backdrop"><section className="modal compute-modal" role="dialog" aria-modal="true" aria-label="Task notifications"><h2>Notifications</h2>
      {!notes.length && <p>No notifications yet.</p>}
      {notes.map(note => <button className="compute-row" disabled={busy} key={note.id} onClick={() => void action(async () => {
        await api('/notifications/' + note.id + '/read', { method: 'PATCH', csrf: session.csrf_token })
        if (!alive.current) return
        setNotes(old => old.map(n => n.id === note.id ? { ...n, read_at: new Date().toISOString() } : n)); setUnread(n => Math.max(0, n - (note.read_at ? 0 : 1))); setShowNotes(false)
        await openTask(note.task_id)
      })}>{note.read_at ? 'Read' : 'Unread'} · {note.event === 'task_succeeded' ? 'Task completed' : 'Task failed'}</button>)}
      {noteCursor && <button disabled={busy} onClick={() => void action(() => more('notifications'))}>Older notifications</button>}
      <button onClick={() => setShowNotes(false)}>Close</button>
    </section></div>}
  </>
}
