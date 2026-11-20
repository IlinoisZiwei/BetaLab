import { mediaPath } from "../shared"
import type { AppController } from "../useAppController"

type Props = AppController["pages"]["home"]

export function HomePage({ signedIn, go, setAccountMode }: Props) {
  return (
    <main
      className="screen home-screen home-redesign"
      style={{
        backgroundImage: `linear-gradient(180deg, rgba(225,240,253,.38) 0%, rgba(226,240,252,.18) 29%, rgba(235,245,253,.76) 52%, rgba(235,245,253,.48) 65%, rgba(232,244,254,.46) 84%, rgba(220,238,253,.40) 100%), url("${mediaPath("home-climbing-wall.png")}")`,
      }}
    >
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

      </header>
      <div className="home-editorial">
        <span className="home-eyebrow">YOUR NEXT MOVE STARTS HERE</span>
        <h2>
          Find your
          <br />
          next <span>move.</span>
        </h2>
        <p>
          A new route. A different beta.
          <br />
          Something that works for you.
        </p>
      </div>
      <nav className="home-entry-grid" aria-label="Primary">
        <button
          type="button"
          className="home-climb-entry"
          onClick={() => go("gyms")}
        >
          <span className="home-entry-icon">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="m2 21 7-16 5 10 3-6 5 12ZM6 12l3 2 3-2" />
            </svg>
          </span>
          <span className="home-entry-copy">
            <strong>Go Climbing</strong>
            <small>Find a gym. Pick your route.</small>
          </span>
        </button>
        <button
          type="button"
          className="home-secondary-entry"
          onClick={() => go("community")}
        >
          <span className="home-secondary-top">
            <span className="home-entry-icon">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M17 4a4 4 0 0 1 0 8M22 21v-2a4 4 0 0 0-3-4" />
              </svg>
            </span>
          </span>
          <strong>Community</strong>
          <small>See another way up.</small>
        </button>
        <button
          type="button"
          className="home-secondary-entry home-library-entry"
          onClick={() => go("library")}
        >
          <span className="home-secondary-top">
            <span className="home-entry-icon">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M5 3h14v18l-7-4-7 4Z" />
              </svg>
            </span>
          </span>
          <strong>My Page</strong>
          <small>Your climbs, collected.</small>
        </button>
      </nav>
    </main>
  )
}
