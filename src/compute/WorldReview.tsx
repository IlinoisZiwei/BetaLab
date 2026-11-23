import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import './contact-review.css'

type Camera = { fit_rmse_px: number; check_max_px: number; observations: {
  pixel: number[]; projected_px: number[]; role: string; error_px: number
}[] }
type Saved = {
  version: string | null; review: Record<string, unknown> | null
  summary: { panel_count: number; hold_count: number; camera_aligned_frames: number; frame_count: number;
    missing_camera_frames: number[]; generation_ready: false } | null
  cameras?: Record<string, Camera>; warnings?: string[]
}
type Summary = { width: number; height: number; reference_frame: number }

export function WorldReview({ taskId, csrf }: { taskId: string; csrf?: string }) {
  const path = '/tasks/' + taskId
  const [saved, setSaved] = useState<Saved | null>(null)
  const [summary, setSummary] = useState<Summary | null>(null)
  const [draft, setDraft] = useState('')
  const [dirty, setDirty] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [reload, setReload] = useState(0)
  const alive = useRef(true)
  const lock = useRef(false)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  useEffect(() => {
    const controller = new AbortController()
    setSaved(null); setError(''); setMessage('')
    void Promise.all([
      api<Saved>(path + '/world-review', { signal: controller.signal }),
      api<{ version: string | null }>(path + '/input-review', { signal: controller.signal }),
      api<{ version: string | null }>(path + '/contact-review', { signal: controller.signal }),
      api<Summary>(path + '/artifacts/input_summary', { signal: controller.signal }),
    ]).then(([value, calibration, contacts, info]) => {
      if (controller.signal.aborted) return
      setSaved(value); setSummary(info); setDirty(false)
      setDraft(JSON.stringify(value.review ?? {
        calibration_version: calibration.version, contact_version: contacts.version,
        root: { plane_id: '', origin_cm: [0, 0, 0], u_axis: null, v_axis: null },
        joins: [],
        intrinsics: { fx: null, fy: null, cx: null, cy: null, width: info.width, height: info.height,
          distortion: null, provenance: '' },
        cameras: [{ frame: info.reference_frame, observations: [] }],
        fixed_camera_confirmed: false, measurements_confirmed: false, notes: '',
      }, null, 2))
    }).catch(e => { if (!controller.signal.aborted) setError(e.message) })
    return () => controller.abort()
  }, [path, reload])
  async function save() {
    if (!saved || lock.current) return
    lock.current = true; setBusy(true); setError(''); setMessage('')
    try {
      const body = { ...JSON.parse(draft), base_version: saved.version }
      const next = await api<Saved>(path + '/world-review', { method: 'POST', body, csrf })
      if (!alive.current) return
      setSaved(next); setDraft(JSON.stringify(next.review, null, 2)); setDirty(false)
      setMessage('Global alignment version saved. Pose depth and source reconstruction remain unresolved.')
    } catch (e) { if (alive.current) setError((e as Error).message) }
    finally { lock.current = false; if (alive.current) setBusy(false) }
  }
  async function packageInputs() {
    if (!saved?.version || busy) return
    setBusy(true); setError('')
    try {
      const pack = await api<{version: string}>(path + '/reconstruction-inputs', {method:'POST',csrf,body:{world_version:saved.version}})
      setMessage(`Pinned input package: ${pack.version}. This is not a generated skeleton; reconstruction is still pending.`)
    } catch (e) { setError((e as Error).message) }
    finally { setBusy(false) }
  }
  const referenceCamera = summary && saved?.cameras?.[String(summary.reference_frame)]
  return <section className="contact-review" aria-label="Global wall alignment">
    {saved?.version && <button type="button" disabled={busy || !csrf || dirty} onClick={() => void packageInputs()}>Prepare versioned reconstruction inputs</button>}
    <h4>Global wall and camera alignment</h4>
    <p>14.3 cm hole spacing alone is insufficient. This step needs measured wall folds and camera
      intrinsics for the analysis image. Missing values stay unknown; no Trial2 angles are copied.</p>
    <p>Handheld video: keep fixed_camera_confirmed false. Supply controls for each aligned frame;
      missing camera frames remain unaligned. Two-dimensional pose becomes world rays with unknown
      depth, not a recovered 3D skeleton.</p>
    <details><summary>Geometry input guide</summary>
      <p>Save wall calibration with confirmed identity and a confirmed contact review first.
        Versions are pinned; reload here to use newly saved versions. Units are cm; world Y is up.
        Root u_axis/v_axis must be orthogonal unit vectors matching the panel grid directions.
        The root origin may be arbitrary and does not establish ground height.</p>
      <p>Each join: parent, child, parent_edge_cm and child_edge_cm (two matching ordered [u,v] endpoints),
        fold_deg (signed right-hand rotation around the parent edge). Every panel needs a measured
        angle in wall calibration. Edges must match within 0.1 cm.</p>
      <p>Intrinsics: fx/fy/cx/cy, exact analysis width/height, distortion [k1,k2,p1,p2,k3] and provenance.
        Each camera frame needs observations with plane_id, uv_cm, pixel [x,y], and role fit/check:
        at least six well-spread noncoplanar fit points and two distinct held-out check points.
        Check points must be independently observed. Fit RMSE ≤ 5 px and each check error ≤ 8 px.</p>
      <p>Set measurements_confirmed true only after verification. This editor validates geometry;
        it does not estimate unknown camera intrinsics or wall measurements.</p>
    </details>
    <button type="button" disabled={busy} onClick={() => {
      if (!dirty || window.confirm('Discard unsaved global geometry edits?')) setReload(n => n + 1)
    }}>Reload global alignment</button>
    {saved && <>
      <label>Global geometry JSON<textarea aria-label="Global geometry JSON" rows={18}
        style={{ fontFamily: 'monospace' }} disabled={busy} value={draft}
        onChange={e => { setDraft(e.target.value); setDirty(true) }} /></label>
      <button type="button" disabled={busy || !csrf} onClick={() => void save()}>
        {busy ? 'Validating geometry…' : 'Validate and save global alignment'}</button>
    </>}
    {error && <p role="alert">{error}</p>}<p role="status">{message}</p>
    {saved?.summary && <div style={{ overflowWrap: 'anywhere' }}>
      <p>Saved version: {saved.version}{dirty ? ' · Unsaved changes' : ''}</p>
      <p>{saved.summary.panel_count} joined panels · {saved.summary.hold_count} selected holds ·
        {' '}{saved.summary.camera_aligned_frames} / {saved.summary.frame_count} camera-aligned frames.</p>
      <p>Unknown-depth pose rays and reviewed contact anchors share the wall coordinate system.
        Generation remains blocked.</p>
      {Object.entries(saved.cameras ?? {}).map(([frame, camera]) => <p key={frame}>Camera frame {frame}:
        fit {camera.fit_rmse_px.toFixed(2)} px RMSE; check max {camera.check_max_px.toFixed(2)} px.</p>)}
      {referenceCamera && summary && <figure>
        <svg viewBox={`0 0 ${summary.width} ${summary.height}`} role="img"
          aria-label="Reference camera reprojection" style={{ width: '100%', background: '#eee' }}>
          <image href={'/api' + path + '/artifacts/reference'} width={summary.width} height={summary.height} />
          {referenceCamera.observations.map((o, i) => <g key={i}>
            <line x1={o.pixel[0]} y1={o.pixel[1]} x2={o.projected_px[0]} y2={o.projected_px[1]} stroke="red" strokeWidth={2} />
            <circle cx={o.pixel[0]} cy={o.pixel[1]} r={5} fill={o.role === 'check' ? 'orange' : 'cyan'} />
            <circle cx={o.projected_px[0]} cy={o.projected_px[1]} r={8} fill="none" stroke="red" strokeWidth={2} />
          </g>)}
        </svg><figcaption>Cyan: fit observations; orange: held-out checks; red rings: projections.
          This overlay shows the reference frame only.</figcaption>
      </figure>}
      {saved.warnings?.map(w => <p key={w}>{w}</p>)}
      <a href={'/api' + path + '/world-review/export?version=' + saved.version}
        target="_blank" rel="noreferrer">Export pinned world coordinates</a>
      {typeof saved.review?.base_version === 'string' && <> · <a
        href={'/api' + path + '/world-review?version=' + saved.review.base_version}
        target="_blank" rel="noreferrer">Previous global version</a></>}
    </div>}
  </section>
}
