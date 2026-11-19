import type { UserVideo } from "../api"

export type Screen = "home" | "account" | "profile" | "community" | "communityVideo" | "gyms" | "gallery" | "route" | "workspace" | "beta" | "library"

export type LibraryTab = "attempts" | "saved" | "wanted"

export type WorkspaceEntry = "attempt" | "upload" | "community"

export type BetaOrigin = "community" | "workspace"

export type AttemptRecord = {
  id: string
  routeId: string
  date: string
  duration: string
  status: string
  contentUrl?: string
  title?: string
}

export type CommunityFeedVideo = UserVideo & {
  is_preset_sample?: boolean
  is_preset_beta?: boolean
}

export type TechniqueTerm = { definition: string } & { use: string }
