import { useEffect, useState } from 'react'
import { api } from '../api'

type Correction = { hold_id: string; cx_px: number; cy_px: number; note: string }
type Data = { version: string | null; review: { corrections: Correction[]; notes: string } | null;
  holds: Correction[]; summary: { width: number; height: number; reference_frame: number } }
export function HoldReview({ taskId, csrf, onSaved }: { taskId: string; csrf?: string; onSaved: (version: string | null) => void }) {
  const [data, setData] = useState<Data | null>(null)
  const [corrections, setCorrections] = useState<Correction[]>([])
  const [notes, setNotes] = useState('')
  const [selected, setSelected] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [reload, setReload] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    api<Data>(`/tasks/${taskId}/hold-review`, { signal: controller.signal }).then(value => {
      if (controller.signal.aborted) return
      setData(value); setCorrections(value.review?.corrections ?? []); setNotes(value.review?.notes ?? '')
      onSaved(value.version)
    }).catch(e => { if (!controller.signal.aborted) setError(e.message) })
    return () => controller.abort()
  }, [taskId, reload])
  async function save() {
    if (!data || busy) return
    setBusy(true); setError(''); setMessage('')
    try {
      const saved = await api<Data>(`/tasks/${taskId}/hold-review`, { method: 'POST', csrf,
        body: { base_version: data.version, reference_frame: data.summary.reference_frame, corrections, notes } })
      setData(saved); onSaved(saved.version)
      setMessage('Hold version saved. Recheck contacts and save calibration using this version. Old versions remain available.')
    } catch (e) { setError((e as Error).message) }
    finally { setBusy(false) }
  }
  return <details><summary>Correct or add holds</summary>
    <p>Select an existing hold to correct its center, or choose Add missed hold. Click its center on the reference image. This does not infer hold size or a segmentation mask.</p>
    {data && <>
      <label>Hold to correct<select value={selected} onChange={e => setSelected(e.target.value)}><option value="">Add missed hold</option>{[...new Set([...data.holds, ...corrections].map(h => h.hold_id))].map(id => <option key={id}>{id}</option>)}</select></label>
      <div style={{ position: 'relative' }}>
        <img onPointerDown={e => e.stopPropagation()} alt="Hold correction reference" style={{ width: '100%', display: 'block', cursor: 'crosshair' }} src={`/api/tasks/${taskId}/artifacts/reference`} onClick={e => {
          const box = e.currentTarget.getBoundingClientRect()
          const hold_id = selected || `manual-${crypto.randomUUID().slice(0,8)}`
          const point = { hold_id, cx_px: Math.min(data.summary.width - 1, Math.round((e.clientX-box.left)/box.width*data.summary.width)), cy_px: Math.min(data.summary.height - 1, Math.round((e.clientY-box.top)/box.height*data.summary.height)), note: '' }
          setCorrections(old => [...old.filter(h => h.hold_id !== hold_id), point]); setSelected(hold_id); setMessage('')
        }} />
        {corrections.map(h => <span key={h.hold_id} style={{ position:'absolute', left:`${h.cx_px/data.summary.width*100}%`, top:`${h.cy_px/data.summary.height*100}%`, color:'#fff', background:'#174d7d', pointerEvents:'none', fontSize:11 }}>{h.hold_id}</span>)}
      </div>
      {corrections.map(h => <div key={h.hold_id}><strong>{h.hold_id}</strong> ({h.cx_px}, {h.cy_px})
        <label>Correction evidence<input value={h.note} onChange={e => setCorrections(old => old.map(x => x.hold_id === h.hold_id ? {...x,note:e.target.value} : x))} /></label>
        <button type="button" onClick={() => {setCorrections(old => old.filter(x => x.hold_id !== h.hold_id));setSelected('')}}>Remove correction {h.hold_id}</button>
      </div>)}
      <label>Hold review notes<textarea value={notes} onChange={e => setNotes(e.target.value)} /></label>
      <button type="button" disabled={busy || !csrf || !notes.trim() || corrections.some(h => !h.note.trim())} onClick={() => void save()}>Save hold corrections</button>
      <button type="button" disabled={busy} onClick={() => { if (window.confirm('Discard unsaved hold edits and reload?')) setReload(n => n+1) }}>Reload hold corrections</button>
    </>}
    {error && <p role="alert">{error}</p>}<p role="status">{message}</p>
  </details>
}
