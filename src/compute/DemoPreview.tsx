import { useEffect, useState } from 'react'
import { api } from '../api'

export type PreparedDemo = {
  video_id: string; title: string; video_url: string; target_height_cm: number;
  target_arm_span_cm: number | null; limitations: string[]; frame_count: number; fps: number;
}

export function DemoPlayer({ demo }: { demo: PreparedDemo }) {
  return <article className="result-insights" aria-label="Prepared skeleton demonstration">
    <h3>{demo.title}</h3>
    <p className="compute-warning">Pre-generated demonstration · not generated for your measurements.</p>
    <p>Model height: {demo.target_height_cm} cm · Arm span: {demo.target_arm_span_cm == null ? 'not independently specified; template proportions' : `${demo.target_arm_span_cm} cm`}</p>
    <video controls preload="metadata" aria-label="Prepared skeleton video" src={demo.video_url} />
    <a href={`/api/videos/${demo.video_id}/content`} target="_blank" rel="noreferrer">Open original video</a>
    <details><summary>Demo scope and limitations</summary>{demo.limitations.map(text => <p key={text}>{text}</p>)}</details>
  </article>
}

export function SavedDemos({ refresh }: { refresh: number }) {
  const [items, setItems] = useState<PreparedDemo[]>([])
  const [selected, setSelected] = useState<PreparedDemo | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    api<{ items: PreparedDemo[] }>('/demo-previews/saved', { signal: controller.signal })
      .then(value => { setItems(value.items); setError(''); setSelected(old => value.items.find(x => x.video_id === old?.video_id) ?? null) })
      .catch(e => { if (!controller.signal.aborted) { setItems([]); setSelected(null); setError((e as Error).message) } })
    return () => controller.abort()
  }, [refresh])
  return <section aria-label="Saved demonstrations"><h3>Saved demonstrations</h3>
    {error && <p role="alert">{error}</p>}
    {!items.length && !error && <p>No saved demonstrations yet.</p>}
    {items.map(demo => <button className="compute-row" key={demo.video_id} onClick={() => setSelected(demo)}>{demo.title} · Pre-generated</button>)}
    {selected && <DemoPlayer demo={selected} />}
  </section>
}
