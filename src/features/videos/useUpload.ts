import { useRef, useState, type RefObject } from "react"
import type { Session, UserVideo } from "../../api"

type Options = {
  session: Session | null
  routeId: string
  authEpoch: RefObject<number>
  onSaved: (video: UserVideo) => void
}

export function useUpload({ session, routeId, authEpoch, onSaved }: Options) {
  const [uploadState, setUploadState] =
    useState<"hidden" | "empty" | "preview" | "loading" | "saved">("hidden")
  const [uploadPrivacy, setUploadPrivacy] =
    useState<"Private" | "Public" | null>(null)
  const [selectedUpload, setSelectedUpload] = useState<File | null>(null)
  const [shareAsBeta, setShareAsBeta] = useState(false)
  const [uploadTitle, setUploadTitle] = useState("")
  const [uploadDescription, setUploadDescription] = useState("")
  const [selectedUploadUrl, setSelectedUploadUrl] = useState("")
  const uploadInputRef = useRef<HTMLInputElement>(null)
  const [uploadError, setUploadError] = useState(false)
  const [generationMessage, setGenerationMessage] = useState("")
  const [uploadProgress, setUploadProgress] = useState(0)
  const uploadBusy = useRef(false)
  const uploadController = useRef<AbortController | null>(null)
  const chooseUpload = (file?: File) => {
    if (!file) return
    const extension = file.name.toLowerCase().split(".").pop()
    if (
      !(extension === "mp4" || extension === "mov") ||
      (file.type && !["video/mp4", "video/quicktime"].includes(file.type))
    ) {
      setUploadError(true)
      setGenerationMessage("Choose a valid MP4 or MOV video.")
      return
    }
    if (file.size > 200 * 1024 * 1024) {
      setUploadError(true)
      setGenerationMessage("Video must be 200 MB or smaller.")
      return
    }
    if (selectedUploadUrl) URL.revokeObjectURL(selectedUploadUrl)
    const url = URL.createObjectURL(file)
    setSelectedUpload(file)
    setSelectedUploadUrl(url)
    setUploadError(false)
    setUploadState("preview")
  }
  const saveUploadedAttempt = async () => {
    if (!uploadPrivacy || !selectedUpload || !session || uploadBusy.current)
      return
    uploadBusy.current = true
    const epoch = authEpoch.current
    const controller = new AbortController()
    uploadController.current = controller
    setUploadError(false)
    setUploadState("loading")
    setUploadProgress(0)
    try {
      const form = new FormData()
      form.append("route_id", routeId)
      form.append("visibility", uploadPrivacy.toLowerCase())
      form.append(
        "share_as_beta",
        String(uploadPrivacy === "Public" && shareAsBeta),
      )
      form.append("title", uploadTitle)
      form.append("description", uploadDescription)
      form.append("video", selectedUpload)
      const data = await new Promise<UserVideo>((resolve, reject) => {
        const request = new XMLHttpRequest()
        request.open("POST", "/api/videos")
        request.setRequestHeader("X-CSRF-Token", session.csrf_token)
        request.upload.onprogress = (event) => {
          if (event.lengthComputable && epoch === authEpoch.current)
            setUploadProgress(Math.round((event.loaded / event.total) * 100))
        }
        const abort = () => request.abort()
        controller.signal.addEventListener("abort", abort, { once: true })
        const cleanup = () =>
          controller.signal.removeEventListener("abort", abort)
        request.onload = () => {
          cleanup()
          let result
          try {
            result = JSON.parse(request.responseText)
          } catch {
            reject(new Error("Unexpected upload response. Please retry."))
            return
          }
          if (request.status >= 200 && request.status < 300) resolve(result)
          else
            reject(
              new Error(
                result?.error?.message ?? "Upload failed. Please retry.",
              ),
            )
        }
        request.onerror = () => {
          cleanup()
          reject(new Error("Connection interrupted. Please retry the upload."))
        }
        request.onabort = () => {
          cleanup()
          reject(new DOMException("Upload cancelled", "AbortError"))
        }
        request.send(form)
      })
      if (epoch !== authEpoch.current) return
      setUploadState("saved")
      onSaved(data)
    } catch (error) {
      if (epoch === authEpoch.current) {
        setUploadError(true)
        setGenerationMessage(
          error instanceof Error && error.name === "AbortError"
            ? "Upload interrupted. Please retry."
            : error instanceof Error
              ? error.message
              : "Video upload failed. Check your connection and retry.",
        )
        setUploadState("preview")
      }
    } finally {
      uploadBusy.current = false
      uploadController.current = null
    }
  }

  function resetUpload() {
    uploadController.current?.abort()
    uploadBusy.current = false
    setUploadState("hidden")
    setSelectedUpload(null)
    setSelectedUploadUrl("")
    setUploadTitle("")
    setUploadDescription("")
  }
  return {
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
  }
}
