import { PasswordSettings } from "./PasswordSettings"
import { ProfilePrivacy } from "./ProfilePrivacy"
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
      <h1 className="profile-edit-title">Edit profile</h1>
      <section className="profile-edit-section"><h2>Personal information</h2>
      <Field label="Username" value={profile.username} onChange={(username) => setProfile({ ...profile, username })} placeholder="Username" />
      <p className="setting-description">This is also your sign-in username.</p>
      {authError && (
        <p className="form-error" role="alert">
          {authError}
        </p>
      )}
      <Field
        label="Display name"
        value={profile.name}
        onChange={(name) => setProfile({ ...profile, name })}
        placeholder="Name"
      />
      <label className="profile-bio-label">Bio<textarea maxLength={500} value={profile.bio} onChange={e => setProfile({...profile, bio:e.target.value})} rows={3} placeholder="A little about your climbing" /></label>
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
          Back
        </AppButton>
      </div>
      </section>
      {session && <ProfilePrivacy session={session} />}
      <section className="profile-edit-section"><h2>Account</h2>
      {session && <PasswordSettings session={session} />}
      <AppButton
        variant="outline"
        disabled={authBusy}
        onClick={() => void signOut()}
      >
        Sign out
      </AppButton>
      </section>
    </main>
  )
}
