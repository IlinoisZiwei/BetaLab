import movementRoutes from "../../data/movementRoutes.json"

import { MediaImage } from "../shared"
import type { AppController } from "../useAppController"

type Props = AppController["pages"]["gymsScreen"]

export function GymsPage({
  search,
  setSearch,
  gymResults,
  setSelectedGym,
  go,
}: Props) {
  return (
    <main className="screen with-header gym-selection">
      <header className="gym-selection-intro">
        <h1>Where to climb?</h1>
      </header>
      <div className="gym-search">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="10.5" cy="10.5" r="6.5" />
          <path d="m16 16 4.5 4.5" />
        </svg>
        <input
          aria-label="Search gyms by name or area"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by name or area"
        />
        {search && (
          <button
            type="button"
            aria-label="Clear gym search"
            onClick={() => setSearch("")}
          >
            ×
          </button>
        )}
      </div>
      <div className="gym-list-heading">
        <h2>{search.trim() ? "Search results" : "Explore gyms"}</h2>
        <span>
          {gymResults.length} {gymResults.length === 1 ? "gym" : "gyms"}
        </span>
      </div>
      <div className="card-list gym-selection-list">
        {gymResults.map((gym) => (
          <button
            className="gym-card"
            type="button"
            key={gym.name}
            onClick={() => {
              setSelectedGym(gym.name)
              go("gallery")
            }}
          >
            <span className="gym-cover">
              {gym.name === "Movement Fishtown" ? (
                <MediaImage routeId={movementRoutes[0].id} wall />
              ) : (
                <span className="gym-cover-placeholder">
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="m3 20 7-15 4 8 2-4 5 11H3Z" />
                    <path d="m7 11 3 2 2-2" />
                  </svg>
                  <span>No photo yet</span>
                </span>
              )}
            </span>
            <span className="gym-card-info">
              <b>{gym.name}</b>
              <span className="gym-area">{gym.place}</span>
              <span
                className={`gym-route-count${
                  gym.count === 0 ? " is-empty" : ""
                }`}
              >
                {gym.count > 0 ? `${gym.count} active routes` : "No routes yet"}
              </span>
            </span>
            <span className="gym-card-chevron" aria-hidden="true">
              ›
            </span>
          </button>
        ))}
      </div>
      {gymResults.length === 0 && (
        <div className="gym-search-empty">
          <strong>No gyms found</strong>
          <p>Try a different name or area.</p>
        </div>
      )}
    </main>
  )
}
