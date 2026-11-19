import { useRef, useState, useEffect } from "react"
import { api, ApiError, type Session } from "../../api"
import type { useNavigation } from "./useNavigation"

type Options = {
  navigation: ReturnType<typeof useNavigation>
  onUserChange: (value: Session | null) => void
}
export function useSession({ navigation, onUserChange }: Options) {
  const { go, flash, setHistory, setScreen } = navigation
  const [measurementPrompt, setMeasurementPrompt] = useState(false)
  const [profile, setProfile] = useState({
    name: "",
    height: "",
    wingspan: "",
  })
  const [account, setAccount] = useState({ email: "", password: "" })
  const [accountMode, setAccountMode] = useState<"signin" | "signup">("signin")

  const [authLoading, setAuthLoading] = useState(true)
  const [authBusy, setAuthBusy] = useState(false)
  const [authError, setAuthError] = useState("")
  const [session, setSession] = useState<Session | null>(null)
  const authEpoch = useRef(0)
  const sessionUserId = useRef<string | null>(null)
  const applySession = (value: Session | null) => {
    const changed = sessionUserId.current !== (value?.user.id ?? null)
    sessionUserId.current = value?.user.id ?? null
    if (changed) {
      authEpoch.current++
      onUserChange(value)
    }
    setSession(value)
    setProfile(
      value
        ? {
            name: value.user.display_name,
            height: value.user.height_cm?.toString() ?? "",
            wingspan: value.user.arm_span_cm?.toString() ?? "",
          }
        : { name: "", height: "", wingspan: "" },
    )
    setAccount({ email: value?.user.username ?? "", password: "" })
  }
  const refreshSession = async () => {
    setAuthLoading(true)
    setAuthError("")
    try {
      applySession(await api<Session>("/auth/me"))
    } catch (error) {
      applySession(null)
      if (!(error instanceof ApiError && error.status === 401))
        setAuthError((error as Error).message)
    } finally {
      setAuthLoading(false)
    }
  }
  useEffect(() => {
    void refreshSession()
  }, [])
  const submitAccount = async () => {
    setAuthBusy(true)
    setAuthError("")
    try {
      const value = await api<Session>(
        `/auth/${accountMode === "signup" ? "register" : "login"}`,
        {
          method: "POST",
          body: { username: account.email.trim(), password: account.password },
        },
      )
      authEpoch.current++
      applySession(value)
      setHistory([])
      setScreen("home")
      if (accountMode === "signup") setMeasurementPrompt(true)
      else flash("Signed in")
    } catch (error) {
      setAuthError((error as Error).message)
    } finally {
      setAuthBusy(false)
    }
  }
  const saveProfile = async () => {
    if (!session) {
      setAccountMode("signin")
      go("account")
      return false
    }
    if (
      (profile.height.trim() && !Number.isFinite(Number(profile.height))) ||
      (profile.wingspan.trim() && !Number.isFinite(Number(profile.wingspan)))
    ) {
      setAuthError("Please enter valid numbers for your measurements.")
      return false
    }
    setAuthBusy(true)
    setAuthError("")
    try {
      const result = await api<{ user: Session["user"] }>("/profile", {
        method: "PUT",
        csrf: session.csrf_token,
        body: {
          display_name: profile.name.trim(),
          height_cm: profile.height.trim() ? Number(profile.height) : null,
          arm_span_cm: profile.wingspan.trim()
            ? Number(profile.wingspan)
            : null,
        },
      })
      setSession({ ...session, user: result.user })
      flash("Profile saved")
      return true
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        authEpoch.current++
        applySession(null)
      }
      setAuthError((error as Error).message)
      return false
    } finally {
      setAuthBusy(false)
    }
  }
  const signOut = async () => {
    if (!session) return
    setAuthBusy(true)
    setAuthError("")
    try {
      await api<void>("/auth/logout", {
        method: "POST",
        csrf: session.csrf_token,
      })
      authEpoch.current++
      applySession(null)
      setMeasurementPrompt(false)
      setAccountMode("signin")
      go("account")
      flash("Signed out")
    } catch (error) {
      setAuthError((error as Error).message)
    } finally {
      setAuthBusy(false)
    }
  }
  return {
    session,
    signedIn: !!session,
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
  }
}
