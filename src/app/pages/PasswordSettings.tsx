import { useState, type FormEvent } from 'react'
import { api, type Session } from '../../api'
export function PasswordSettings({session}:{session:Session}) {
  const [current,setCurrent] = useState('')
  const [password,setPassword] = useState('')
  const [confirm,setConfirm] = useState('')
  const [busy,setBusy] = useState(false)
  const [error,setError] = useState('')
  const [done,setDone] = useState(false)
  async function submit(event:FormEvent) {
    event.preventDefault()
    if(busy) return
    setDone(false); setError('')
    if(password !== confirm) {setError('New passwords do not match.');return}
    setBusy(true)
    try {
      await api<void>('/profile/password',{method:'POST',csrf:session.csrf_token,body:{current_password:current,new_password:password}})
      setCurrent('');setPassword('');setConfirm('');setDone(true)
    } catch(e) {setError((e as Error).message)} finally {setBusy(false)}
  }
  return <details className="password-settings"><summary>Change password</summary><form onSubmit={e => void submit(e)}>
    <label>Current password<input type="password" autoComplete="current-password" required maxLength={128} value={current} onChange={e=>setCurrent(e.target.value)} /></label>
    <label>New password<input type="password" autoComplete="new-password" required minLength={8} maxLength={128} value={password} onChange={e=>setPassword(e.target.value)} /></label>
    <label>Confirm new password<input type="password" autoComplete="new-password" required minLength={8} maxLength={128} value={confirm} onChange={e=>setConfirm(e.target.value)} /></label>
    <p className="setting-description">At least 8 characters. Other signed-in sessions will be signed out.</p>
    {error && <p role="alert">{error}</p>}{done && <p role="status">Password updated.</p>}
    <button className="btn btn-outline" type="submit" disabled={busy}>{busy?'Updating…':'Update password'}</button>
  </form></details>
}
