import { useEffect, useState } from 'react'
import { api, type Session, type User } from '../../api'

type PrivacyKey = 'measurements_visible' | 'library_visible' | 'likes_visible' | 'saves_visible' | 'skeletons_visible' | 'calendar_visible'
const settings: {key:PrivacyKey; label:string; detail:string; library?:boolean}[] = [
  {key:'measurements_visible',label:'Body measurements',detail:'Show height and arm span on your public profile.'},
  {key:'library_visible',label:'My Library',detail:'Show your Public videos on your profile. Private videos always stay private.'},
  {key:'likes_visible',label:'Liked videos',detail:'Show the public videos you have liked.',library:true},
  {key:'saves_visible',label:'Saved Beta',detail:'Show the public videos you have saved.',library:true},
  {key:'skeletons_visible',label:'My Skeletons',detail:'Share completed preview videos while their source remains Public. Preview images may reveal your proportions.',library:true},
  {key:'calendar_visible',label:'My Calendar',detail:'Show activity from Public video uploads.'},
]
export function ProfilePrivacy({ session }: {session: Session}) {
  const [user, setUser] = useState(session.user)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    api<Session>('/auth/me', {signal:controller.signal}).then(value => {if (!controller.signal.aborted) setUser(value.user)}).catch(e => {if (!controller.signal.aborted) setError((e as Error).message)}).finally(() => {if (!controller.signal.aborted) setLoading(false)})
    return () => controller.abort()
  }, [session.user.id])
  async function save(patch: Partial<User>) {
    if (busy || loading) return
    setBusy(true); setError('')
    const next = {...user,...patch}
    const body = {account_visibility:next.account_visibility ?? 'public', ...Object.fromEntries(settings.map(s => [s.key,next[s.key] ?? false]))}
    try {
      const result = await api<{user: User}>('/profile/privacy', {method:'PATCH', csrf:session.csrf_token, body})
      setUser(result.user)
    } catch(e) {setError((e as Error).message)} finally {setBusy(false)}
  }
  return <section className="profile-edit-section"><h2>Privacy</h2>
    <label className="privacy-setting">Account visibility<select disabled={busy || loading} value={user.account_visibility ?? 'public'} onChange={e => void save({account_visibility:e.target.value as 'public'|'private'})}><option value="public">Public</option><option value="private">Private</option></select></label>
    <p className="setting-description">Private hides your full profile, including all sections below. Individually published Public videos remain in Community.</p>
    <h3 className="privacy-subheading">On my public profile</h3>
    {settings.map(setting => <div key={setting.key} className={setting.library ? 'privacy-library-child' : ''}>
      <label className="privacy-setting"><span>{setting.label}</span><input type="checkbox" disabled={busy || loading || (setting.library && !user.library_visible)} checked={user[setting.key] ?? false} onChange={e => void save({[setting.key]:e.target.checked})} /></label>
      <p className="setting-description">{setting.detail}</p>
    </div>)}
    <p className="setting-description">Want to Try stays private. Share as beta separately shares height and arm span with that video's viewers.</p>
    {loading && <p role="status">Loading settings…</p>}{busy && <p role="status">Saving…</p>}{error && <p role="alert">{error}</p>}
  </section>
}
