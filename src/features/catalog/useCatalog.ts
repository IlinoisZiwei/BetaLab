import { useState, useEffect, type RefObject } from "react"
import { api, ApiError, type Session, type Gym, type Route } from "../../api"

type Options = { session: Session | null; authEpoch: RefObject<number>; onExpired: () => void }

export function useCatalog({ session, authEpoch, onExpired }: Options) {
  const [catalog, setCatalog] = useState<{
    gyms: Gym[]
    routes: Route[]
  } | null>(null)
  const [catalogError, setCatalogError] = useState("")
  const [catalogLoading, setCatalogLoading] = useState(false)
  const loadCatalog = async () => {
    const epoch = authEpoch.current
    setCatalogLoading(true)
    setCatalogError("")
    try {
      const [g, r] = await Promise.all([
        api<{ items: Gym[] }>("/gyms"),
        api<{ items: Route[] }>("/routes?include_archived=true&limit=100"),
      ])
      if (epoch === authEpoch.current)
        setCatalog({ gyms: g.items, routes: r.items })
    } catch (error) {
      if (epoch !== authEpoch.current) return
      if (error instanceof ApiError && error.status === 401) {
        onExpired()
      } else setCatalogError((error as Error).message)
    } finally {
      if (epoch === authEpoch.current) setCatalogLoading(false)
    }
  }
  useEffect(() => {
    if (session) void loadCatalog()
  }, [session?.user.id])
  const catalogGyms =
    catalog?.gyms.map((g) => ({
      name: g.name,
      place: g.location_label,
      count: g.active_route_count,
    })) ?? []
  const catalogRoutes =
    catalog?.routes.map((r) => ({
      id: r.id,
      gym: catalog.gyms.find((g) => g.id === r.gym_id)?.name ?? "",
      name: r.name,
      grade: r.grade,
      version: r.set_label,
      archived: r.archived,
      showArchiveBadge: true,
    })) ?? []

  return { catalog, setCatalog, catalogError, setCatalogError, catalogLoading, loadCatalog, catalogGyms, catalogRoutes }
}
