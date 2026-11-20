import { routes, SelectField, routeLabel, MediaImage } from "../shared"
import type { AppController } from "../useAppController"

type Props = AppController["pages"]["galleryScreen"]

export function GalleryPage({
  selectedGym,
  catalogRoutes,
  gradeFilter,
  setGradeFilter,
  wantedRoutes,
  openRoute,
  catalog,
  toggleWanted,
}: Props) {
  return (
    <main className="screen with-header route-gallery-page">
      <header className="route-gallery-intro">
        <h1>{selectedGym}</h1>
        <p>
          {
            catalogRoutes.filter(
              (route) => route.id !== "r2" && route.gym === selectedGym,
            ).length
          }{" "}
          routes · Select a route to see the full wall
        </p>
        <div className="gallery-tools">
          <SelectField
            label="Grade"
            value={gradeFilter}
            onChange={setGradeFilter}
          >
            <option>All grades</option>
            {[
              ...new Set(
                catalogRoutes
                  .filter(
                    (route) => route.id !== "r2" && route.gym === selectedGym,
                  )
                  .map((route) => route.grade),
              ),
            ]
              .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
              .map((grade) => (
                <option key={grade}>{grade}</option>
              ))}
          </SelectField>
        </div>
      </header>
      {wantedRoutes.some(
        (id) => routes.find((route) => route.id === id)?.gym === selectedGym,
      ) && (
        <section className="marked-strip">
          <div className="section-heading">
            <h2>Marked routes</h2>
            <span>
              {
                wantedRoutes.filter(
                  (id) =>
                    routes.find((route) => route.id === id)?.gym ===
                    selectedGym,
                ).length
              }
            </span>
          </div>
          <div>
            {wantedRoutes
              .filter(
                (id) =>
                  routes.find((route) => route.id === id)?.gym === selectedGym,
              )
              .map((id) => (
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

      {catalog && !catalogRoutes.some((r) => r.gym === selectedGym) && (
        <div className="empty-state">
          <strong>No route footage yet</strong>
          <p>
            We are collecting routes for this gym. Browse Movement Fishtown for
            the available samples.
          </p>
        </div>
      )}
      <div className="card-list route-list">
        {catalogRoutes
          .filter(
            (route) =>
              route.id !== "r2" &&
              route.gym === selectedGym &&
              (gradeFilter === "All grades" || route.grade === gradeFilter),
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
                  <b>{route.name}</b>
                  <span className="gallery-route-meta">
                    <span className="gallery-grade">{route.grade}</span>
                  </span>
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
                onClick={() => void toggleWanted(route.id)}
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
}
