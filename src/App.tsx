import { useMemo, useRef, useState, useEffect } from "react"

type Screen = "home" | "account" | "profile" | "community" | "gyms" | "gallery" | "route" | "workspace" | "beta" | "library"

type LibraryTab = "attempts" | "saved" | "wanted"
type WorkspaceEntry = "attempt" | "upload" | "community"
type BetaOrigin = "community" | "workspace"

const gyms = [
  { name: "Gym A", place: "North District", count: 2 },
  { name: "Gym B", place: "West District", count: 0 },
]

const routes = [
  {
    gym: "Gym A",
    id: "r1",
    name: "Corner Study",
    grade: "V3",
    version: "Set 02",
    archived: false,
  },
  {
    gym: "Gym A",
    id: "r2",
    name: "Long Reach",
    grade: "V5",
    version: "Set 01",
    archived: false,
  },
  {
    gym: "Gym A",
    id: "r3",
    name: "Old Slab",
    grade: "V2",
    version: "Set 04",
    archived: true,
    showArchiveBadge: true,
  },
]

const betaCards = [
  {
    id: "b1",
    author: "Nora P.",
    gym: "Gym A",
    route: "Corner Study",
    grade: "V3",
  },
  {
    id: "b3",
    author: "Jo M.",
    gym: "Gym A",
    route: "Long Reach",
    grade: "V5",
  },
]

type TechniqueTerm = { definition: string } & { use: string }

const techniqueTerms: Record<string, TechniqueTerm> = {
  "drop knee": {
    definition:
      "Rotate one knee inward and lower it to bring the hips closer to the wall.",
    use: "Useful when a side-on body position can reduce the reach distance.",
  },
  "inside edge": {
    definition:
      "Place the inside edge of the climbing shoe on a hold for controlled pressure.",
    use: "Useful for stable footwork while rotating the hips toward the wall.",
  },
  flag: {
    definition:
      "Extend a free leg across or behind the body to counterbalance movement.",
    use: "Useful when only one foot is weighted and the body begins to swing.",
  },
}

function AppButton({
  children,
  onClick,
  variant = "solid",
  className = "",
  disabled = false,
}: {
  children: React.ReactNode
  onClick?: () => void
  variant?: "solid" | "outline" | "text"
  className?: string
  disabled?: boolean
}) {
  return (
    <button
      className={`btn btn-${variant} ${className}`}
      type="button"
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  )
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  type?: string
}) {
  return (
    <label className="field">
      {label && <span>{label}</span>}
      <input
        aria-label={label || placeholder}
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  )
}

function SelectField({
  label,
  value,
  onChange,
  children,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  children: React.ReactNode
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {children}
      </select>
    </label>
  )
}

const signedDifference = (value: number) => `${value > 0 ? "+" : ""}${value}`

const routeLabel = (idOrName: string) => {
  const route = routes.find(route => route.id === idOrName || route.name === idOrName)
  return route ? `${route.gym} · ${route.grade}` : idOrName
}

const mediaPath = (name: string) => `${import.meta.env.BASE_URL}media/${name}`
const routeMedia = (id: string) => {
  const trial = id === "r1" ? 2 : id === "r2" ? 3 : 1
  return { video: mediaPath(`trial${trial}.mp4`), poster: mediaPath(`trial${trial}-poster.jpg`), wall: mediaPath(`wall${trial}.jpg`), pose: trial === 1 ? null : mediaPath(`pose${trial}.mp4`) }
}
function MediaImage({routeId, wall = false, className = ""}: {routeId: string; wall?: boolean; className?: string}) {
  const media = routeMedia(routeId)
  return <img className={`real-media-image ${className}`} src={wall ? media.wall : media.poster} alt={wall ? "Climbing wall and holds" : "Climbing recording preview"} loading="lazy" />
}
function MediaVideo({routeId, pose = false, seekTime, measurementLabel}: {routeId: string; pose?: boolean; seekTime?: number; measurementLabel?: string}) {
  const media = routeMedia(routeId)
  const ref = useRef<HTMLVideoElement>(null)
  const src = pose ? media.pose : media.video
  const [playing, setPlaying] = useState(false)
  useEffect(() => setPlaying(false), [src])
  useEffect(() => {if (ref.current && seekTime !== undefined) ref.current.currentTime = seekTime}, [seekTime])
  if (!src) return <p className="empty-state">No skeleton recording for this route yet.</p>
  return <><video ref={ref} key={src} className="real-media-video" src={src} poster={pose ? undefined : media.poster} controls playsInline preload="metadata" onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} />{measurementLabel && <span className={`video-body-label${playing ? " is-hidden" : ""}`} aria-hidden={playing}>{measurementLabel}</span>}</>
}

function Placeholder({
  children,
  className = "",
}: {
  children: React.ReactNode
  className?: string
}) {
  return <div className={`placeholder ${className}`}>{children}</div>
}

function PlaybackButton() {
  const [playing, setPlaying] = useState(false)

  return (
    <button
      className="playback-toggle"
      type="button"
      aria-label={playing ? "Pause video" : "Play video"}
      aria-pressed={playing}
      onClick={() => setPlaying(!playing)}
    >
      {playing ? (
        <span className="pause-symbol" aria-hidden="true">
          <i />
          <i />
        </span>
      ) : (
        <span className="play-symbol" aria-hidden="true" />
      )}
    </button>
  )
}

function App() {
  const [screen, setScreen] = useState<Screen>("home")
  const [history, setHistory] = useState<Screen[]>([])
  const [notice, setNotice] = useState("")
  const [search, setSearch] = useState("")
  const [gymFilter, setGymFilter] = useState("All gyms")
  const [gradeFilter, setGradeFilter] = useState("All grades")
  const [selectedGym, setSelectedGym] = useState("Gym A")
  const [selectedRoute, setSelectedRoute] = useState(routes[0])
  const [savedBeta, setSavedBeta] = useState<string[]>([])
  const [wantedRoutes, setWantedRoutes] = useState<string[]>([])
  const [attempts, setAttempts] = useState<string[]>(["r1"])
  const [attemptRecords, setAttemptRecords] = useState([
    {
      id: "a1",
      routeId: "r1",
      date: "14 May 2025",
      duration: "0:18",
      status: "Private",
    },
    {
      id: "a2",
      routeId: "r1",
      date: "08 May 2025",
      duration: "0:21",
      status: "Private · Tip saved",
    },
    {
      id: "a3",
      routeId: "r1",
      date: "02 May 2025",
      duration: "0:16",
      status: "Private",
    },
  ])
  const [activeAttemptId, setActiveAttemptId] = useState("a1")
  const [manageMode, setManageMode] = useState<null | "menu" | "visibility" | "delete">(null)
  const [jobs, setJobs] = useState<Record<string, string>>({})
  const [demoFailure, setDemoFailure] = useState("none")
  const [uploadError, setUploadError] = useState(false)
  const [signedIn, setSignedIn] = useState(false)
  const [expandedComposer, setExpandedComposer] = useState<string | null>(null)
  const [commentDrafts, setCommentDrafts] = useState<Record<string,string>>({})
  const [comments, setComments] = useState<{id:string; source:string; text:string; author:string; parentId?:string; liked?:boolean}[]>([])
  const [replyTargets, setReplyTargets] = useState<Record<string,string | null>>({})
  const [replyDrafts, setReplyDrafts] = useState<Record<string,string>>({})
  const [expandedReplies, setExpandedReplies] = useState<string[]>([])
  const [confirmBody, setConfirmBody] = useState(false)
  const [bodyFailure, setBodyFailure] = useState(false)
  const [confidenceDemo, setConfidenceDemo] = useState(false)
  const activeAttempt = attemptRecords.find(record => record.id === activeAttemptId)
  const analyze = (id: string, fail = false) => {
    setJobs(j => ({...j,[id]:"Analyzing"}))
    window.setTimeout(() => setJobs(j => ({...j,[id]:fail ? "Analysis failed" : "Ready"})), 3500)
  }
  const renderCommentItem = (c: typeof comments[number], isReply = false) => {
    const replies = comments.filter(item => item.source === c.source && item.parentId === c.id)
    return <article className={`comment-item${isReply ? " comment-reply" : ""}`} key={c.id}>
      <span className="comment-avatar" aria-hidden="true">{c.author.slice(0,1).toUpperCase()}</span>
      <div className="comment-content">
        <div className="comment-byline"><strong>{c.author}</strong><span>Just now</span></div><p>{c.text}</p>
        <div className="comment-actions">
          <button type="button" aria-pressed={!!c.liked} className={c.liked ? "is-liked" : ""} onClick={() => {
            if (!signedIn) {setAccountMode("signin");go("account");return}
            setComments(items => items.map(item => item.id === c.id ? {...item,liked:!item.liked} : item))
          }}><span aria-hidden="true">{c.liked ? "♥" : "♡"}</span> {c.liked ? "Liked · 1" : "Like"}</button>
          <button type="button" onClick={() => setReplyTargets(targets => ({...targets,[c.source]:c.id}))}>Reply</button>
          <button type="button" aria-label="Delete my comment" onClick={() => {
            setComments(items => items.filter(item => item.id !== c.id && item.parentId !== c.id))
            setReplyTargets(targets => ({...targets,[c.source]:null}))
          }}>Delete</button>
        </div>
        {replyTargets[c.source] === c.id && <div className="inline-reply-composer">
          <label htmlFor={`reply-${c.id}`}>Replying to {c.author}</label>
          <div className="comment-input-wrap"><textarea id={`reply-${c.id}`} aria-label={`Reply to ${c.author}`} placeholder="Write a reply…" maxLength={500} value={replyDrafts[c.id] ?? ""} onChange={e => setReplyDrafts(d => ({...d,[c.id]:e.target.value}))}/>
          <div className="reply-compose-actions"><button type="button" className="comment-delete" onClick={() => setReplyTargets(targets => ({...targets,[c.source]:null}))}>Cancel</button>
          <button type="button" className="comment-post" disabled={signedIn && !(replyDrafts[c.id] ?? "").trim()} onClick={() => {
            if (!signedIn) {setAccountMode("signin");go("account");return}
            const text = (replyDrafts[c.id] ?? "").trim(); if (!text) return
            const rootId = c.parentId ?? c.id
            setComments(items => [...items,{id:crypto.randomUUID(),source:c.source,text:isReply ? `@${c.author} ${text}` : text,author:profile.name || "You",parentId:rootId}])
            setReplyDrafts(d => ({...d,[c.id]:""}));setReplyTargets(targets => ({...targets,[c.source]:null}));setExpandedReplies(ids => ids.includes(rootId) ? ids : [...ids,rootId])
          }}>{signedIn ? "Post reply" : "Sign in to reply"}</button></div></div>
        </div>}
        {!isReply && replies.length > 0 && <><button type="button" className="replies-toggle" aria-expanded={expandedReplies.includes(c.id)} onClick={() => setExpandedReplies(ids => ids.includes(c.id) ? ids.filter(id => id !== c.id) : [...ids,c.id])}>{expandedReplies.includes(c.id) ? "Hide replies" : `View ${replies.length} ${replies.length === 1 ? "reply" : "replies"}`}</button>{expandedReplies.includes(c.id) && <div className="comment-replies">{replies.map(reply => renderCommentItem(reply,true))}</div>}</>}
      </div>
    </article>
  }
  const renderComments = (source: string) => <section className="comment-section" aria-label="Comments">
    <div className="comments-heading"><h2>Comments</h2><span className="comment-count">{comments.filter(c => c.source === source).length}</span></div>
    {comments.filter(c => c.source === source).length === 0 && <div className="comments-empty"><strong>Start the conversation</strong><p>Share a thought or ask about this beta.</p></div>}
    <div className="comment-list" aria-live="polite">
      {comments.filter(c => c.source === source && !c.parentId).map(c => renderCommentItem(c))}
    </div>
    <div className={`comment-composer compact-composer${expandedComposer === source ? " is-expanded" : ""}`} onBlur={e => {if (!e.currentTarget.contains(e.relatedTarget as Node | null) && !(commentDrafts[source] ?? "").trim()) setExpandedComposer(null)}}>
      <span className="comment-avatar" aria-hidden="true">{signedIn ? (profile.name || "You").slice(0,1).toUpperCase() : "○"}</span>
      <div className="comment-input-wrap">
        <textarea rows={1} onFocus={() => setExpandedComposer(source)} aria-label="Write a comment" placeholder="Add a comment…" maxLength={500} value={commentDrafts[source] ?? ""} onChange={e => setCommentDrafts(d => ({...d,[source]:e.target.value}))}/>
        <div className="comment-compose-footer"><span>{(commentDrafts[source] ?? "").length > 400 ? `${(commentDrafts[source] ?? "").length}/500` : ""}</span>
          <button type="button" className="comment-post" disabled={signedIn && !(commentDrafts[source] ?? "").trim()} onClick={() => {
            if (!signedIn) {setAccountMode("signin");go("account");return}
            const text = (commentDrafts[source] ?? "").trim(); if (!text) return
            setComments(c => [...c,{id:crypto.randomUUID(),source,text,author:profile.name || "You"}]);setCommentDrafts(d => ({...d,[source]:""}));setExpandedComposer(null)
          }}>{signedIn ? "Post" : "Sign in to post"}</button>
        </div>
      </div>
    </div>
  </section>
  const [libraryTab, setLibraryTab] = useState<LibraryTab>("attempts")
  const [workspaceSource, setWorkspaceSource] = useState(
    "My attempt — Corner Study",
  )
  const [workspaceEntry, setWorkspaceEntry] =
    useState<WorkspaceEntry>("attempt")
  const [workspaceBetaId, setWorkspaceBetaId] = useState("b1")
  const [betaOrigin, setBetaOrigin] = useState<BetaOrigin>("workspace")
  const [likedBeta, setLikedBeta] = useState<string[]>([])
  const [hasAttempt, setHasAttempt] = useState(true)
  const [uploadState, setUploadState] =
    useState<"hidden" | "empty" | "preview" | "loading" | "saved">("hidden")
  const [uploadPrivacy, setUploadPrivacy] = useState<"Private" | "Public" | null>(null)
  const [historyVisible, setHistoryVisible] = useState(false)
  const [cueTime, setCueTime] = useState(7)
  const [, setSuggestionsVisible] = useState(false)
  const [betaVisible, setBetaVisible] = useState(false)
  const [activeTerm, setActiveTerm] = useState<string | null>(null)
  const [generationState, setGenerationState] =
    useState<"idle" | "preparing" | "adapting" | "ready" | "failed">("idle")
  const generationRun = useRef(0)
  const [expandedVideo, setExpandedVideo] = useState<string | null>(null)
  const [profile, setProfile] = useState({
    name: "",
    height: "",
    wingspan: "",
  })
  const [account, setAccount] = useState({ email: "", password: "" })
  const [accountMode, setAccountMode] = useState<"signin" | "signup">("signin")
  const [measurementPrompt, setMeasurementPrompt] = useState(false)

  const go = (next: Screen) => {
    setHistory((items) => [...items, screen])
    setScreen(next)
    setNotice("")
  }

  const back = () => {
    const previous = history.at(-1) ?? "home"
    setHistory((items) => items.slice(0, -1))
    setScreen(previous)
    setNotice("")
  }

  const openRoute = (route = routes[0]) => {
    setSelectedRoute(route)
    setSelectedGym(route.gym)
    go("route")
  }

  const openWorkspace = (
    source: string,
    entry: WorkspaceEntry = "attempt",
    betaId = "b1",
  ) => {
    setManageMode(null)
    setUploadError(false)
    if (entry === "attempt") setActiveAttemptId(betaId.startsWith("a") ? betaId : (attemptRecords.find(r => r.routeId === (routes.find(r => source.includes(r.name))?.id ?? selectedRoute.id))?.id ?? "a1"))
    setWorkspaceSource(source)
    setWorkspaceEntry(entry)
    setWorkspaceBetaId(betaId)
    setSuggestionsVisible(false)
    setBetaVisible(false)
    setActiveTerm(null)
    if (entry === "upload") {
      setHasAttempt(false)
      setUploadState("empty")
      setUploadPrivacy(null)
    } else if (entry === "attempt") {
      setHasAttempt(true)
      setUploadState("hidden")
    } else {
      const existingAttempt = attempts.includes(selectedRoute.id)
      setHasAttempt(existingAttempt)
      setUploadState("hidden")
    }
    go("workspace")
  }

  const toggle = (
    id: string,
    values: string[],
    update: (next: string[]) => void,
  ) => {
    update(
      values.includes(id)
        ? values.filter((value) => value !== id)
        : [...values, id],
    )
  }

  const pageTitle: Record<Screen, string> = {
    home: "BetaLab",
    account: "Account",
    profile: "Profile",
    community: "Community",
    gyms: "Select Gym",
    gallery: selectedGym,
    route: "Route",
    workspace: "Beta Workspace",
    beta: "Community Beta",
    library: "My Library",
  }

  const header = screen !== "home" && (
    <header className="topbar">
      <AppButton variant="text" onClick={back} className="back">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m14 6-6 6 6 6" /></svg><span>Back</span>
      </AppButton>
      <strong>{pageTitle[screen]}</strong>
      <span className="header-spacer" aria-hidden="true" />
    </header>
  )

  const flash = (message: string) => {
    setNotice(message)
    window.setTimeout(() => setNotice(""), 2200)
  }

  const startBodyPreview = () => {
    const run = ++generationRun.current
    setConfirmBody(false)
    setGenerationState("preparing")
    window.setTimeout(() => {
      if (generationRun.current === run) setGenerationState("adapting")
    }, 700)
    window.setTimeout(() => {
      if (generationRun.current === run) setGenerationState(bodyFailure ? "failed" : "ready")
    }, 1500)
  }

  const resetBodyPreview = () => {
    generationRun.current += 1
    setGenerationState("idle")
  }

  const home = (
    <main className="screen home-screen home-redesign" style={{backgroundImage: `linear-gradient(180deg, rgba(225,240,253,.38) 0%, rgba(226,240,252,.18) 29%, rgba(235,245,253,.88) 61%, #f2f8fd 84%), url("${mediaPath("home-climbing-wall.png")}")`}}>
      <header className="home-header">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true">
            B
          </span>
          <h1>
            <span>Beta</span>
            <span>Lab</span>
          </h1>
        </div>
        <button
          className="account-icon-button"
          type="button"
          aria-label="Profile and account"
          onClick={() => {
            if (
              account.email ||
              profile.name ||
              profile.height ||
              profile.wingspan
            ) {
              go("profile")
            } else {
              setAccountMode("signin")
              go("account")
            }
          }}
        >
          <span className="account-icon" aria-hidden="true">
            <i />
            <i />
          </span>
        </button>
      </header>
      <div className="home-editorial">
        <span className="home-eyebrow">YOUR NEXT MOVE STARTS HERE</span>
        <h2>Find your<br/>next move<span>.</span></h2>
        <p>A new route. A different beta.<br/>Something that works for you.</p>
      </div>
      <nav className="home-entry-grid" aria-label="Primary">
        <button type="button" className="home-climb-entry" onClick={() => go("gyms")}>
          <span className="home-entry-icon"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m2 21 7-16 5 10 3-6 5 12ZM6 12l3 2 3-2"/></svg></span>
          <span className="home-entry-copy"><strong>Go Climbing</strong><small>Find a gym. Pick your route.</small></span>
        </button>
        <button type="button" className="home-secondary-entry" onClick={() => go("community")}>
          <span className="home-secondary-top"><span className="home-entry-icon"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M17 4a4 4 0 0 1 0 8M22 21v-2a4 4 0 0 0-3-4"/></svg></span></span>
          <strong>Community</strong><small>See another way up.</small>
        </button>
        <button type="button" className="home-secondary-entry home-library-entry" onClick={() => go("library")}>
          <span className="home-secondary-top"><span className="home-entry-icon"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 3h14v18l-7-4-7 4Z"/></svg></span></span>
          <strong>My Library</strong><small>Your climbs, collected.</small>
        </button>
      </nav>
    </main>
  )

  const accountScreen = (
    <main className="screen with-header form-page">
      <p>
        {accountMode === "signin"
          ? "Sign in to sync across devices. This is optional."
          : "Create an optional account. Body measurements help find closer beta."}
      </p>
      <div className="segmented">
        <button
          className={accountMode === "signin" ? "active" : ""}
          type="button"
          onClick={() => setAccountMode("signin")}
        >
          Sign in
        </button>
        <button
          className={accountMode === "signup" ? "active" : ""}
          type="button"
          onClick={() => setAccountMode("signup")}
        >
          Sign up
        </button>
      </div>
      <Field
        label="Email"
        value={account.email}
        onChange={(email) => setAccount({ ...account, email })}
        placeholder="name@example.com"
      />
      <Field
        label="Password"
        value={account.password}
        onChange={(password) => setAccount({ ...account, password })}
        placeholder="Demo password"
        type="password"
      />
      <div className="stack-actions">
        <AppButton
          onClick={() => {
            setSignedIn(true)
            if (accountMode === "signup") {
              setMeasurementPrompt(true)
            } else {
              flash("Signed in — returning to your prior action")
              back()
            }
          }}
        >
          {accountMode === "signup" ? "Create account" : "Submit"}
        </AppButton>
        <AppButton variant="outline" onClick={back}>
          Cancel
        </AppButton>
      </div>
      <p className="muted small">
        Your current content is preserved. No profile is required.
      </p>
    </main>
  )

  const profileScreen = (
    <main className="screen with-header form-page">
      <p>View and update your optional account and body information.</p>
      <Field
        label="Email"
        value={account.email}
        onChange={(email) => setAccount({ ...account, email })}
        placeholder="name@example.com"
      />
      <Field
        label="Name"
        value={profile.name}
        onChange={(name) => setProfile({ ...profile, name })}
        placeholder="Name"
      />
      <div className="field-row">
        <Field
          label="Height (cm)"
          value={profile.height}
          onChange={(height) => setProfile({ ...profile, height })}
          placeholder="168"
        />
        <Field
          label="Wingspan (cm)"
          value={profile.wingspan}
          onChange={(wingspan) => setProfile({ ...profile, wingspan })}
          placeholder="171"
        />
      </div>
      <div className="stack-actions">
        <AppButton
          onClick={() => {
            flash("Profile saved")
            back()
          }}
        >
          Save
        </AppButton>
        <AppButton variant="outline" onClick={back}>
          Skip
        </AppButton>
      </div>
      <p className="privacy-box">
        Profile details are private unless you choose to share them.
      </p>
    </main>
  )

  const filteredBeta = betaCards.filter((card) => {
    const term = search.toLowerCase()
    const matchesSearch = [card.author, card.gym, card.route, card.grade].some(
      (value) => value.toLowerCase().includes(term),
    )
    return (
      matchesSearch &&
      (gymFilter === "All gyms" || card.gym === gymFilter) &&
      (gradeFilter === "All grades" || card.grade === gradeFilter)
    )
  })

  const communityScreen = (
    <main className="screen with-header community-feed">
      <div className="community-search"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4.5 4.5"/></svg><input aria-label="Search community" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search routes, climbers or gyms"/>{search && <button type="button" aria-label="Clear community search" onClick={() => setSearch("")}>×</button>}</div>
      <div className="community-filters">
        <select aria-label="Gym" value={gymFilter} onChange={e => setGymFilter(e.target.value)}><option>All gyms</option><option>Gym A</option><option>Gym B</option></select>
        <select aria-label="Grade" value={gradeFilter} onChange={e => setGradeFilter(e.target.value)}><option>All grades</option><option>V3</option><option>V5</option></select>
      </div>
      <div className="section-heading">
        <h2>Community videos</h2>
      </div>
      <div className="card-list">
        {attemptRecords.filter(record => record.status.startsWith("Public")).filter(record => {const route = routes.find(r => r.id === record.routeId)!; return (gymFilter === "All gyms" || route.gym === gymFilter) && (gradeFilter === "All grades" || route.grade === gradeFilter) && (!search || route.name.toLowerCase().includes(search.toLowerCase()))}).map(record => <article className="video-card" key={record.id}><button className="community-video-link" onClick={() => {const route = routes.find(r => r.id === record.routeId)!;setSelectedRoute(route);setSelectedGym(route.gym);openWorkspace(`${record.date} · ${route.name}`, "attempt", record.id)}}><span className="community-video-media"><MediaImage routeId={record.routeId}/></span><span className="card-body"><strong>Your public video</strong><small>{routeLabel(record.routeId)} · {record.date}</small></span></button></article>)}
        {filteredBeta.map((card) => (
          <article className="video-card" key={card.id}>
            <button
              className="community-video-link"
              type="button"
              onClick={() => {
                const targetRoute =
                  routes.find((route) => route.name === card.route) ?? routes[0]
                setSelectedGym(card.gym)
                setSelectedRoute(targetRoute)
                setWorkspaceBetaId(card.id)
                setBetaOrigin("community")
                resetBodyPreview()
                setHasAttempt(attempts.includes(targetRoute.id))
                go("beta")
              }}
            >
              <span className="community-video-media">
                <MediaImage routeId={routes.find(route => route.name === card.route)?.id ?? "r1"} />
                <span className="community-play-icon" aria-hidden="true"><svg viewBox="0 0 20 20"><path d="m7 4.5 8 5.5-8 5.5Z" /></svg></span>
              </span>
              <span className="card-body">
                <span className="community-card-summary"><span className="community-card-location"><strong>{card.gym}</strong><span className="community-card-grade">{card.grade}</span></span><span className="community-card-author">By {card.author}</span></span>
              </span>
            </button>
          </article>
        ))}
        {filteredBeta.length === 0 && !attemptRecords.some(r => r.status.startsWith("Public")) && (
          <div className="empty-state">
            <strong>No beta found</strong>
            <p>Try clearing a filter.</p>
          </div>
        )}
      </div>
    </main>
  )

  const gymResults = gyms.filter(gym => `${gym.name} ${gym.place}`.toLowerCase().includes(search.trim().toLowerCase()))
  const gymsScreen = (
    <main className="screen with-header gym-selection">
      <header className="gym-selection-intro"><h1>Where to climb?</h1></header>
      <div className="gym-search"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4.5 4.5"/></svg><input aria-label="Search gyms by name or area" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search by name or area"/>{search && <button type="button" aria-label="Clear gym search" onClick={() => setSearch("")}>×</button>}</div>
      <div className="gym-list-heading"><h2>{search.trim() ? "Search results" : "Explore gyms"}</h2><span>{gymResults.length} {gymResults.length === 1 ? "gym" : "gyms"}</span></div>
      <div className="card-list gym-selection-list">
        {gymResults.map(gym => <button className="gym-card" type="button" key={gym.name} onClick={() => {setSelectedGym(gym.name);go("gallery")}}>
          <span className="gym-cover">{gym.name === "Gym A" ? <MediaImage routeId="r1" wall /> : <span className="gym-cover-placeholder"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m3 20 7-15 4 8 2-4 5 11H3Z"/><path d="m7 11 3 2 2-2"/></svg><span>No photo yet</span></span>}</span>
          <span className="gym-card-info"><b>{gym.name}</b><span className="gym-area">{gym.place}</span><span className={`gym-route-count${gym.count === 0 ? " is-empty" : ""}`}>{gym.count > 0 ? `${gym.count} active routes` : "No routes yet"}</span></span>
          <span className="gym-card-chevron" aria-hidden="true">›</span>
        </button>)}
      </div>
      {gymResults.length === 0 && <div className="gym-search-empty"><strong>No gyms found</strong><p>Try a different name or area.</p></div>}
    </main>
  )

  const galleryScreen = (
    <main className="screen with-header route-gallery-page">
      <header className="route-gallery-intro"><h1>{selectedGym}</h1>
      <div className="gallery-tools">
        <SelectField
          label="Grade"
          value={gradeFilter}
          onChange={setGradeFilter}
        >
          <option>All grades</option>
          <option>V2</option>
          <option>V3</option>
          <option>V5</option>
        </SelectField>
      </div>
      </header>
      {wantedRoutes.some(id => routes.find(route => route.id === id)?.gym === selectedGym) && (
        <section className="marked-strip">
          <div className="section-heading">
            <h2>Marked routes</h2>
            <span>{wantedRoutes.filter(id => routes.find(route => route.id === id)?.gym === selectedGym).length}</span>
          </div>
          <div>
            {wantedRoutes.filter(id => routes.find(route => route.id === id)?.gym === selectedGym).map((id) => (
              <button
                type="button"
                key={id}
                onClick={() =>
                  openRoute(routes.find((route) => route.id === id))
                }
              >
                {routeLabel(id)} →
              </button>
            ))}
          </div>
        </section>
      )}

      {selectedGym === "Gym B" && <div className="empty-state"><strong>No route footage yet</strong><p>We are collecting routes for this gym. Browse Gym A for the available samples.</p></div>}
      <div className="card-list route-list">
        {routes
          .filter(
            (route) =>
              route.gym === selectedGym && (gradeFilter === "All grades" || route.grade === gradeFilter),
          )
          .map((route) => (
            <article className="route-card" key={route.id}>
              <button
                className="route-open"
                type="button"
                onClick={() => openRoute(route)}
              >
                <MediaImage routeId={route.id} wall />
                <span>
                  <b>{route.gym}</b>
                  <span className="gallery-route-meta"><span className="gallery-grade">{route.grade}</span></span>
                  {route.archived && route.showArchiveBadge !== false && (
                    <em>Archived route</em>
                  )}
                </span>
              </button>
              <button
                className={`bookmark-button ${
                  wantedRoutes.includes(route.id) ? "marked" : ""
                }`}
                type="button"
                aria-label={
                  wantedRoutes.includes(route.id)
                    ? `Remove ${routeLabel(route.id)} bookmark`
                    : `Bookmark ${routeLabel(route.id)}`
                }
                aria-pressed={wantedRoutes.includes(route.id)}
                onClick={() => toggle(route.id, wantedRoutes, setWantedRoutes)}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M6.5 3.5h11v17l-5.5-3.8-5.5 3.8z" />
                </svg>
              </button>
            </article>
          ))}
      </div>
    </main>
  )

  const routeAttempts = attemptRecords.filter(
    (attempt) => attempt.routeId === selectedRoute.id,
  )

  const routeScreen = (
    <main className="screen with-header route-detail-page">
      <div className="route-detail-heading"><h1>{selectedGym}</h1><span>{selectedRoute.grade}</span></div>
      {selectedRoute.archived && (
        <p className="archive-label">Archived — available for past attempts</p>
      )}
      <MediaImage routeId={selectedRoute.id} wall className="route-image" />
      <button
        className="add-attempt-card"
        type="button"
        onClick={() =>
          openWorkspace(`New attempt — ${selectedRoute.name}`, "upload")
        }
      >
        <span className="add-video-symbol" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14" /></svg></span>
        <strong>Add my video</strong>
      </button>
      <div className="section-heading previous-attempts-heading">
        <h2>Previous attempts</h2>
        <span>{routeAttempts.length}</span>
      </div>
      <div className="attempt-history">
        {routeAttempts.map((attempt, index) => (
          <button
            type="button"
            key={attempt.id}
            onClick={() =>
              openWorkspace(
                `${attempt.date} · ${selectedRoute.name}`,
                "attempt",
                attempt.id,
              )
            }
          >
            <span className="attempt-cover"><MediaImage routeId={selectedRoute.id} /><span className="attempt-play" aria-hidden="true"><svg viewBox="0 0 16 16"><path d="m5 3 7 5-7 5Z" /></svg></span></span>
            <span>
              <b>Attempt {routeAttempts.length - index}</b>
              <small>
                {attempt.date} · {attempt.duration}
              </small>
              <small>{attempt.status}</small>
            </span>
          </button>
        ))}
        {routeAttempts.length === 0 && (
          <div className="empty-state">
            <strong>No attempts yet</strong>
            <p>Add a video when you are ready.</p>
          </div>
        )}
      </div>
    </main>
  )

  const similarClimbers = [
    {
      id: "b1",
      name: "Nora P.",
      height: 170,
      wingspan: 172,
      cue: "Right foot before the cross-through",
      time: "0:32",
      bio: "Static climber · prefers controlled movement",
    },
    {
      id: "b2",
      name: "Sam K.",
      height: 166,
      wingspan: 170,
      cue: "Lower hip position through the reach",
      time: "0:19",
      bio: "Dynamic climber · compact reach",
    },
    {
      id: "b3",
      name: "Jo M.",
      height: 174,
      wingspan: 176,
      cue: "Different start point for the same move",
      time: "0:16",
      bio: "",
    },
  ]

  const selectedBeta =
    similarClimbers.find((climber) => climber.id === workspaceBetaId) ??
    similarClimbers[0]

  const betaDetailScreen = (
    <main className="screen with-header beta-detail-page">
      <header className="beta-video-info">
        <div className="beta-author-line"><h1>{selectedBeta.name}</h1><span>Original climber</span>
          {betaOrigin === "community" && <div className="beta-icon-actions">
            <button type="button" aria-label="Like video" title={likedBeta.includes(workspaceBetaId) ? "Unlike video" : "Like video"} aria-pressed={likedBeta.includes(workspaceBetaId)} onClick={() => toggle(workspaceBetaId, likedBeta, setLikedBeta)}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/></svg></button>
            <button type="button" aria-label="Save beta" title={savedBeta.includes(workspaceBetaId) ? "Remove saved beta" : "Save beta"} aria-pressed={savedBeta.includes(workspaceBetaId)} onClick={() => toggle(workspaceBetaId, savedBeta, setSavedBeta)}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h12a1 1 0 0 1 1 1v17l-7-4-7 4V4a1 1 0 0 1 1-1Z"/></svg></button>
          </div>}
        </div>
        <p className="beta-route-line">{selectedGym} <span>{selectedRoute.grade}</span></p>
        <p className="beta-climber-measurements">Original climber: {selectedBeta.height} cm height · {selectedBeta.wingspan} cm arm span</p>
      </header>

      {generationState === "idle" ? (
        <section className="beta-detail-video">
          <div className="video-frame">
            <MediaVideo routeId={selectedRoute.id} />
            <button
              className="expand-video"
              type="button"
              onClick={() => setExpandedVideo(`${selectedBeta.name} video`)}
            >
              Expand
            </button>
          </div>
          <div className="player-controls">
            <PlaybackButton />
            <input
              aria-label="Community beta timeline"
              type="range"
              min="0"
              max="18"
              defaultValue="6"
            />
            <span>00:06 / {selectedBeta.time}</span>
          </div>
            <AppButton
              className="generate-entry"
              onClick={() => {
                if (!routeMedia(selectedRoute.id).pose) { flash("No skeleton recording for this route yet"); return }
                if (profile.height && profile.wingspan) setConfirmBody(true)
                else setMeasurementPrompt(true)
              }}
            >
              Skeleton Preview
            </AppButton>
        </section>
      ) : (
        <section className="body-video-preview">
          <div className="section-heading">
            <h2>
              {generationState === "ready"
                ? "Your skeleton preview"
                : generationState === "preparing"
                  ? "Preparing proportions"
                  : "Adapting movement"}
            </h2>
            <AppButton variant="text" onClick={resetBodyPreview}>
              Original video
            </AppButton>
          </div>
          {generationState === "failed" ? <div className="process-status"><strong>Preview could not be generated</strong><p>Your original video is unchanged.</p><button className="btn btn-outline" onClick={() => {setBodyFailure(false);resetBodyPreview();setConfirmBody(true)}}>Retry</button></div> : generationState !== "ready" ? (
            <div className="generation-progress">
              <div>
                <i />
              </div>
              <p>
                {generationState === "preparing"
                  ? "Reading height and wingspan"
                  : "Building body-proportion preview"}
              </p>
            </div>
          ) : (
            <>
              <div className="video-frame skeleton-video-frame">
                <MediaVideo routeId={selectedRoute.id} pose measurementLabel={`Your proportions · Height ${profile.height ? `${profile.height} cm` : "—"} · Arm span ${profile.wingspan ? `${profile.wingspan} cm` : "—"}`} />
              </div>
              {confidenceDemo && <details className="confidence-note"><summary>Some joints need review · demo</summary><p>Example only: left wrist and right ankle positions are uncertain in an obscured section. No confidence report is attached to this recording yet; actual locations will come from the algorithm.</p></details>}
              <div className="player-controls">
                <PlaybackButton />
                <input
                  aria-label="Generated video timeline"
                  type="range"
                  min="0"
                  max="18"
                  defaultValue="6"
                />
                <span>00:06 / {selectedBeta.time}</span>
              </div>
            </>
          )}
        </section>
      )}
      {renderComments(`beta:${workspaceBetaId}`)}
    </main>
  )

  const saveUploadedAttempt = () => {
    if (!uploadPrivacy) return
    setUploadError(false); setUploadState("loading")
    const routeId = selectedRoute.id, privacy = uploadPrivacy, id = crypto.randomUUID(), failure = uploadError ? "none" : demoFailure
    window.setTimeout(() => {
      if (failure === "upload") {setUploadError(true);setUploadState("preview");return}
      setUploadState("saved");setHasAttempt(true);setWorkspaceEntry("attempt");setActiveAttemptId(id)
      setWorkspaceSource(`Today · ${selectedRoute.name}`)
      setAttemptRecords(records => [{id,routeId,date:"Today",duration:routeId === "r1" ? "0:32" : "0:16",status:privacy},...records])
      setAttempts(items => items.includes(routeId) ? items : [...items,routeId])
      setJobs(j => ({...j,[id]:"Video saved"}))
      window.setTimeout(() => analyze(id, failure === "analysis"), 900)
      flash("Video saved. You can leave while analysis runs.")
    }, 1400)
  }

  const showOthersBeta = betaVisible || !hasAttempt || (!!jobs[activeAttemptId] && jobs[activeAttemptId] !== "Ready")
  const workspaceScreen = (
    <main className="screen with-header workspace workspace-flow">
      <header className="workspace-video-header">
        <div className="workspace-title-row">
          <h1>{selectedGym} <span className="workspace-title-grade">{selectedRoute.grade}</span></h1>
          {hasAttempt && <button type="button" className="workspace-more" aria-label="Manage my video" onClick={() => setManageMode(manageMode ? null : "menu")}>⋯</button>}
        </div>
        <div className="workspace-info-line">{hasAttempt && <p className="workspace-attempt-date">My attempt <span aria-hidden="true">·</span> {activeAttempt?.date ?? workspaceSource.split(" · ")[0]}</p>}{hasAttempt && activeAttempt && <span className="video-status-inline" role="status"><span>{activeAttempt.status.split(" · ")[0]}</span>{(!jobs[activeAttemptId] || jobs[activeAttemptId] === "Ready") && <><span className="status-divider" aria-hidden="true">·</span><span className="video-ready"><i aria-hidden="true" />Ready</span></>}</span>}</div>
      </header>

      {hasAttempt && activeAttempt && <>
        {manageMode && <section className="video-management">
          {manageMode === "menu" && <><button className="btn btn-outline" onClick={() => setManageMode("visibility")}>Change visibility</button><button className="btn btn-outline" onClick={() => setManageMode("delete")}>Delete video</button></>}
          {manageMode === "visibility" && <><p>Who can see this video?</p><div className="privacy-options">{["Private","Public"].map(option => <button key={option} className={activeAttempt.status.startsWith(option) ? "selected" : ""} aria-pressed={activeAttempt.status.startsWith(option)} onClick={() => {setAttemptRecords(records => records.map(r => r.id === activeAttemptId ? {...r,status:option}:r));flash(`Visibility changed to ${option}`)}}>{option}</button>)}</div><button className="btn btn-text" onClick={() => setManageMode(null)}>Done</button></>}
          {manageMode === "delete" && <><strong>Delete this video?</strong><p>This removes this attempt and its comments. Other attempts remain.</p><button className="btn btn-outline" onClick={() => setManageMode(null)}>Cancel</button><button className="btn btn-solid" onClick={() => {const remaining = attemptRecords.filter(r => r.id !== activeAttemptId);setAttemptRecords(remaining);if (!remaining.some(r => r.routeId === selectedRoute.id)) setAttempts(items => items.filter(id => id !== selectedRoute.id));setComments(c => c.filter(item => item.source !== `attempt:${activeAttemptId}`));setManageMode(null);setHasAttempt(false);setJobs(j => {const next={...j};delete next[activeAttemptId];return next});go("route")}}>Delete video</button></>}
        </section>}
        {jobs[activeAttemptId] && jobs[activeAttemptId] !== "Ready" && <div className="process-status" role="status"><strong>{jobs[activeAttemptId]}</strong>{["Analyzing","Video saved"].includes(jobs[activeAttemptId]) && <p>Your video is saved. You can leave and return through My Library.</p>}{jobs[activeAttemptId] === "Analysis failed" && <><p>Your video is saved. Only the analysis failed.</p><button className="btn btn-outline" onClick={() => analyze(activeAttemptId)}>Retry analysis</button></>}</div>}
      </>}
      <section className="workspace-section video-section">
        {workspaceEntry === "upload" && !hasAttempt && uploadState !== "loading" && <div className="section-heading"><h2>Add my video</h2></div>}
        {!(workspaceEntry === "upload" && !hasAttempt) && (
          <>
            <div className="video-frame">
              <MediaVideo routeId={selectedRoute.id} seekTime={cueTime} />
              <button
                className="expand-video"
                type="button"
                onClick={() =>
                  setExpandedVideo(
                    workspaceEntry === "community"
                      ? `${selectedBeta.name} video`
                      : "My video",
                  )
                }
              >
                Expand
              </button>
            </div>
            <div className="player-controls">
              <PlaybackButton />
              <input
                aria-label="Video timeline"
                type="range"
                min="0"
                max="18"
                value={cueTime} onChange={event => setCueTime(Number(event.target.value))}
              />
              <span>00:{String(cueTime).padStart(2, "0")} / 00:18</span>
            </div>
          </>
        )}

        {workspaceEntry === "community" && (
          <div className="inline-action">
            <span>Viewing {selectedBeta.name} on this route.</span>
            <AppButton
              variant="outline"
              onClick={() => setUploadState("empty")}
            >
              Add my video
            </AppButton>
          </div>
        )}

        {uploadState !== "hidden" && uploadState !== "saved" && (
          <div className="inline-upload">
            {uploadState === "empty" && (
              <>
                <p className="upload-intro">Choose a climbing video to review.</p>
                <AppButton onClick={() => setUploadState("preview")}>
                  Upload from device
                </AppButton>
                <AppButton
                  variant="text"
                  onClick={() => {
                    if (workspaceEntry === "upload" && !hasAttempt) back()
                    else setUploadState("hidden")
                  }}
                >
                  Cancel
                </AppButton>
              </>
            )}
            {uploadState === "preview" && (
              <>
                <MediaVideo routeId={selectedRoute.id} />
                {uploadError && <p role="alert">Upload failed. Your selection is preserved. Try again.</p>}
                <fieldset className="upload-privacy">
                  <legend>Visibility</legend>
                  <div className="privacy-options">
                    {(["Private", "Public"] as const).map(option => (
                      <label key={option} className={uploadPrivacy === option ? "selected" : ""}>
                        <input type="radio" name="video-privacy" value={option} checked={uploadPrivacy === option} onChange={() => setUploadPrivacy(option)} />
                        <span>{option}</span>
                      </label>
                    ))}
                  </div>
                  {uploadPrivacy && <p>{uploadPrivacy === "Public" ? "Shared with the community." : "Only you can view it."}</p>}
                </fieldset>
                <div className="inline-buttons">
                  <AppButton
                    variant="outline"
                    onClick={() => setUploadState("empty")}
                  >
                    Cancel
                  </AppButton>
                  <button className="btn btn-solid" type="button" disabled={!uploadPrivacy} onClick={saveUploadedAttempt}>{uploadError ? "Retry upload" : "Save video"}</button>
                </div>
                <details className="demo-controls"><summary>Prototype test states</summary><select aria-label="Upload test scenario" value={demoFailure} onChange={e => setDemoFailure(e.target.value)}><option value="none">Successful upload and analysis</option><option value="upload">Upload fails</option><option value="analysis">Analysis fails after saving</option></select><p>Local prototype · nothing is published online.</p></details>
              </>
            )}
            {uploadState === "loading" && (
              <p>
                <strong>Uploading…</strong> Please keep this page open.
              </p>
            )}
          </div>
        )}
      </section>

      {(hasAttempt || workspaceEntry !== "upload") && (
        <section className="workspace-section analysis-tools">
          <div className="workspace-mode-tabs" role="tablist" aria-label="Video tools">
            <button type="button" role="tab" id="suggestions-tab" aria-controls="suggestions-panel" aria-selected={!showOthersBeta} disabled={!hasAttempt || (!!jobs[activeAttemptId] && jobs[activeAttemptId] !== "Ready")} onClick={() => {setBetaVisible(false);setSuggestionsVisible(true)}}>Suggestions</button>
            <button type="button" role="tab" id="others-tab" aria-controls="others-panel" aria-selected={showOthersBeta} onClick={() => {setBetaVisible(true);setSuggestionsVisible(false);setActiveTerm(null)}}>Community Beta</button>
          </div>
          {!showOthersBeta && hasAttempt && (!jobs[activeAttemptId] || jobs[activeAttemptId] === "Ready") && (
            <div className="suggestion-text compact-suggestions" id="suggestions-panel" role="tabpanel" aria-labelledby="suggestions-tab">
              <article className="suggestion-card"><button className="cue-link" onClick={() => setCueTime(7)}>View moment · 00:07</button><p><b>Observed:</b> Hips move away from the wall during the reach.</p><p><b>Try:</b> <button className="technical-term" onClick={() => setActiveTerm("drop knee")}>Drop knee</button></p><p><b>Why:</b> Turning the hip inward may reduce the reach distance.</p></article>
              <article className="suggestion-card"><b>Insufficient evidence · example</b><p>The foot is obscured. No foot-placement suggestion is available for this section.</p></article>
            </div>
          )}
          {showOthersBeta && (
            <div className="beta-list-simple" id="others-panel" role="tabpanel" aria-labelledby="others-tab">
              {[...similarClimbers].filter(climber => betaCards.some(card => card.id === climber.id && card.route === selectedRoute.name && card.gym === selectedGym)).sort((a,b) => profile.height && profile.wingspan ? (Math.abs(a.height - Number(profile.height)) + Math.abs(a.wingspan - Number(profile.wingspan))) - (Math.abs(b.height - Number(profile.height)) + Math.abs(b.wingspan - Number(profile.wingspan))) : 0).map((climber) => (
                <button
                  className="beta-video-card"
                  type="button"
                  key={climber.id}
                  onClick={() => {
                    setWorkspaceBetaId(climber.id)
                    setBetaOrigin("workspace")
                    resetBodyPreview()
                    go("beta")
                  }}
                >
                  <span className="beta-card-thumbnail"><MediaImage routeId={selectedRoute.id} /><span className="beta-card-duration">{climber.time}</span></span>
                  <span className="beta-card-details">
                    <b>{climber.name}</b>
                    <span className="beta-card-measurements"><span>Height <strong>{climber.height} cm</strong></span><span>Arm span <strong>{climber.wingspan} cm</strong></span></span>
                    {profile.height && profile.wingspan && <small className="beta-card-difference">Height {signedDifference(climber.height - Number(profile.height))} cm · Arm span {signedDifference(climber.wingspan - Number(profile.wingspan))} cm</small>}
                    <span className="beta-card-open">View beta <span aria-hidden="true">↗</span></span>
                  </span>
                </button>
              ))}
            </div>
          )}
        </section>
      )}
      {hasAttempt && activeAttempt?.status.startsWith("Public") && renderComments(`attempt:${activeAttemptId}`)}
    </main>
  )

  const libraryItems = useMemo(() => {
    if (libraryTab === "attempts")
      return attempts.map((id) => ({
        id,
        label: routes.find((route) => route.id === id)?.name ?? id,
        meta: `${attemptRecords.filter(record => record.routeId === id).length} attempts · ${jobs[attemptRecords.find(record => record.routeId === id)?.id ?? ""] ?? "Ready"}`,
        target: "workspace" as const,
      }))
    if (libraryTab === "saved")
      return savedBeta.map((id) => ({
        id,
        label: betaCards.find((card) => card.id === id)?.route ?? id,
        meta: "Saved community beta",
        target: "workspace" as const,
      }))
    return wantedRoutes.map((id) => ({
      id,
      label: routes.find((route) => route.id === id)?.name ?? id,
      meta: "Want to try",
      target: "route" as const,
    }))
  }, [attempts, attemptRecords, jobs, libraryTab, savedBeta, wantedRoutes])

  const libraryScreen = (
    <main className="screen with-header">
      <div className="tabs library-tabs">
        <button
          className={libraryTab === "attempts" ? "active" : ""}
          type="button"
          onClick={() => setLibraryTab("attempts")}
        >
          My Attempts
        </button>
        <button
          className={libraryTab === "saved" ? "active" : ""}
          type="button"
          onClick={() => setLibraryTab("saved")}
        >
          Saved Beta
        </button>
        <button
          className={libraryTab === "wanted" ? "active" : ""}
          type="button"
          onClick={() => setLibraryTab("wanted")}
        >
          Want to Try
        </button>
      </div>
      {libraryTab === "attempts" && <section className="library-history">
        <button type="button" className="history-toggle" aria-expanded={historyVisible} onClick={() => setHistoryVisible(!historyVisible)}><span>Attempt history <small>{attemptRecords.length}</small></span><span className="history-chevron" aria-hidden="true">{historyVisible ? "⌃" : "⌄"}</span></button>
        {historyVisible && <><div className="history-entries">{attemptRecords.map(record => {
          const route = routes.find(route => route.id === record.routeId)
          return <button key={record.id} type="button" className="history-row" onClick={() => {setSelectedRoute(route ?? routes[0]); setSelectedGym(route?.gym ?? "Gym A"); openWorkspace(`${record.date} · Attempt`, "attempt", record.id)}}>
            <span className="history-thumbnail"><MediaImage routeId={record.routeId}/><span>{record.duration}</span></span>
            <span className="history-entry-info"><span className="history-entry-title"><strong>{route?.gym}</strong><span className="history-grade">{route?.grade}</span></span><span className="history-date">{record.date}</span><span className="history-status">{record.status} · {jobs[record.id] ?? "Ready"}</span></span>
            <span className="history-entry-arrow" aria-hidden="true">›</span>
          </button>
        })}</div></>}

      </section>}
      {libraryTab !== "attempts" && <div className="library-list">
        {libraryItems.map((item) => (
          <button
            type="button"
            key={item.id}
            onClick={() => {
              if (item.target === "route") {
                openRoute(routes.find((route) => route.id === item.id))
              } else if (item.meta === "Saved community beta") {
                const savedCard = betaCards.find(card => card.id === item.id); const savedRoute = routes.find(route => route.name === savedCard?.route) ?? routes[0]; setSelectedRoute(savedRoute); setSelectedGym(savedRoute.gym)
                setWorkspaceBetaId(item.id)
                setBetaOrigin("community")
                resetBodyPreview()
                go("beta")
              } else {
                setSelectedRoute(routes.find(route => route.id === item.id) ?? routes[0]); setSelectedGym(routes.find(route => route.id === item.id)?.gym ?? "Gym A")
                openWorkspace(
                  `${item.meta} — ${item.label}`,
                  "attempt",
                  item.id,
                )
              }
            }}
          >
            <MediaImage routeId={item.target === "route" ? item.id : (routes.find(route => route.name === item.label)?.id ?? "r1")} wall={item.target === "route"} />
            <span>
              <b>{routeLabel(item.label)}</b>
              <small>{item.meta}</small>
            </span>
            <span>→</span>
          </button>
        ))}
        {libraryItems.length === 0 && (
          <div className="library-empty">
            <span className="library-empty-icon" aria-hidden="true"><svg viewBox="0 0 24 24">{libraryTab === "saved" ? <path d="M6 3h12a1 1 0 0 1 1 1v17l-7-4-7 4V4a1 1 0 0 1 1-1Z"/> : <><path d="m3 20 7-15 4 8 2-4 5 11H3Z"/><path d="m7 11 3 2 2-2"/></>}</svg></span>
            <strong>{libraryTab === "saved" ? "Keep a beta for later" : "Find your next climb"}</strong>
            <p>
              {libraryTab === "saved" ? "Save a community video to revisit it here." : "Mark a route you’d like to try. It’ll be waiting here."}
            </p>
            <AppButton
              variant="outline"
              onClick={() => go(libraryTab === "saved" ? "community" : "gyms")}
            >
              Browse {libraryTab === "saved" ? "community" : "routes"}
            </AppButton>
          </div>
        )}
      </div>}
    </main>
  )

  const screens: Record<Screen, React.ReactNode> = {
    home,
    account: accountScreen,
    profile: profileScreen,
    community: communityScreen,
    gyms: gymsScreen,
    gallery: galleryScreen,
    route: routeScreen,
    workspace: workspaceScreen,
    beta: betaDetailScreen,
    library: libraryScreen,
  }

  return (
    <div className="prototype-shell">
      <div className="phone">
        <div className="phone-content">
        {header}
        {notice && (
          <div className="toast" role="status">
            {notice}
          </div>
        )}
        {screens[screen]}
        </div>
        <nav className="bottom-nav" aria-label="Main navigation">
          {([
            {id:"home", label:"Home", path:"M3 10 12 3l9 7v11h-6v-7H9v7H3Z"},
            {id:"community", label:"Community", path:"M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M17 4a4 4 0 0 1 0 8M22 21v-2a4 4 0 0 0-3-4"},
            {id:"gyms", label:"Go Climbing", path:"m2 21 7-16 5 10 3-6 5 12ZM6 12l3 2 3-2"},
            {id:"library", label:"My Library", path:"M4 3h16v18l-8-5-8 5Z"}
          ] as const).map(tab => {const active = tab.id === screen || (tab.id === "gyms" && ["gallery","route","workspace"].includes(screen)) || (tab.id === "community" && screen === "beta"); return <button key={tab.id} type="button" aria-current={active ? "page" : undefined} onClick={() => {setHistory([]);setScreen(tab.id);setNotice("");document.querySelector(".phone-content")?.scrollTo(0,0)}}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={tab.path}/></svg><span>{tab.label}</span></button>})}
        </nav>
        {activeTerm && (
          <div className="term-sheet-backdrop" role="presentation">
            <section
              className="term-sheet"
              role="dialog"
              aria-modal="true"
              aria-labelledby="term-title"
            >
              <div className="section-heading">
                <h2 id="term-title">{activeTerm}</h2>
                <AppButton variant="text" onClick={() => setActiveTerm(null)}>
                  Close
                </AppButton>
              </div>
              <Placeholder>[Animated technique · {activeTerm}]</Placeholder>
              <p>{techniqueTerms[activeTerm].definition}</p>
              <p>
                <b>When to use it:</b> {techniqueTerms[activeTerm].use}
              </p>
            </section>
          </div>
        )}
        {expandedVideo && (
          <div
            className="modal-backdrop video-modal-backdrop"
            role="presentation"
          >
            <section
              className="video-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="expanded-video-title"
            >
              <div className="section-heading">
                <h2 id="expanded-video-title">{expandedVideo}</h2>
                <AppButton
                  variant="text"
                  onClick={() => setExpandedVideo(null)}
                >
                  Close
                </AppButton>
              </div>
              <MediaVideo routeId={selectedRoute.id} pose={expandedVideo.includes("Generated")} />
              <div className="player-controls">
                <PlaybackButton />
                <input
                  aria-label="Expanded video timeline"
                  type="range"
                  min="0"
                  max="18"
                  defaultValue="7"
                />
                <span>00:07 / 00:18</span>
              </div>
            </section>
          </div>
        )}
        {confirmBody && <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true" aria-labelledby="confirm-body-title"><h2 id="confirm-body-title">Confirm your proportions</h2><Field label="Height (cm)" value={profile.height} onChange={height => setProfile({...profile,height})}/><Field label="Arm span (cm)" value={profile.wingspan} onChange={wingspan => setProfile({...profile,wingspan})}/><p className="muted small">Preview workflow demo. Algorithm connection is pending.</p><details className="demo-controls"><summary>Prototype test states</summary><label><input type="checkbox" checked={confidenceDemo} onChange={e => setConfidenceDemo(e.target.checked)}/> Show low-confidence example</label><label><input type="checkbox" checked={bodyFailure} onChange={e => setBodyFailure(e.target.checked)}/> Simulate generation failure</label></details><button className="btn btn-solid" disabled={!(Number(profile.height)>0 && Number(profile.wingspan)>0)} onClick={startBodyPreview}>Generate preview</button><button className="btn btn-outline" onClick={() => setConfirmBody(false)}>Cancel</button></section></div>}
        {measurementPrompt && (
          <div className="modal-backdrop" role="presentation">
            <section
              className="modal measurement-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="measurement-title"
            >
              <span className="section-kicker">OPTIONAL PROFILE SETUP</span>
              <h2 id="measurement-title">Add your body information</h2>
              <p>
                This helps prioritize beta from climbers with similar
                measurements. It stays private by default.
              </p>
              <Field
                label="Name — optional"
                value={profile.name}
                onChange={(name) => setProfile({ ...profile, name })}
                placeholder="Name"
              />
              <div className="field-row">
                <Field
                  label="Height (cm)"
                  value={profile.height}
                  onChange={(height) => setProfile({ ...profile, height })}
                  placeholder="168"
                />
                <Field
                  label="Wingspan (cm)"
                  value={profile.wingspan}
                  onChange={(wingspan) => setProfile({ ...profile, wingspan })}
                  placeholder="171"
                />
              </div>
              <AppButton
                onClick={() => {
                  setMeasurementPrompt(false)
                  if (screen === "account") back()
                  if (screen === "beta") setConfirmBody(true)
                  flash("Profile information saved")
                }}
              >
                Save profile information
              </AppButton>
              <AppButton
                variant="outline"
                onClick={() => {
                  setMeasurementPrompt(false)
                  if (screen === "account") back()
                  flash("Skipped — you can add this later in Profile")
                }}
              >
                Skip for now
              </AppButton>
            </section>
          </div>
        )}
      </div>
    </div>
  )
}

export default App
