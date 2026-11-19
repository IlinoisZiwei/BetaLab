import { AppButton } from "../shared"
import type { AppController } from "../useAppController"

type Props = AppController["pages"]["header"]

export function PageHeader({ screen, back, pageTitle }: Props) {
  return (
    screen !== "home" &&
    screen !== "community" &&
    screen !== "communityVideo" && (
      <header className="topbar">
        <AppButton variant="text" onClick={back} className="back">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="m14 6-6 6 6 6" />
          </svg>
          <span>Back</span>
        </AppButton>
        <strong>{pageTitle[screen]}</strong>
        <span className="header-spacer" aria-hidden="true" />
      </header>
    )
  )
}
