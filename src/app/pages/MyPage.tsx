import { useEffect, useState, type ReactNode } from 'react'
import { type Session } from '../../api'
import type { AppController } from '../useAppController'
import { LibraryPage } from './LibraryPage'
import '../../styles/my-page.css'

type Props = { session: Session; libraryProps: AppController['pages']['libraryScreen']; computeContent: ReactNode }
const dayKey = (date: Date) => date.toISOString().slice(0, 10)
export function MyPage({ session, libraryProps, computeContent }: Props) {
  const [section, setSection] = useState<'library' | 'calendar'>('library')
  useEffect(() => {
    const open = () => setSection('library')
    window.addEventListener('open-my-skeletons', open)
    return () => window.removeEventListener('open-my-skeletons', open)
  }, [])
  const user = session.user
  const [selectedDay, setSelectedDay] = useState(dayKey(new Date()))
  const [year, setYear] = useState(new Date().getUTCFullYear())
  const records = new Map<string, Map<string, { count: number; routes: Set<string> }>>()
  for (const video of libraryProps.myVideos) {
    const day = video.created_at.slice(0, 10)
    const gym = libraryProps.catalogRoutes.find(r => r.id === video.route_id)?.gym ?? 'Unknown gym'
    if (!records.has(day)) records.set(day, new Map())
    const gyms = records.get(day)!
    const group = gyms.get(gym) ?? { count: 0, routes: new Set<string>() }
    group.count++; group.routes.add(video.route_id); gyms.set(gym, group)
  }
  const first = new Date(Date.UTC(year, 0, 1)); const last = new Date(Date.UTC(year, 11, 31))
  const days: Date[] = []
  for (let d = new Date(first); d <= last; d.setUTCDate(d.getUTCDate() + 1)) days.push(new Date(d))
  const count = (key: string) => [...(records.get(key)?.values() ?? [])].reduce((n, g) => n + g.count, 0)
  const intro = <>
    <section className="my-page-profile" aria-label="My profile">
      <div className="my-page-identity"><span className="my-page-avatar" aria-hidden="true">{user.display_name.slice(0, 1).toUpperCase()}</span><div><h1>{user.display_name}</h1><p>@{user.username}</p></div><button type="button" onClick={() => libraryProps.go('profile')}>Edit profile</button></div>
      {user.bio && <p className="my-page-bio">{user.bio}</p>}
      <div className="my-page-stats" aria-label="Social statistics">{['Likes received', 'Saves received', 'Followers', 'Following'].map(label => <div key={label}><strong>0</strong><span>{label}</span></div>)}</div>
    </section>
    <nav className="my-page-sections" aria-label="My Page sections"><button className={section === 'library' ? 'active' : ''} onClick={() => setSection('library')}>My Library</button><button className={section === 'calendar' ? 'active' : ''} onClick={() => setSection('calendar')}>My Calendar</button></nav>
  </>
  if (section === 'library') return <LibraryPage {...libraryProps} pageIntro={intro} computeContent={computeContent} />
  return <main className="screen with-header library-page">{intro}<section className="my-calendar" aria-label="Climbing activity calendar">
    <div className="calendar-heading"><h2>My Calendar</h2><label>Year <select value={year} onChange={e => setYear(Number(e.target.value))}>{[new Date().getUTCFullYear(), ...libraryProps.myVideos.map(v => Number(v.created_at.slice(0, 4)))].filter((v, i, all) => all.indexOf(v) === i).sort((a,b) => b-a).map(y => <option key={y}>{y}</option>)}</select></label></div>
    <p className="calendar-caption">Upload activity · UTC</p>
    <div className="calendar-months">{Array.from({length:12}, (_,month) => {
      const monthDays = days.filter(date => date.getUTCMonth() === month)
      const monthName = new Intl.DateTimeFormat('en', {month:'short', timeZone:'UTC'}).format(monthDays[0])
      return <section className="calendar-month" key={month} aria-label={`${monthName} ${year}`}><h3>{monthName}</h3><div className="calendar-grid">
        {Array.from({length:monthDays[0].getUTCDay()}, (_,i) => <span key={`blank-${i}`} />)}
        {monthDays.map(date => {
          const key = dayKey(date); const n = count(key); const level = n === 0 ? 0 : n < 2 ? 1 : n < 4 ? 2 : n < 7 ? 3 : 4
          const summary = [...(records.get(key)?.entries() ?? [])].map(([gym,g]) => `${gym}: ${g.routes.size} routes, ${g.count} attempts`).join('; ')
          return <button key={key} type="button" className={`calendar-day level-${level}`} aria-pressed={selectedDay === key} aria-label={`${key}: ${summary || 'No uploads'}`} title={`${key}: ${summary || 'No uploads'}`} onClick={() => setSelectedDay(key)} onFocus={() => setSelectedDay(key)} onMouseEnter={() => setSelectedDay(key)} />
        })}
      </div></section>
    })}</div>
    <div className="calendar-legend">Uploads per day: {['0', '1', '2–3', '4–6', '7+'].map((label,i) => <span key={label}><i className={`calendar-day level-${i}`} />{label}</span>)}</div>
    <div className="calendar-detail" aria-live="polite"><h3>{selectedDay}</h3>{records.has(selectedDay) ? [...records.get(selectedDay)!.entries()].map(([gym,g]) => <p key={gym}>{gym} · {g.routes.size} different routes · {g.count} recorded attempts</p>) : <p>No video uploads on this date.</p>}</div>
  </section></main>
}
