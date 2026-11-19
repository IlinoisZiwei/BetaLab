import { CommunityCompute } from "./compute/CommunityCompute"

import { Screen, techniqueTerms, AppButton, Field, MediaVideo, Placeholder, PlaybackButton } from "./app/shared"
import { useAppController } from "./app/useAppController"
import { PageHeader } from "./app/pages/PageHeader"
import { HomePage } from "./app/pages/HomePage"
import { AccountPage } from "./app/pages/AccountPage"
import { ProfilePage } from "./app/pages/ProfilePage"
import { CommunityPage } from "./app/pages/CommunityPage"
import { CommunityVideoPage } from "./app/pages/CommunityVideoPage"
import { GymsPage } from "./app/pages/GymsPage"
import { GalleryPage } from "./app/pages/GalleryPage"
import { RoutePage } from "./app/pages/RoutePage"
import { BetaPage } from "./app/pages/BetaPage"
import { WorkspacePage } from "./app/pages/WorkspacePage"
import { LibraryPage } from "./app/pages/LibraryPage"

function App() {
  const { pages, shell } = useAppController()
  const {
    globalSwipeStart, history, back, session,
    computeVideo, setComputeVideo, screen, go,
    notice, signedIn, authLoading, authError,
    catalogLoading, catalogError, loadCatalog, refreshSession,
    setHistory, setScreen, setNotice, activeTerm,
    setActiveTerm, expandedVideo, setExpandedVideo, selectedRoute,
    cueTime, jumpToCueTime, measurementPrompt, profile,
    setProfile, authBusy, saveProfile, setMeasurementPrompt,
    flash,
  } = shell
  const header = <PageHeader {...pages.header} />
  const home = <HomePage {...pages.home} />
  const accountScreen = <AccountPage {...pages.accountScreen} />
  const profileScreen = <ProfilePage {...pages.profileScreen} />
  const communityScreen = <CommunityPage {...pages.communityScreen} />
  const communityVideoScreen = <CommunityVideoPage {...pages.communityVideoScreen} />
  const gymsScreen = <GymsPage {...pages.gymsScreen} />
  const galleryScreen = <GalleryPage {...pages.galleryScreen} />
  const routeScreen = <RoutePage {...pages.routeScreen} />
  const betaDetailScreen = <BetaPage {...pages.betaDetailScreen} />
  const workspaceScreen = <WorkspacePage {...pages.workspaceScreen} />
  const screens: Record<Screen, React.ReactNode> = {
    home,
    account: accountScreen,
    profile: profileScreen,
    community: communityScreen,
    communityVideo: communityVideoScreen,
    gyms: gymsScreen,
    gallery: galleryScreen,
    route: routeScreen,
    workspace: workspaceScreen,
    beta: betaDetailScreen,
    library: null,
  }
  return (
    <div className="prototype-shell">
      <div className="phone">
        <div
          className="phone-content"
          onPointerDown={(event) => {
            if (
              event.pointerType !== "mouse" ||
              event.button !== 0 ||
              (event.target as HTMLElement).closest(
                "button,a,input,textarea,select,video,summary",
              )
            )
              return
            globalSwipeStart.current = {
              x: event.clientX,
              y: event.clientY,
              pointerId: event.pointerId,
            }
            event.currentTarget.setPointerCapture(event.pointerId)
          }}
          onPointerUp={(event) => {
            if (event.pointerType !== "mouse") return
            const start = globalSwipeStart.current
            globalSwipeStart.current = null
            if (!start) return
            const dx = event.clientX - start.x,
              dy = event.clientY - start.y
            if (
              dx < -64 &&
              Math.abs(dx) > Math.abs(dy) * 1.5 &&
              history.length > 0
            ) {
              event.preventDefault()
              back()
            }
          }}
        >
          {header}
          {session && (
            <CommunityCompute
              key={session.user.id}
              session={session}
              source={computeVideo}
              closeSource={() => setComputeVideo(null)}
              library={screen === "library"}
              renderLibrary={(content) => <LibraryPage {...pages.libraryScreen} computeContent={content} />}
              openLibrary={() => {
                if (screen !== "library") go("library")
                requestAnimationFrame(() =>
                  document.querySelector(".phone-content")?.scrollTo(0, 0),
                )
              }}
            />
          )}
          {notice && (
            <div className="toast" role="status">
              {notice}
            </div>
          )}
          {!signedIn && !authLoading && (
            <>
              <header className="topbar auth-topbar">
                <span className="header-spacer" aria-hidden="true" />
                <strong>BetaLab</strong>
                <span className="header-spacer" aria-hidden="true" />
              </header>
              {accountScreen}
            </>
          )}
          {(authLoading ||
            (signedIn && authError) ||
            (signedIn &&
              ["gyms", "gallery"].includes(screen) &&
              (catalogLoading || catalogError))) && (
            <div className="process-status" role="status">
              {authLoading
                ? "Restoring session…"
                : authError ||
                  (catalogLoading ? "Loading gyms and routes…" : catalogError)}
              {!authLoading && authError && (
                <button
                  type="button"
                  onClick={() =>
                    signedIn ? void loadCatalog() : void refreshSession()
                  }
                >
                  Retry connection
                </button>
              )}
              {catalogError && (
                <button type="button" onClick={() => void loadCatalog()}>
                  Retry loading
                </button>
              )}
            </div>
          )}
          {signedIn && screens[screen]}
        </div>
        {signedIn && screen !== "home" && screen !== "communityVideo" && (
          <nav className="bottom-nav" aria-label="Main navigation">
            {([
              {
                id: "home",
                label: "Home",
                path: "M3 10 12 3l9 7v11h-6v-7H9v7H3Z",
              },
              {
                id: "community",
                label: "Community",
                path: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M17 4a4 4 0 0 1 0 8M22 21v-2a4 4 0 0 0-3-4",
              },
              {
                id: "gyms",
                label: "Go Climbing",
                path: "m2 21 7-16 5 10 3-6 5 12ZM6 12l3 2 3-2",
              },
              {
                id: "library",
                label: "My Library",
                path: "M4 3h16v18l-8-5-8 5Z",
              },
            ] as const).map((tab) => {
              const active =
                tab.id === screen ||
                (tab.id === "gyms" &&
                  ["gallery", "route", "workspace"].includes(screen)) ||
                (tab.id === "community" && screen === "beta")
              return (
                <button
                  key={tab.id}
                  type="button"
                  aria-current={active ? "page" : undefined}
                  onClick={() => {
                    if (tab.id !== screen) {
                      setHistory((items) => [...items, screen])
                      setScreen(tab.id)
                    }
                    setNotice("")
                    document.querySelector(".phone-content")?.scrollTo(0, 0)
                  }}
                >
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.7"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <path d={tab.path} />
                  </svg>
                  <span>{tab.label}</span>
                </button>
              )
            })}
          </nav>
        )}
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
              <MediaVideo
                routeId={selectedRoute.id}
                pose={expandedVideo.includes("Generated")}
                seekTime={cueTime}
              />
              <div className="player-controls">
                <PlaybackButton />
                <input
                  aria-label="Expanded video timeline"
                  type="range"
                  min="0"
                  max="18"
                  value={cueTime}
                  onChange={(event) =>
                    jumpToCueTime(Number(event.target.value))
                  }
                />
                <span>
                  00:{String(Math.floor(cueTime)).padStart(2, "0")} / 00:18
                </span>
              </div>
            </section>
          </div>
        )}
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
                disabled={authBusy}
                onClick={async () => {
                  if (!(await saveProfile())) return
                  setMeasurementPrompt(false)
                  setScreen("home")
                  setHistory([])
                  flash("Profile saved")
                }}
              >
                Save and continue
              </AppButton>
              <AppButton
                variant="outline"
                onClick={() => {
                  setMeasurementPrompt(false)
                  setScreen("home")
                  setHistory([])
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
