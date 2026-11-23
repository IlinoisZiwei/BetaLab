import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import './contact-review.css'

const limbs = ['left_hand', 'right_hand', 'left_foot', 'right_foot'] as const
type Interval = {
  limb: typeof limbs[number]; state: 'hold' | 'free' | 'unknown'; hold_id: string | null
  start_frame: number; release_frame: number; note: string
}
type Saved = {
  version: string
  review: { base_version: string | null; hold_review_version?: string | null; intervals: Interval[]; confirmed: boolean; notes: string }
  normalized: { unknown_limb_frames: number }
}
type Data = {
  version: string | null; saved: Saved | null; candidates: Interval[]
  summary: { frame_count: number; fps: number }; holds: { hold_id: string }[]
}

// Human corrections are separate from automatic artifacts and wall calibration.
export function ContactReview({ taskId, csrf, holdVersion = null }: { taskId: string; csrf?: string; holdVersion?: string | null }) {
  const path = '/tasks/' + taskId + '/contact-review'
  const loadedHoldVersion = useRef<string | null>(null)
  const [data, setData] = useState<Data | null>(null)
  const [intervals, setIntervals] = useState<Interval[]>([])
  const [notes, setNotes] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [reload, setReload] = useState(0)
  const video = useRef<HTMLVideoElement>(null)
  const alive = useRef(true)
  const lock = useRef(false)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  useEffect(() => {
    if (dirty) { setError('Hold inputs changed. Save or reload contact edits before switching hold versions.'); return }
    const controller = new AbortController()
    setData(null); setError(''); setMessage('')
    api<Data>(path + (holdVersion ? '?hold_version=' + holdVersion : ''), { signal: controller.signal }).then(value => {
      if (controller.signal.aborted) return
      loadedHoldVersion.current = holdVersion
      setData(value); setIntervals(value.saved?.review.intervals ?? [])
      setNotes(value.saved?.review.notes ?? '')
      setConfirmed((value.saved?.review.hold_review_version ?? null) === holdVersion && (value.saved?.review.confirmed ?? false)); setDirty(false)
    }).catch(e => { if (!controller.signal.aborted) setError(e.message) })
    return () => controller.abort()
  }, [path, reload, holdVersion])
  function edit(next: Interval[]) {
    setIntervals(next); setConfirmed(false); setDirty(true); setMessage('')
  }
  function update(index: number, patch: Partial<Interval>) {
    edit(intervals.map((item, i) => i === index ? { ...item, ...patch } : item))
  }
  async function save() {
    if (!data || lock.current) return
    lock.current = true; setBusy(true); setError(''); setMessage('')
    try {
      const saved = await api<Saved>(path, { method: 'POST', csrf,
        body: { base_version: data.version, hold_review_version: loadedHoldVersion.current, intervals, confirmed, notes } })
      if (!alive.current) return
      setData({ ...data, version: saved.version, saved }); setDirty(false)
      setMessage('Contact review saved. Unknown intervals remain unknown; generation remains blocked.')
    } catch (e) { if (alive.current) setError((e as Error).message) }
    finally { lock.current = false; if (alive.current) setBusy(false) }
  }
  return <section className="contact-review" aria-label="Contact review">
    <h4>Contact and release review</h4>
    <p>Edit the sampled analysis timeline. Start frame is included; release frame is excluded.
      Unmarked intervals remain unknown. Mark “free” only when the limb is visibly not contacting the wall.
      Unresolved wall or ground contacts should stay unknown.</p>
    {error && <p role="alert">{error}</p>}
    <button type="button" disabled={busy} onClick={() => {
      if (!dirty || window.confirm('Discard unsaved contact edits and reload?')) { setDirty(false); setReload(n => n + 1) }
    }}>Reload contact review</button>
    {data && <>
      <video ref={video} controls preload="metadata" aria-label="Contact reference video"
        style={{ width: '100%', maxHeight: 400 }} src={'/api/tasks/' + taskId + '/artifacts/video'} />
      <p>{data.summary.frame_count} analysis frames · {data.summary.fps} fps.
        Release frame {data.summary.frame_count} means the end of the clip.
        Seconds = frame / fps; these are not original source frame numbers.</p>
      <fieldset disabled={busy} style={{ minWidth: 0 }}>
        <legend>Manual contact intervals</legend>
        <button type="button" onClick={() => {
          if (!intervals.length || window.confirm('Replace these intervals with unreviewed automatic candidates?'))
            edit(data.candidates.map(item => ({ ...item })))
        }}>Load automatic contact candidates</button>
        <button type="button" onClick={() => edit([...intervals, {
          limb: 'left_hand', state: 'unknown', hold_id: null, start_frame: 0,
          release_frame: data.summary.frame_count, note: '',
        }])}>Add contact interval</button>
        {intervals.map((item, index) => <fieldset key={index} style={{ minWidth: 0, marginBlock: 10 }}>
          <legend>Interval {index + 1}</legend>
          <label>Limb<select aria-label={`Limb ${index + 1}`} value={item.limb}
            onChange={e => update(index, { limb: e.target.value as Interval['limb'] })}>
            {limbs.map(limb => <option key={limb}>{limb}</option>)}</select></label>
          <label>State<select aria-label={`State ${index + 1}`} value={item.state} onChange={e => {
            const state = e.target.value as Interval['state']
            update(index, { state, hold_id: state === 'hold' ? data.holds[0]?.hold_id ?? null : null })
          }}>{['hold', 'free', 'unknown'].map(state => <option key={state}>{state}</option>)}</select></label>
          {item.state === 'hold' && <label>Hold<select aria-label={`Hold ${index + 1}`} value={item.hold_id ?? ''}
            onChange={e => update(index, { hold_id: e.target.value })}>
            {data.holds.map(hold => <option key={hold.hold_id}>{hold.hold_id}</option>)}</select></label>}
          <label>Contact start frame<input aria-label={`Start frame ${index + 1}`} type="number" min={0}
            max={data.summary.frame_count - 1} step={1} value={item.start_frame}
            onChange={e => update(index, { start_frame: e.target.valueAsNumber })} /></label>
          <label>Release frame<input aria-label={`Release frame ${index + 1}`} type="number" min={1}
            max={data.summary.frame_count} step={1} value={item.release_frame}
            onChange={e => update(index, { release_frame: e.target.valueAsNumber })} /></label>
          <p>{(item.start_frame / data.summary.fps).toFixed(3)}–{(item.release_frame / data.summary.fps).toFixed(3)} s</p>
          <button type="button" onClick={() => {
            if (video.current) video.current.currentTime = item.start_frame / data.summary.fps
          }}>View contact {index + 1}</button>
          <button type="button" onClick={() => {
            if (video.current) video.current.currentTime = Math.min(item.release_frame, data.summary.frame_count - 1) / data.summary.fps
          }}>View release {index + 1}</button>
          <label>Observation<input aria-label={`Observation ${index + 1}`} value={item.note}
            onChange={e => update(index, { note: e.target.value })} /></label>
          <button type="button" onClick={() => edit(intervals.filter((_, i) => i !== index))}>Remove interval {index + 1}</button>
        </fieldset>)}
        <label>Review notes<textarea aria-label="Contact review notes" value={notes}
          onChange={e => { setNotes(e.target.value); setConfirmed(false); setDirty(true) }} /></label>
        <label className="contact-confirmation"><input type="checkbox" checked={confirmed} onChange={e => { setConfirmed(e.target.checked); setDirty(true) }} />
          I reviewed these intervals; unmarked or uncertain frames remain unknown.</label>
        <button type="button" disabled={!csrf || !notes.trim()} onClick={() => void save()}>Save contact review</button>
      </fieldset>
      {data.saved && <div style={{ overflowWrap: 'anywhere' }}>
        <p>Saved version: {data.saved.version}{dirty ? ' · Unsaved changes' : ''}</p>
        <p>{data.saved.normalized.unknown_limb_frames} unknown limb-frames in the saved version.</p>
        <a href={'/api' + path + '?version=' + data.saved.version} target="_blank" rel="noreferrer">Open saved contact version</a>
        {data.saved.review.base_version && <> · <a href={'/api' + path + '?version=' + data.saved.review.base_version}
          target="_blank" rel="noreferrer">Previous contact version</a></>}
        {data.saved.review.confirmed && <> · <a href={'/api' + path + '/export?version=' + data.saved.version}
          target="_blank" rel="noreferrer">Export saved contacts for computation</a></>}
      </div>}
    </>}
    <p role="status">{message}</p>
  </section>
}
