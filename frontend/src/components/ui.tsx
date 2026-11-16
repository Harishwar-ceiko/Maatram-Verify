import type { ReactNode } from "react";
import { clsx } from "clsx";
import { Loader2 } from "lucide-react";
import { statusLabel } from "../lib/query";

/* Brand ------------------------------------------------------------------ */

export function Brand({ size = "md" }: { size?: "sm" | "md" }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <span
        className={clsx(
          "grid place-items-center rounded-[2px] bg-ink text-paper",
          size === "md" ? "h-8 w-8" : "h-7 w-7",
        )}
        aria-hidden="true"
      >
        <svg width="15" height="15" viewBox="0 0 16 16" fill="none">
          <path
            d="M3 8.4 6.2 11.6 13 4.8"
            stroke="currentColor"
            strokeWidth="1.7"
            strokeLinecap="square"
          />
        </svg>
      </span>
      <span
        className={clsx(
          "font-serif leading-none tracking-[-0.02em]",
          size === "md" ? "text-[19px]" : "text-[17px]",
        )}
      >
        Maatram <span className="text-muted">Verify</span>
      </span>
    </span>
  );
}

/* Buttons ---------------------------------------------------------------- */

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

export function Button({
  variant = "primary",
  size,
  block,
  busy,
  className,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: "sm";
  block?: boolean;
  busy?: boolean;
}) {
  return (
    <button
      className={clsx(
        "btn",
        `btn-${variant}`,
        size === "sm" && "btn-sm",
        block && "btn-block",
        className,
      )}
      disabled={props.disabled || busy}
      {...props}
    >
      {busy ? <Loader2 size={15} className="animate-spin" aria-hidden="true" /> : null}
      {children}
    </button>
  );
}

/* Form ------------------------------------------------------------------- */

export function Field({
  label,
  htmlFor,
  hint,
  error,
  children,
  className,
}: {
  label: string;
  htmlFor?: string;
  hint?: ReactNode;
  error?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={clsx("field", className)}>
      <label className="field-label" htmlFor={htmlFor}>
        {label}
      </label>
      {children}
      {error ? (
        <span className="field-error" role="alert">
          {error}
        </span>
      ) : hint ? (
        <span className="field-hint">{hint}</span>
      ) : null}
    </div>
  );
}

/* Status ----------------------------------------------------------------- */

export function StatusBadge({ value, className }: { value: string; className?: string }) {
  return (
    <span className={clsx("status", `status-${value}`, className)}>
      <span className="status-mark" aria-hidden="true" />
      {statusLabel(value)}
    </span>
  );
}

/* Feedback --------------------------------------------------------------- */

export function Alert({
  tone = "error",
  title,
  children,
}: {
  tone?: "error" | "info" | "warn" | "success";
  title?: string;
  children?: ReactNode;
}) {
  const tones = {
    error: "border-fail/40 bg-fail-wash text-fail",
    info: "border-line-strong bg-paper-deep/60 text-ink-soft",
    warn: "border-warn/35 bg-warn-wash text-warn",
    success: "border-pass/30 bg-pass-wash text-pass",
  } as const;
  return (
    <div
      className={clsx("rounded-[2px] border px-3.5 py-3 text-[13px] leading-relaxed", tones[tone])}
      role={tone === "error" ? "alert" : "status"}
    >
      {title ? <p className="font-semibold">{title}</p> : null}
      {children ? <div className={title ? "mt-1" : undefined}>{children}</div> : null}
    </div>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-[13px] text-muted" role="status">
      <Loader2 size={15} className="animate-spin" aria-hidden="true" />
      {label}
    </span>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return (
    <span
      className={clsx("block animate-pulse rounded-[2px] bg-paper-deep", className)}
      aria-hidden="true"
    />
  );
}

export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  icon?: ReactNode;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      {icon ? <div className="empty-mark">{icon}</div> : null}
      <h3 className="text-[15px] font-semibold text-ink">{title}</h3>
      {children ? <div className="max-w-[42ch] text-[13px] text-muted">{children}</div> : null}
      {action ? <div className="mt-1.5">{action}</div> : null}
    </div>
  );
}

/* Page furniture --------------------------------------------------------- */

export function PageHeader({
  title,
  description,
  actions,
  aside,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  aside?: ReactNode;
}) {
  return (
    <header className="mb-8 flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
      <div className="min-w-0 max-w-[68ch]">
        <h1 className="page-title">{title}</h1>
        {description ? <p className="lede mt-2.5">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
      {aside}
    </header>
  );
}

export function SectionCard({
  title,
  aside,
  children,
  className,
  bodyClassName,
}: {
  title?: ReactNode;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section className={clsx("card", className)}>
      {title ? (
        <div className="card-head">
          <h2 className="section-title">{title}</h2>
          {aside}
        </div>
      ) : null}
      <div className={clsx("card-body", bodyClassName)}>{children}</div>
    </section>
  );
}

export function Requirement({ children }: { children: ReactNode }) {
  return (
    <li className="flex items-start gap-2.5 text-[13px] leading-relaxed text-ink-soft">
      <svg
        width="13"
        height="13"
        viewBox="0 0 16 16"
        fill="none"
        className="mt-[5px] shrink-0 text-pass"
        aria-hidden="true"
      >
        <path d="M3 8.4 6.2 11.6 13 4.8" stroke="currentColor" strokeWidth="1.7" strokeLinecap="square" />
      </svg>
      <span>{children}</span>
    </li>
  );
}
