import { AppButton, Field } from "../shared"
import type { AppController } from "../useAppController"

type Props = AppController["pages"]["profileScreen"]

export function ProfilePage({
  session,
  authError,
  profile,
  setProfile,
  authBusy,
  saveProfile,
  back,
  signOut,
}: Props) {
  return (
    <main className="screen with-header form-page">
      <p>
        Signed in as <strong>{session?.user.username}</strong>. Update your name
        and optional measurements.
      </p>
      {authError && (
        <p className="form-error" role="alert">
          {authError}
        </p>
      )}
      <Field
        label="Name"
        value={profile.name}
        onChange={(name) => setProfile({ ...profile, name })}
        placeholder="Name"
      />
      <div className="field-row">
        <Field
          label="Height (cm)"
          value={profile.height}
          onChange={(height) => setProfile({ ...profile, height })}
          placeholder="168"
        />
        <Field
          label="Wingspan (cm)"
          value={profile.wingspan}
          onChange={(wingspan) => setProfile({ ...profile, wingspan })}
          placeholder="171"
        />
      </div>
      <div className="stack-actions">
        <AppButton
          disabled={authBusy || !profile.name.trim()}
          onClick={() => void saveProfile()}
        >
          {authBusy ? "Saving…" : "Save"}
        </AppButton>
        <AppButton variant="outline" onClick={back}>
          Skip
        </AppButton>
      </div>
      <AppButton
        variant="outline"
        disabled={authBusy}
        onClick={() => void signOut()}
      >
        Sign out
      </AppButton>
      <p className="privacy-box">
        Measurements are optional. Height: 100–230 cm; arm span: 80–260 cm.
      </p>
    </main>
  )
}
