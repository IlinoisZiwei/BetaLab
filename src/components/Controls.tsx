import { useState } from "react"

export function AppButton({
  children,
  onClick,
  variant = "solid",
  className = "",
  disabled = false,
}: {
  children: React.ReactNode
  onClick?: () => void
  variant?: "solid" | "outline" | "text"
  className?: string
  disabled?: boolean
}) {
  return (
    <button
      className={`btn btn-${variant} ${className}`}
      type="button"
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  )
}

export function Field({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  type?: string
}) {
  return (
    <label className="field">
      {label && <span>{label}</span>}
      <input
        aria-label={label || placeholder}
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  )
}

export function SelectField({
  label,
  value,
  onChange,
  children,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  children: React.ReactNode
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {children}
      </select>
    </label>
  )
}

export function Placeholder({
  children,
  className = "",
}: {
  children: React.ReactNode
  className?: string
}) {
  return <div className={`placeholder ${className}`}>{children}</div>
}

export function PlaybackButton() {
  const [playing, setPlaying] = useState(false)

  return (
    <button
      className="playback-toggle"
      type="button"
      aria-label={playing ? "Pause video" : "Play video"}
      aria-pressed={playing}
      onClick={() => setPlaying(!playing)}
    >
      {playing ? (
        <span className="pause-symbol" aria-hidden="true">
          <i />
          <i />
        </span>
      ) : (
        <span className="play-symbol" aria-hidden="true" />
      )}
    </button>
  )
}
