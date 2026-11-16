import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { AuthLayout } from "../../components/AuthLayout";
import { PasswordInput } from "../../components/form";
import { Alert, Button, Field } from "../../components/ui";
import { useAuth, landingFor } from "../../lib/auth";
import { ApiError } from "../../lib/api";

const DEMOS = [
  { label: "Applicant demo", email: "ananya@student.example", password: "Student@2026" },
  { label: "Reviewer demo", email: "admin@maatram.example", password: "Admin@2026" },
];

export function LoginPage() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const user = await signIn(email.trim(), password);
      navigate(landingFor(user.role), { replace: true });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.detail : "Could not sign in. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <h2 className="font-serif text-[1.7rem] font-medium leading-tight tracking-[-0.015em]">
        Sign in
      </h2>
      <p className="mt-2 text-[13.5px] text-muted">Continue to your application file.</p>

      <form className="mt-7 grid gap-4" onSubmit={onSubmit} noValidate>
        {error ? <Alert tone="error">{error}</Alert> : null}

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

        <Field label="Password" htmlFor="password">
          <PasswordInput
            id="password"
            name="password"
            autoComplete="current-password"
            placeholder="Your password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </Field>

        <Button type="submit" block busy={busy} className="mt-1 h-11">
          Sign in
          {busy ? null : <ArrowRight size={15} aria-hidden="true" />}
        </Button>
      </form>

      <p className="mt-5 text-center text-[13px] text-muted">
        New applicant?{" "}
        <Link to="/register" className="font-medium text-ink underline decoration-line-strong underline-offset-4 hover:decoration-ink">
          Create an account
        </Link>
      </p>

      <div className="mt-8 border-t border-line pt-4">
        <p className="text-[11.5px] text-muted">Demo access for this prototype</p>
        <div className="mt-2.5 grid grid-cols-2 gap-2">
          {DEMOS.map((demo) => (
            <button
              key={demo.email}
              type="button"
              className="rounded-[2px] border border-line bg-raised px-3 py-2 text-left transition-colors duration-150 hover:border-line-strong hover:bg-paper"
              onClick={() => {
                setEmail(demo.email);
                setPassword(demo.password);
                setError(null);
              }}
            >
              <span className="block text-[12px] font-medium text-ink">{demo.label}</span>
              <span className="mono mt-0.5 block truncate text-[10px] text-muted">{demo.email}</span>
            </button>
          ))}
        </div>
        <p className="mt-2.5 text-[10.5px] leading-relaxed text-faint">
          Clicking fills the form. Credentials are seeded locally, never sent anywhere else.
        </p>
      </div>
    </AuthLayout>
  );
}
