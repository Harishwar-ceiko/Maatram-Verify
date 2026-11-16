import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { AuthLayout } from "../../components/AuthLayout";
import { PasswordInput } from "../../components/form";
import { Alert, Button, Field } from "../../components/ui";
import { useAuth, landingFor } from "../../lib/auth";
import { ApiError } from "../../lib/api";

export function RegisterPage() {
  const { signUp } = useAuth();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    if (password.length < 8 || !/[a-zA-Z]/.test(password) || !/\d/.test(password)) {
      setError("Use at least 8 characters, with a letter and a number.");
      return;
    }
    setBusy(true);
    try {
      const user = await signUp(fullName.trim(), email.trim(), password);
      navigate(landingFor(user.role), { replace: true });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.detail : "Could not create the account. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <h2 className="font-serif text-[1.7rem] font-medium leading-tight tracking-[-0.015em]">
        Create your applicant account
      </h2>
      <p className="mt-2 text-[13.5px] text-muted">
        One account holds every application you file.
      </p>

      <form className="mt-7 grid gap-4" onSubmit={onSubmit} noValidate>
        {error ? <Alert tone="error">{error}</Alert> : null}

        <Field label="Full name" htmlFor="full_name">
          <input
            id="full_name"
            name="full_name"
            className="input"
            autoComplete="name"
            placeholder="As printed on your mark sheet"
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
            required
          />
        </Field>

        <Field label="Email address" htmlFor="email">
          <input
            id="email"
            name="email"
            type="email"
            className="input"
            autoComplete="email"
            placeholder="you@example.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </Field>

        <Field
          label="Password"
          htmlFor="password"
          hint="At least 8 characters, with a letter and a number."
        >
          <PasswordInput
            id="password"
            name="password"
            autoComplete="new-password"
            placeholder="Choose a password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </Field>

        <Button type="submit" block busy={busy} className="mt-1 h-11">
          Create account
          {busy ? null : <ArrowRight size={15} aria-hidden="true" />}
        </Button>
      </form>

      <p className="mt-5 text-center text-[13px] text-muted">
        Already registered?{" "}
        <Link to="/login" className="font-medium text-ink underline decoration-line-strong underline-offset-4 hover:decoration-ink">
          Sign in
        </Link>
      </p>

      <div className="mt-8 border-t border-line pt-4">
        <p className="text-[11.5px] leading-relaxed text-muted">
          Reviewer accounts are provisioned by the admissions office. This form creates applicant
          accounts only.
        </p>
      </div>
    </AuthLayout>
  );
}
