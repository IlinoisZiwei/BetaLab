import { useEffect, useRef, useState, type FormEvent } from 'react'
import type { UserVideo, VideoUpdate } from '../../api'

type Props = {video: UserVideo; save: (changes: VideoUpdate) => Promise<boolean | undefined>; close: () => void}
export function EditVideoForm({video, save, close}: Props) {
  const [title,setTitle] = useState(video.title)
  const [description,setDescription] = useState(video.description)
  const [visibility,setVisibility] = useState(video.visibility)
  const [beta,setBeta] = useState(video.share_as_beta)
  const [busy,setBusy] = useState(false)
  const [error,setError] = useState('')
  const alive = useRef(true)
  const lock = useRef(false)
  useEffect(() => {alive.current=true;return () => {alive.current=false}},[])
  async function submit(event: FormEvent) {
    event.preventDefault()
    if(lock.current) return
    if(!title.trim()) {setError('Please enter a video title.');return}
    lock.current=true;setBusy(true);setError('')
    try {
      const saved = await save({title:title.trim(),description:description.trim(),visibility,share_as_beta:visibility==='public' && beta})
      if(alive.current) {
        if(saved) close()
        else setError('The video could not be saved. Please try again.')
      }
    } catch(e) {if(alive.current) setError((e as Error).message)}
    finally {lock.current=false;if(alive.current) setBusy(false)}
  }
  return <form className="edit-video-form" aria-label="Edit video" onSubmit={e => void submit(e)}>
    <h2>Edit video</h2>
    <fieldset disabled={busy}>
      <label>Title<input type="text" required maxLength={120} value={title} onChange={e=>setTitle(e.target.value)} /></label>
      <label>Description (optional)<textarea rows={3} maxLength={500} value={description} onChange={e=>setDescription(e.target.value)} /></label>
      <fieldset className="edit-video-visibility"><legend>Visibility</legend><div className="privacy-options">{(['private','public'] as const).map(option=><label key={option}><input type="radio" name={`edit-visibility-${video.id}`} value={option} checked={visibility===option} onChange={()=>{setVisibility(option);if(option==='private')setBeta(false)}} />{option==='public'?'Public':'Private'}</label>)}</div></fieldset>
      {visibility==='public' && <label className="share-beta-choice"><input type="checkbox" checked={beta} onChange={e=>setBeta(e.target.checked)} /><span><strong>Share as beta</strong><small>Also show this video in this route's Community Beta and share your height and wingspan for comparison.</small></span></label>}
    </fieldset>
    {error && <p className="form-error" role="alert">{error}</p>}
    <div className="edit-video-actions"><button type="button" className="btn btn-outline" disabled={busy} onClick={close}>Cancel</button><button type="submit" className="btn btn-solid" disabled={busy || !title.trim()}>{busy?'Saving…':'Save changes'}</button></div>
  </form>
}
