import { AppButton, Field } from "../shared"
import type { AppController } from "../useAppController"

type Props = AppController["pages"]["accountScreen"]

export function AccountPage({
  accountMode,
  authError,
  setAccountMode,
  account,
  setAccount,
  authBusy,
  authLoading,
  submitAccount,
}: Props) {
  return (
    <main className="screen with-header form-page auth-form-page">
      <h1>{accountMode === "signin" ? "Welcome back" : "Join BetaLab"}</h1>
      <p>
        {accountMode === "signin"
          ? "Sign in with your username and password."
          : "Create an account, then optionally add your body measurements."}
      </p>
      {authError && (
        <p className="form-error" role="alert">
          {authError}
        </p>
      )}
      <div className="segmented">
        <button
          className={accountMode === "signin" ? "active" : ""}
          type="button"
          onClick={() => setAccountMode("signin")}
        >
          Sign in
        </button>
        <button
          className={accountMode === "signup" ? "active" : ""}
          type="button"
          onClick={() => setAccountMode("signup")}
        >
          Sign up
        </button>
      </div>
      <Field
        label="Username"
        value={account.email}
        onChange={(email) => setAccount({ ...account, email })}
        placeholder="3–32 letters, numbers or underscores"
      />
      <Field
        label="Password"
        value={account.password}
        onChange={(password) => setAccount({ ...account, password })}
        placeholder="At least 8 characters"
        type="password"
      />
      <div className="stack-actions">
        <AppButton
          disabled={
            authBusy ||
            authLoading ||
            !account.email.trim() ||
            account.password.length < 8
          }
          onClick={() => void submitAccount()}
        >
          {authBusy
            ? "Please wait…"
            : accountMode === "signup"
              ? "Create account"
              : "Sign in"}
        </AppButton>
      </div>
      <p className="muted small">
        Usernames are case-insensitive. Passwords must contain at least 8
        characters.
      </p>
    </main>
  )
}
