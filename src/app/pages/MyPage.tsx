import { useEffect, useRef, useState, type ReactNode } from 'react'
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
  const [month, setMonth] = useState(new Date().getUTCMonth())
  const swipe = useRef<{x:number; y:number; moved:boolean} | null>(null)
  const suppressClick = useRef(false)
  function showMonth(next:number, nextYear=year) {
    if (next < 0 || next > 11) return
    setYear(nextYear); setMonth(next)
    const now = new Date()
    setSelectedDay(dayKey(nextYear === now.getUTCFullYear() && next === now.getUTCMonth() ? now : new Date(Date.UTC(nextYear,next,1))))
  }
  const records = new Map<string, Map<string, { count: number; routes: Set<string> }>>()
  for (const video of libraryProps.myVideos) {
    const day = video.created_at.slice(0, 10)
    const gym = libraryProps.catalogRoutes.find(r => r.id === video.route_id)?.gym ?? 'Unknown gym'
    if (!records.has(day)) records.set(day, new Map())
    const gyms = records.get(day)!
    const group = gyms.get(gym) ?? { count: 0, routes: new Set<string>() }
    group.count++; group.routes.add(video.route_id); gyms.set(gym, group)
  }
  const first = new Date(Date.UTC(year, month, 1)); const last = new Date(Date.UTC(year, month + 1, 0))
  const days: Date[] = []
  for (let d = new Date(first); d <= last; d.setUTCDate(d.getUTCDate() + 1)) days.push(new Date(d))
  const count = (key: string) => [...(records.get(key)?.values() ?? [])].reduce((n, g) => n + g.count, 0)
  const intro = <>
    <section className="my-page-profile" aria-label="My profile">
      <div className="my-page-identity"><span className="my-page-avatar" aria-hidden="true">{user.display_name.slice(0, 1).toUpperCase()}</span><div><h1>{user.display_name}</h1><p>@{user.username}</p></div><button type="button" onClick={() => libraryProps.go('profile')}>Edit profile</button></div>
      {user.bio && <p className="my-page-bio">{user.bio}</p>}
      <div className="my-page-stats" aria-label="Social statistics">{['Likes received', 'Saves received', 'Followers', 'Following'].map(label => <div key={label}><strong>0</strong><span>{label}</span></div>)}</div>
    </section>
    <nav className="my-page-sections" aria-label="My Page sections"><button className={section === 'library' ? 'active' : ''} onClick={() => setSection('library')}>My Library</button><button className={section === 'calendar' ? 'active' : ''} onClick={() => {showMonth(new Date().getUTCMonth());setSection('calendar')}}>My Calendar</button></nav>
  </>
  if (section === 'library') return <LibraryPage {...libraryProps} pageIntro={intro} computeContent={computeContent} />
  return <main className="screen with-header library-page">{intro}<section className="my-calendar" aria-label="Climbing activity calendar">
    <div className="calendar-heading"><h2>My Calendar</h2><label>Year <select value={year} onChange={e => showMonth(new Date().getUTCMonth(), Number(e.target.value))}>{[new Date().getUTCFullYear(), ...libraryProps.myVideos.map(v => Number(v.created_at.slice(0, 4)))].filter((v, i, all) => all.indexOf(v) === i).sort((a,b) => b-a).map(y => <option key={y}>{y}</option>)}</select></label></div>
    <p className="calendar-caption">Upload activity · UTC</p>
    <div className="calendar-month-navigation">
      <button type="button" aria-label="Previous month" disabled={month === 0} onClick={() => showMonth(month - 1)}>‹</button>
      <h3 aria-live="polite">{new Intl.DateTimeFormat('en', {month:'long',year:'numeric',timeZone:'UTC'}).format(first)}</h3>
      <button type="button" aria-label="Next month" disabled={month === 11} onClick={() => showMonth(month + 1)}>›</button>
    </div>
    <section className="calendar-month-view" aria-label="Monthly activity" data-horizontal-swipe
      onPointerDown={event => {
        if (!event.isPrimary || event.button !== 0) {swipe.current=null;return}
        event.stopPropagation()
        suppressClick.current=false
        swipe.current={x:event.clientX,y:event.clientY,moved:false}
      }}
      onPointerMove={event => {
        const start=swipe.current
        if(!start) return
        const dx=event.clientX-start.x, dy=event.clientY-start.y
        if(Math.abs(dx)>12 && Math.abs(dx)>Math.abs(dy)*1.5) {
          start.moved=true;suppressClick.current=true
          event.currentTarget.setPointerCapture(event.pointerId)
        }
      }}
      onPointerUp={event => {
        const start=swipe.current;swipe.current=null
        if(!start) return
        const dx=event.clientX-start.x, dy=event.clientY-start.y
        if(start.moved && Math.abs(dx)>45 && Math.abs(dx)>Math.abs(dy)*1.5) showMonth(month+(dx<0?1:-1))
      }}
      onPointerCancel={() => {swipe.current=null}}
      onClickCapture={event => {if(suppressClick.current){event.preventDefault();event.stopPropagation();suppressClick.current=false}}}
    >
      <div className="calendar-weekdays" aria-hidden="true">{['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(day=><span key={day}>{day}</span>)}</div>
      <div className="calendar-month-grid">
        {Array.from({length:first.getUTCDay()}, (_,i) => <span key={`blank-${i}`} />)}
        {days.map(date => {
          const key = dayKey(date); const n = count(key); const level = n === 0 ? 0 : n < 2 ? 1 : n < 4 ? 2 : n < 7 ? 3 : 4
          const summary = [...(records.get(key)?.entries() ?? [])].map(([gym,g]) => `${gym}: ${g.routes.size} routes, ${g.count} attempts`).join('; ')
          return <button key={key} type="button" className={`calendar-day level-${level}`} aria-pressed={selectedDay === key} aria-label={`${key}: ${summary || 'No uploads'}`} title={`${key}: ${summary || 'No uploads'}`} onClick={() => setSelectedDay(key)} onFocus={() => setSelectedDay(key)} onMouseEnter={() => {if(!swipe.current)setSelectedDay(key)}}>{date.getUTCDate()}</button>
        })}
      </div>
    </section>
    <div className="calendar-legend">Uploads per day: {['0', '1', '2–3', '4–6', '7+'].map((label,i) => <span key={label}><i className={`calendar-day level-${i}`} />{label}</span>)}</div>
    <div className="calendar-detail" aria-live="polite"><h3>{selectedDay}</h3>{records.has(selectedDay) ? [...records.get(selectedDay)!.entries()].map(([gym,g]) => <p key={gym}>{gym} · {g.routes.size} different routes · {g.count} recorded attempts</p>) : <p>No video uploads on this date.</p>}</div>
  </section></main>
}
