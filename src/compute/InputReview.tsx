import { HoldReview } from './HoldReview'
import { CalibrationGuide } from './CalibrationGuide'
import { useEffect, useState } from 'react'
import { api } from '../api'
import { ContactReview } from './ContactReview'
import { WorldReview } from './WorldReview'

type Summary = { reference_frame: number; width: number; height: number; frame_count: number; hold_count: number; contact_rows: number; seconds: number }
type Review = { version: string | null; review: Record<string, unknown> | null; calibrated: { holds: { status: string }[]; generation_ready: boolean } | null }

// This is a review of newly extracted inputs, not the Trial2 diagnostics viewer.
export function InputReview({ taskId, csrf }: { taskId: string; csrf?: string }) {
  const [holdVersion, setHoldVersion] = useState<string | null>(null)
  const [summary, setSummary] = useState<Summary | null>(null)
  const [review, setReview] = useState<Review | null>(null)
  const [draft, setDraft] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [reload, setReload] = useState(0)
  const path = '/tasks/' + taskId
  useEffect(() => {
    const controller = new AbortController()
    setSummary(null); setReview(null); setError('')
    void Promise.all([api<Summary>(path + '/artifacts/input_summary', { signal: controller.signal }),
      api<Review>(path + '/input-review', { signal: controller.signal })]).then(([data, saved]) => {
      if (controller.signal.aborted) return
      setSummary(data); setReview(saved)
      setDraft(JSON.stringify(saved.review ?? { grid_spacing_cm: 14.3, reference_frame: data.reference_frame,
        selected_hold_ids: [], planes: [], identity_confirmed: false, contact_reviewed: false,
        notes: 'Record measured inputs and any uncertainty here.' }, null, 2))
    }).catch(e => { if (!controller.signal.aborted) setError(e.message) })
    return () => controller.abort()
  }, [path, reload])
  async function save() {
    if (busy || !review) return
    setBusy(true); setError(''); setMessage('')
    try {
      const body = { ...JSON.parse(draft), base_version: review.version, hold_review_version: holdVersion }
      const saved = await api<Review>(path + '/input-review', { method: 'POST', body, csrf })
      setReview(saved); setMessage('Calibration review saved. Coordinates are plane-local; generation remains blocked.')
    } catch (e) { setError((e as Error).message) }
    finally { setBusy(false) }
  }
  return <section aria-label="New video inputs">
    <h3>New video inputs · review required</h3>
    <p>Automatic hold, pose and contact candidates are ready for review. The video above is the sampled input recording, not a generated skeleton.</p>
    {summary && <>
      <p>{summary.frame_count} frames · {summary.hold_count} hold candidates · {summary.contact_rows} limb observations · {summary.seconds.toFixed(1)}s processing</p>
      <figure><img style={{ maxWidth: '100%', maxHeight: 600, objectFit: 'contain' }} src={'/api' + path + '/artifacts/hold_preview'} alt="Numbered automatic hold candidates; route selection is unconfirmed" />
        <figcaption>Automatic candidates include other routes. Choose only the holds for this climb.</figcaption></figure>
      <HoldReview taskId={taskId} csrf={csrf} onSaved={setHoldVersion} />
      <details><summary>Wall reference and calibration editor</summary>
        <p>Reference frame {summary.reference_frame}, {summary.width} × {summary.height} pixels. Click the reference to read pixel coordinates. Use this image, not the annotated preview, for calibration.</p>
        <img onPointerDown={e => e.stopPropagation()} style={{ width: '100%', height: 'auto', cursor: 'crosshair' }} src={'/api' + path + '/artifacts/reference'} alt="Wall calibration reference" onClick={e => {
          const box = e.currentTarget.getBoundingClientRect()
          setMessage(`Reference pixel: [${Math.min(summary.width - 1, Math.round((e.clientX - box.left) / box.width * summary.width))}, ${Math.min(summary.height - 1, Math.round((e.clientY - box.top) / box.height * summary.height))}]`)
        }} />
        <p>Enter selected_hold_ids from the candidate list. Each plane needs an id, convex polygon, four grid_corners ordered top-left → top-right → bottom-right → bottom-left on that wall, horizontal_steps and vertical_steps (hole intervals, not hole count), angle_from_horizontal_deg (null if unknown), and a measurement note. Adjacent hole centers are 14.3 cm apart. Never copy another video's wall measurements.</p>
        <pre style={{ whiteSpace: 'pre-wrap' }}>{'{"id":"panel-1","polygon":[[x,y],…],"grid_corners":[[x,y],[x,y],[x,y],[x,y]],"horizontal_steps":1,"vertical_steps":1,"angle_from_horizontal_deg":null,"note":"Describe measurement"}'}</pre>
        <p>Keep contact_reviewed false in calibration JSON. Contact corrections have their own versioned editor below; global 3D wall joins have their own editor below.</p>
        <CalibrationGuide draft={draft} onChange={setDraft} image={"/api" + path + "/artifacts/reference"} width={summary.width} height={summary.height} />
        <label>Calibration review JSON<textarea aria-label="Calibration review JSON" rows={18} style={{ width: '100%', fontFamily: 'monospace' }} value={draft} onChange={e => setDraft(e.target.value)} /></label>
        <button type="button" disabled={busy || !csrf || !review} onClick={() => void save()}>Save calibration review</button>
        <button type="button" disabled={busy} onClick={() => setReload(n => n + 1)}>Reload saved review</button>
      </details>
      <ContactReview key={taskId} taskId={taskId} csrf={csrf} holdVersion={holdVersion} />
      <WorldReview key={taskId + 'world'} taskId={taskId} csrf={csrf} />
      <p>Private input files: {['holds', 'pose', 'identity', 'alignment', 'frame_map', 'contacts', 'contact_events', 'input_summary', 'provenance'].map(name => <span key={name}><a href={'/api' + path + '/artifacts/' + name} target="_blank" rel="noreferrer">{name}</a>{' · '}</span>)}</p>
      {review?.calibrated && <p>Saved review: {review.calibrated.holds.filter(h => h.status === 'plane_local_only').length} / {review.calibrated.holds.length} selected holds have plane-local coordinates. Use the global alignment editor for world coordinates; source adaptation remains pending.</p>}
    </>}
    {error && <p role="alert">{error}</p>}<p role="status">{message}</p>
  </section>
}
