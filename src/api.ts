export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message) }
}

export async function api<T>(path: string, options: {method?: string; body?: unknown; csrf?: string; headers?: Record<string, string>; signal?: AbortSignal} = {}): Promise<T> {
  const multipart = options.body instanceof FormData
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      method: options.method ?? "GET",
      credentials: "same-origin",
      signal: options.signal,
      headers: {
        ...options.headers,
        ...(options.body !== undefined && !multipart ? {"Content-Type": "application/json"} : {}),
        ...(options.csrf ? {"X-CSRF-Token": options.csrf} : {}),
      },
      ...(options.body !== undefined ? {body: multipart ? options.body as FormData : JSON.stringify(options.body)} : {}),
    })
  } catch { throw new ApiError(0, "Cannot connect. Check your connection and try again.") }
  if (response.status === 204) return undefined as T
  const data = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(response.status, data?.error?.message ?? "Service unavailable. Please try again.")
  if (!data) throw new ApiError(0, "Unexpected response. Please check that the API is running.")
  return data as T
}

export type User = {bio?: string; measurements_visible?: boolean; library_visible?: boolean; likes_visible?: boolean; saves_visible?: boolean; skeletons_visible?: boolean; account_visibility?: "private" | "public"; calendar_visible?: boolean; id: string; username: string; display_name: string; height_cm: number | null; arm_span_cm: number | null}
export type Session = {user: User; csrf_token: string}
export type Gym = {id: string; name: string; location_label: string; active_route_count: number}
export type Route = {id: string; gym_id: string; name: string; grade: string; set_label: string; archived: boolean}
export type UserVideo = {id: string; owner_id: string; route_id: string; visibility: "private" | "public"; share_as_beta: boolean; original_name: string; title: string; description: string; media_type: string; size_bytes: number; duration_seconds: number; created_at: string; content_url: string; username?: string; display_name?: string; height_cm?: number | null; arm_span_cm?: number | null}

export type VideoUpdate = Pick<UserVideo, "title" | "description" | "visibility" | "share_as_beta">
