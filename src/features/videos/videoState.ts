import type { UserVideo } from "../../api"

export type VideoLists = {
  owned: UserVideo[]
  public: UserVideo[]
  beta: UserVideo[]
}
export const emptyVideos = (): VideoLists => ({
  owned: [],
  public: [],
  beta: [],
})
export type VideoAction = {
  type: "replace"
  list: keyof VideoLists
  videos: UserVideo[]
} | {
  // Next page of a paged list; ids already present are skipped.
  type: "append"
  list: keyof VideoLists
  videos: UserVideo[]
} | { type: "upsert"; video: UserVideo; routeId: string } | {
  type: "remove"
  id: string
} | { type: "reset" }

// One mutation updates every visible collection atomically; fetches retain their query scope.
export function videoReducer(
  state: VideoLists,
  action: VideoAction,
): VideoLists {
  if (action.type === "reset") return emptyVideos()
  if (action.type === "replace")
    return { ...state, [action.list]: action.videos }
  if (action.type === "append") {
    const current = state[action.list]
    return { ...state, [action.list]: [...current, ...action.videos.filter((video) => !current.some((item) => item.id === video.id))] }
  }
  const id = action.type === "remove" ? action.id : action.video.id
  const without = (items: UserVideo[]) => items.filter((item) => item.id !== id)
  if (action.type === "remove")
    return {
      owned: without(state.owned),
      public: without(state.public),
      beta: without(state.beta),
    }
  const video = action.video
  return {
    owned: [video, ...without(state.owned)],
    public:
      video.visibility === "public"
        ? [video, ...without(state.public)]
        : without(state.public),
    beta:
      video.visibility === "public" &&
      video.share_as_beta &&
      video.route_id === action.routeId
        ? [video, ...without(state.beta)]
        : without(state.beta),
  }
}
