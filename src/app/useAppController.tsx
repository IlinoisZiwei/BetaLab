import { useCatalog } from "../features/catalog/useCatalog"
import { useComments } from "../features/community/useComments"
import { useSocial } from "../features/community/useSocial"
import { useUpload } from "../features/videos/useUpload"
import { useVideoLibrary } from "../features/videos/useVideoLibrary"
import { useNavigation } from "./hooks/useNavigation"
import { useSession } from "./hooks/useSession"

import type { Task } from "../compute/results"

import { type ComputeVideo } from "../compute/CommunityCompute"

import { useMemo, useRef, useState, useEffect } from "react"
import { api, type UserVideo } from "../api"
import { Screen, LibraryTab, WorkspaceEntry, BetaOrigin, AttemptRecord, CommunityFeedVideo, routes, similarClimbers, betaCards, routeMedia } from "./shared"

// Coordinates feature hooks and cross-page transitions; page markup lives in pages/.
export function useAppController() {
  const {
    screen,
    setScreen,
    history,
    setHistory,
    notice,
    setNotice,
    go,
    back,
    flash,
  } = useNavigation()
  const [search, setSearch] = useState("")
  const [gradeFilter, setGradeFilter] = useState("All grades")
  const [communitySearch, setCommunitySearch] = useState("")
  const [communityGymFilter, setCommunityGymFilter] = useState("All gyms")
  const [communityGradeFilter, setCommunityGradeFilter] = useState("All grades")
  const [selectedGym, setSelectedGym] = useState("Movement Fishtown")
  const [selectedRoute, setSelectedRoute] = useState(routes[0])
  const [sampleAttempts, setAttemptRecords] = useState<AttemptRecord[]>([
    {
      id: "a1",
      routeId: "r1",
      date: "14 May 2025",
      duration: "0:18",
      status: "Public",
      contentUrl: undefined as string | undefined,
    },
    {
      id: "a2",
      routeId: "r1",
      date: "08 May 2025",
      duration: "0:21",
      status: "Public · Tip saved",
    },
    {
      id: "a3",
      routeId: "r1",
      date: "02 May 2025",
      duration: "0:16",
      status: "Public",
    },
  ])
  const [activeAttemptId, setActiveAttemptId] = useState("a1")
  const [manageMode, setManageMode] =
    useState<null | "menu" | "visibility" | "delete">(null)
  const [jobs, setJobs] = useState<Record<string, string>>({})
  const [libraryTab, setLibraryTab] = useState<LibraryTab>("attempts")
  const [workspaceSource, setWorkspaceSource] = useState(
    "My attempt — Corner Study",
  )
  const [workspaceEntry, setWorkspaceEntry] =
    useState<WorkspaceEntry>("attempt")
  const [workspaceBetaId, setWorkspaceBetaId] = useState("b1")
  const [betaOrigin, setBetaOrigin] = useState<BetaOrigin>("workspace")
  const [hasAttempt, setHasAttempt] = useState(true)
  const [cueTime, setCueTime] = useState(7)
  const jumpToCueTime = (time: number) => {
    const safeTime = Math.min(18, Math.max(0, Number.isFinite(time) ? time : 0))
    setCueTime(safeTime)
  }
  const [, setSuggestionsVisible] = useState(false)
  const [betaVisible, setBetaVisible] = useState(false)
  const [activeTerm, setActiveTerm] = useState<string | null>(null)
  const [expandedVideo, setExpandedVideo] = useState<string | null>(null)
  const [sourceResultTask, setSourceResultTask] = useState<Task | null>(null)
  const [analysisPendingVideoId, setAnalysisPendingVideoId] =
    useState<string | null>(null)
  const [computeVideo, setComputeVideo] = useState<ComputeVideo | null>(null)
  const [expandedCommunityDescription, setExpandedCommunityDescription] =
    useState<string | null>(null)
  const [communityVideoId, setCommunityVideoId] = useState<string | null>(null)
  const globalSwipeStart = useRef<{
    x: number
    y: number
    pointerId: number
  } | null>(null)
  const videoMutationBusy = useRef(false)
  const {
    session,
    signedIn,
    profile,
    setProfile,
    account,
    setAccount,
    accountMode,
    setAccountMode,
    authLoading,
    authBusy,
    authError,
    setAuthError,
    applySession,
    refreshSession,
    submitAccount,
    saveProfile,
    signOut,
    authEpoch,
    measurementPrompt,
    setMeasurementPrompt,
  } = useSession({
    navigation: {
      screen,
      setScreen,
      history,
      setHistory,
      notice,
      setNotice,
      go,
      back,
      flash,
    },
    onUserChange: (value) => {
      resetUpload()
      videoMutationBusy.current = false
      resetVideos()
      setAttemptRecords((records) =>
        records.filter((record) => /^a[0-9]+$/.test(record.id)),
      )
      setJobs({})
      resetSocial()
      setManageMode(null)
      setHasAttempt(false)
      setActiveAttemptId("")
      setHistory([])
      setExpandedVideo(null)
      setSourceResultTask(null)
      setAnalysisPendingVideoId(null)
      setComputeVideo(null)
      setCommunityVideoId(null)
      setCatalogError("")
      setScreen(value ? "home" : "account")
      setCatalog(null)
    },
  })
  const { catalog, setCatalog, catalogError, setCatalogError, catalogLoading, loadCatalog, catalogGyms, catalogRoutes } =
    useCatalog({ session, authEpoch, onExpired: () => {
      applySession(null); setAuthError("Your session expired. Please sign in again.")
    } })
  const {
    uploadState,
    setUploadState,
    uploadPrivacy,
    setUploadPrivacy,
    selectedUpload,
    setSelectedUpload,
    shareAsBeta,
    setShareAsBeta,
    uploadTitle,
    setUploadTitle,
    uploadDescription,
    setUploadDescription,
    selectedUploadUrl,
    setSelectedUploadUrl,
    uploadInputRef,
    uploadError,
    setUploadError,
    generationMessage,
    uploadProgress,
    uploadController,
    chooseUpload,
    saveUploadedAttempt,
    resetUpload,
  } = useUpload({
    session,
    routeId: selectedRoute.id,
    authEpoch,
    onSaved: (data) => {
      if (!session) return
      const savedEpoch = authEpoch.current
      const id = data.id as string
      setHasAttempt(true)
      setWorkspaceEntry("attempt")
      setActiveAttemptId(id)
      setWorkspaceSource(`Today · ${selectedRoute.name}`)
      syncVideo(data)
      setAnalysisPendingVideoId(id)
      setJobs((j) => ({ ...j, [id]: "Video saved" }))
      flash("Video saved successfully.")
      // Separate from upload failure handling: never undo a saved video if queuing fails.
      void api(`/tasks/upload-analysis/${id}`, {
        method: "POST",
        csrf: session.csrf_token,
      })
        .catch((error) => {
          if (savedEpoch === authEpoch.current)
            flash(
              `Video saved. Analysis was not started: ${(error as Error).message}`,
            )
        })
        .finally(() => {
          if (savedEpoch === authEpoch.current)
            setAnalysisPendingVideoId((current) =>
              current === id ? null : current,
            )
        })
    },
  })
  const {
    myVideos,
    publicVideos,
    routeBetaVideos,
    syncVideo,
    removeVideo,
    resetVideos,
    publicHasMore,
    publicLoading,
    publicError,
    loadMorePublic,
    retryPublic,
    refreshPublic,
  } = useVideoLibrary({
    session,
    screen,
    routeId: selectedRoute.id,
    onError: setCatalogError,
  })
  const expireSession = () => {
    applySession(null)
    setAuthError("Your session expired. Please sign in again.")
  }
  const {
    social,
    savedVideos,
    wantedRoutes,
    danmakuOn,
    following,
    toggleFollow,
    toggleSocial,
    toggleWanted,
    updateCommentCount,
    shareVideo,
    toggleDanmaku,
    forgetVideo,
    reset: resetSocial,
  } = useSocial({
    session,
    authEpoch,
    flash,
    onExpired: expireSession,
    visibleVideos: [...myVideos, ...publicVideos, ...routeBetaVideos],
    onOpenShared: (id, video) => {
      setCommunityVideoId(id)
      go("communityVideo")
      void refreshPublic(video ?? undefined)
    },
  })
  const { renderComments } = useComments({
    session,
    onExpired: expireSession,
    onCountChange: updateCommentCount,
  })
  const attempts = [...new Set(myVideos.map((video) => video.route_id))]
  const attemptRecords: AttemptRecord[] = [
    ...myVideos.map((video) => ({
      id: video.id,
      routeId: video.route_id,
      title: video.title,
      contentUrl: video.content_url,
      date: new Date(video.created_at).toLocaleDateString(),
      duration: `${Math.floor(video.duration_seconds / 60)}:${String(Math.floor(video.duration_seconds % 60)).padStart(2, "0")}`,
      status: video.visibility === "public" ? "Public" : "Private",
    })),
    ...sampleAttempts.filter(
      (record) => !myVideos.some((video) => video.id === record.id),
    ),
  ]
  const activeVideo = [...myVideos, ...publicVideos, ...routeBetaVideos, ...savedVideos].find(
    (video) => video.id === activeAttemptId,
  )
  const activeAttempt = activeVideo
    ? {
        id: activeVideo.id,
        routeId: activeVideo.route_id,
        title: activeVideo.title,
        contentUrl: activeVideo.content_url,
        status: activeVideo.visibility === "public" ? "Public" : "Private",
        date: new Date(activeVideo.created_at).toLocaleDateString(),
        duration: String(activeVideo.duration_seconds),
      }
    : attemptRecords.find((record) => record.id === activeAttemptId)
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
    if (entry === "attempt")
      setActiveAttemptId(
        myVideos.some(
          (video) => video.id === betaId && video.owner_id === session?.user.id,
        )
          ? betaId
          : (myVideos.find((video) => video.route_id === selectedRoute.id)
              ?.id ?? ""),
      )
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
      setSelectedUpload(null)
      setSelectedUploadUrl("")
      setShareAsBeta(false)
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


  const pageTitle: Record<Screen, string> = {
    home: "BetaLab",
    account: "Account",
    profile: "Profile",
    community: "Community",
    communityVideo: "Community",
    gyms: "Select Gym",
    gallery: selectedGym,
    route: "Route",
    workspace: "Beta Workspace",
    beta: "Community Beta",
    library: "My Library",
  }

  const communitySampleVideos: CommunityFeedVideo[] = useMemo(
    () =>
      attemptRecords
        .filter(
          (record) =>
            record.id.startsWith("a") &&
            !myVideos.some((video) => video.id === record.id),
        )
        .map((record) => {
          const [minutes, seconds] = record.duration.split(":").map(Number)
          return {
            id: `sample-${record.id}`,
            owner_id: "preset",
            route_id: record.routeId,
            visibility: "public",
            share_as_beta: false,
            original_name: `${record.title ?? `Attempt ${record.id.slice(1)}`}.mp4`,
            title: record.title ?? `Attempt ${record.id.slice(1)}`,
            description: "",
            media_type: "video/mp4",
            size_bytes: 0,
            duration_seconds: (minutes || 0) * 60 + (seconds || 0),
            created_at: new Date(record.date).toISOString(),
            content_url: routeMedia(record.routeId).video,
            username: "betalab-demo",
            display_name: "BetaLab demo",
            is_preset_sample: true,
          }
        }),
    [attemptRecords, myVideos],
  )
  const communityPresetBetaVideos: CommunityFeedVideo[] = useMemo(
    () =>
      betaCards.map((card) => {
        const climber = similarClimbers.find((item) => item.id === card.id)
        const route = routes.find(
          (item) => item.name === card.route && item.gym === card.gym,
        )
        const [minutes, seconds] = (climber?.time ?? "0:00")
          .split(":")
          .map(Number)
        return {
          id: `preset-beta-${card.id}`,
          owner_id: "preset",
          route_id: route?.id ?? "r1",
          visibility: "public",
          share_as_beta: true,
          original_name: `${card.author} beta.mp4`,
          title: `${card.author}'s beta`,
          description: climber?.bio || climber?.cue || "",
          media_type: "video/mp4",
          size_bytes: 0,
          duration_seconds: (minutes || 0) * 60 + (seconds || 0),
          created_at: new Date("2025-05-14T12:00:00Z").toISOString(),
          content_url: routeMedia(route?.id ?? "r1").video,
          username: card.author.toLowerCase().replace(/[^a-z0-9]+/g, ""),
          display_name: card.author,
          height_cm: climber?.height ?? null,
          arm_span_cm: climber?.wingspan ?? null,
          is_preset_sample: true,
          is_preset_beta: true,
        }
      }),
    [],
  )
  const communityVideos: CommunityFeedVideo[] = useMemo(
    () =>
      [
        ...publicVideos,
        ...communitySampleVideos,
        ...communityPresetBetaVideos,
      ].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)),
    [publicVideos, communitySampleVideos, communityPresetBetaVideos],
  )
  const communityResults = communityVideos.filter((video) => {
    const route =
      catalogRoutes.find((item) => item.id === video.route_id) ??
      routes.find((item) => item.id === video.route_id)
    const term = communitySearch.trim().toLowerCase()
    return (
      (!term ||
        [
          video.title,
          video.display_name,
          video.username,
          route?.gym,
          route?.name,
          route?.grade,
        ].some((value) => value?.toLowerCase().includes(term))) &&
      (communityGymFilter === "All gyms" ||
        route?.gym === communityGymFilter) &&
      (communityGradeFilter === "All grades" ||
        route?.grade === communityGradeFilter)
    )
  })

  useEffect(() => {
    if (screen !== "communityVideo" || !communityVideoId) return
    requestAnimationFrame(() =>
      document
        .getElementById(`community-video-${communityVideoId}`)
        ?.scrollIntoView({ block: "start" }),
    )
  }, [screen, communityVideoId, communityVideos])

  const gymResults = catalogGyms.filter((gym) =>
    `${gym.name} ${gym.place}`
      .toLowerCase()
      .includes(search.trim().toLowerCase()),
  )

  const routeAttempts = [
    ...myVideos
      .filter(
        (video) =>
          video.route_id === selectedRoute.id &&
          video.owner_id === session?.user.id,
      )
      .map((video) => ({
        id: video.id,
        routeId: video.route_id,
        date: new Date(video.created_at).toLocaleDateString(),
        duration: `${Math.floor(video.duration_seconds / 60)}:${String(Math.floor(video.duration_seconds % 60)).padStart(2, "0")}`,
        status: video.visibility === "public" ? "Public" : "Private",
        contentUrl: video.content_url,
        title: video.title,
        sourceUrl: video.content_url,
      })),
  ]

  const selectedBeta =
    similarClimbers.find((climber) => climber.id === workspaceBetaId) ??
    similarClimbers[0]

  const changeVideo = async (
    visibility: "private" | "public",
    share: boolean,
  ) => {
    if (
      !session ||
      activeVideo?.owner_id !== session.user.id ||
      videoMutationBusy.current
    )
      return
    videoMutationBusy.current = true
    const epoch = authEpoch.current
    try {
      const video = await api<UserVideo>(`/videos/${activeAttemptId}`, {
        method: "PATCH",
        csrf: session.csrf_token,
        body: { visibility, share_as_beta: share },
      })
      if (epoch === authEpoch.current) {
        syncVideo(video)
        flash("Video sharing updated")
      }
    } catch (error) {
      if (epoch === authEpoch.current) flash((error as Error).message)
    } finally {
      videoMutationBusy.current = false
    }
  }
  const deleteActiveVideo = async () => {
    if (
      !session ||
      activeVideo?.owner_id !== session.user.id ||
      videoMutationBusy.current
    )
      return
    videoMutationBusy.current = true
    const id = activeAttemptId,
      epoch = authEpoch.current
    try {
      await api<void>(`/videos/${id}`, {
        method: "DELETE",
        csrf: session.csrf_token,
      })
      if (epoch !== authEpoch.current) return
      removeVideo(id)
      setAttemptRecords((items) => items.filter((v) => v.id !== id))
      forgetVideo(id)
      setJobs((items) => {
        const next = { ...items }
        delete next[id]
        return next
      })
      setManageMode(null)
      setHasAttempt(false)
      setActiveAttemptId("")
      go("route")
      flash("Video deleted")
    } catch (error) {
      if (epoch === authEpoch.current) flash((error as Error).message)
    } finally {
      videoMutationBusy.current = false
    }
  }
  const showOthersBeta =
    betaVisible || activeVideo?.owner_id !== session?.user.id || !hasAttempt
  // Another climber's uploaded video, opened from the route list, Community or Saved.
  const communityBetaVideo = [...routeBetaVideos, ...savedVideos, ...publicVideos].find(
    (video) => video.id === activeAttemptId,
  )
  const isOwnUploadedVideo = myVideos.some(
    (video) => video.id === activeAttemptId,
  )
  const isPresetSample = !isOwnUploadedVideo && !communityBetaVideo

  const libraryItems = useMemo(() => {
    if (libraryTab === "attempts")
      return myVideos.map((video) => ({
        id: video.id,
        label: video.title,
        meta: `${routes.find((route) => route.id === video.route_id)?.name ?? video.route_id} · ${
          video.visibility === "public" ? "Public" : "Private"
        }`,
        target: "video" as const,
        routeId: video.route_id,
      }))
    if (libraryTab === "saved")
      return savedVideos.map((video) => ({
        id: video.id,
        label: video.title,
        meta: `Saved · ${video.display_name || video.username || "Community member"}`,
        target: "saved" as const,
        routeId: video.route_id,
        contentUrl: video.content_url,
      }))
    return wantedRoutes.map((id) => ({
      id,
      label: routes.find((route) => route.id === id)?.name ?? id,
      meta: "Want to try",
      target: "route" as const,
    }))
  }, [
    attempts,
    attemptRecords,
    jobs,
    libraryTab,
    savedVideos,
    wantedRoutes,
    myVideos,
  ])
  return {
    pages: {
      header: { screen, back, pageTitle },
      home: { signedIn, go, setAccountMode },
      accountScreen: { accountMode, authError, setAccountMode, account, setAccount, authBusy, authLoading, submitAccount },
      profileScreen: { session, authError, profile, setProfile, authBusy, saveProfile, back, signOut },
      communityScreen: {
        communitySearch, setCommunitySearch, communityGymFilter, setCommunityGymFilter,
        catalogGyms, communityGradeFilter, setCommunityGradeFilter, catalogRoutes,
        communityResults, setCommunityVideoId, setExpandedCommunityDescription, go,
        communityVideos, publicHasMore, publicLoading, publicError, loadMorePublic, retryPublic,
      },
      communityVideoScreen: {
        communityVideos, communityVideoId, catalogRoutes, expandedCommunityDescription,
        back, social, toggleSocial, shareVideo, danmakuOn, toggleDanmaku,
        session, expireSession, updateCommentCount, setComputeVideo, setExpandedCommunityDescription,
        following, toggleFollow,
      },
      gymsScreen: { search, setSearch, gymResults, setSelectedGym, go },
      galleryScreen: { selectedGym, catalogRoutes, gradeFilter, setGradeFilter, wantedRoutes, openRoute, catalog, toggleWanted },
      routeScreen: { selectedGym, selectedRoute, openWorkspace, routeAttempts },
      workspaceScreen: {
        selectedGym, selectedRoute, hasAttempt, isOwnUploadedVideo,
        setManageMode, manageMode, isPresetSample, activeAttempt,
        workspaceSource, jobs, activeAttemptId, workspaceEntry,
        communityBetaVideo, changeVideo, activeVideo, myVideos,
        deleteActiveVideo, session, setSourceResultTask, analysisPendingVideoId,
        setJobs, setComputeVideo, uploadState, cueTime,
        jumpToCueTime, selectedBeta, setUploadState, uploadInputRef,
        chooseUpload, back, selectedUploadUrl, selectedUpload,
        uploadError, generationMessage, uploadTitle, setUploadTitle,
        uploadDescription, setUploadDescription, uploadPrivacy, setUploadPrivacy,
        setShareAsBeta, shareAsBeta, saveUploadedAttempt, uploadProgress,
        uploadController, showOthersBeta, setBetaVisible, setSuggestionsVisible,
        setActiveTerm, sourceResultTask, routeBetaVideos, setAttemptRecords,
        setActiveAttemptId, setHasAttempt, setWorkspaceEntry, setWorkspaceSource,
        profile, setWorkspaceBetaId, setBetaOrigin, go,
        renderComments,
      },
      betaDetailScreen: {
        selectedBeta, betaOrigin, social, workspaceBetaId, toggleSocial,
        selectedGym, selectedRoute, setComputeVideo, renderComments,
      },
      libraryScreen: {
        libraryTab, setLibraryTab, catalogGyms, myVideos,
        catalogRoutes, setSelectedRoute, setSelectedGym, setActiveAttemptId,
        setHasAttempt, setWorkspaceEntry, setWorkspaceSource, go,
        libraryItems, openRoute, savedVideos,
      },
    },
    shell: {
      globalSwipeStart, history, back, session,
      computeVideo, setComputeVideo, screen, go,
      notice, signedIn, authLoading, authError,
      catalogLoading, catalogError, loadCatalog, refreshSession,
      setHistory, setScreen, setNotice, activeTerm,
      setActiveTerm, expandedVideo, setExpandedVideo, selectedRoute,
      cueTime, jumpToCueTime, measurementPrompt, profile,
      setProfile, authBusy, saveProfile, setMeasurementPrompt,
      flash,
    },
  }
}

export type AppController = ReturnType<typeof useAppController>
