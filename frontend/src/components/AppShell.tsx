import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import {
  ClipboardCheck,
  FileText,
  Gauge,
  LayoutDashboard,
  LogOut,
  Menu,
  Plus,
  ScrollText,
  ShieldCheck,
  X,
} from "lucide-react";
import { clsx } from "clsx";
import { useAuth } from "../lib/auth";
import { Brand } from "./ui";

interface NavItem {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  end?: boolean;
}

const studentNav: NavItem[] = [
  { to: "/overview", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/applications", label: "My applications", icon: FileText, end: true },
  { to: "/applications/new", label: "New application", icon: Plus, end: true },
];

const adminNav: NavItem[] = [
  { to: "/admin", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/admin/applications", label: "All applications", icon: FileText, end: true },
  { to: "/admin/reviews", label: "Review queue", icon: ClipboardCheck, end: true },
  { to: "/admin/accuracy", label: "Accuracy", icon: Gauge, end: true },
  { to: "/admin/audit", label: "Audit log", icon: ScrollText, end: true },
];

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

function NavList({ items, onNavigate }: { items: NavItem[]; onNavigate?: () => void }) {
  return (
    <nav className="grid gap-0.5">
      {items.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={onNavigate}
          className={({ isActive }) => clsx("rail-link", isActive && "font-semibold")}
        >
          <Icon aria-hidden="true" />
          <span>{label}</span>
        </NavLink>
      ))}
    </nav>
  );
}

function RailBody({ onNavigate }: { onNavigate?: () => void }) {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const isAdmin = user?.role === "admin";

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="px-5 pt-6 pb-5">
        <Brand />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
        {isAdmin ? (
          <>
            <p className="label px-3 pb-1.5 pt-2">Admissions office</p>
            <NavList items={adminNav} onNavigate={onNavigate} />
          </>
        ) : (
          <>
            <p className="label px-3 pb-1.5 pt-2">Workspace</p>
            <NavList items={studentNav} onNavigate={onNavigate} />
          </>
        )}
      </div>

      <div className="border-t border-line p-3">
        <div className="flex items-center gap-2.5 px-2 py-1.5">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-[2px] border border-line-strong bg-surface font-mono text-[11px] text-ink-soft">
            {user ? initials(user.full_name) : "—"}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block break-words text-[13px] font-medium leading-tight">
              {user?.full_name}
            </span>
            <span className="mt-0.5 flex items-center gap-1 text-[11px] text-muted">
              {isAdmin ? (
                <>
                  <ShieldCheck size={11} aria-hidden="true" /> Reviewer
                </>
              ) : (
                "Applicant"
              )}
            </span>
          </span>
          <button
            type="button"
            className="btn btn-ghost h-8 w-8 p-0"
            aria-label="Sign out"
            onClick={() => {
              signOut();
              navigate("/login", { replace: true });
            }}
          >
            <LogOut size={15} aria-hidden="true" />
          </button>
        </div>
        <p className="px-2 pb-1 pt-2 font-mono text-[10px] leading-relaxed text-faint">
          MH26-01 · rules v1
        </p>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const { user } = useAuth();

  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <div className="min-h-dvh md:grid md:grid-cols-[var(--rail)_minmax(0,1fr)]">
      <aside className="rail sticky top-0 hidden h-dvh md:block">
        <RailBody />
      </aside>

      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-line bg-paper/95 px-4 backdrop-blur-sm md:hidden">
        <button
          type="button"
          className="btn btn-ghost h-9 w-9 p-0"
          aria-label="Open navigation"
          aria-expanded={open}
          aria-controls="mobile-nav"
          onClick={() => setOpen(true)}
        >
          <Menu size={19} aria-hidden="true" />
        </button>
        <Brand size="sm" />
        <span className="grid h-8 w-8 place-items-center rounded-[2px] border border-line-strong bg-surface font-mono text-[11px] text-ink-soft">
          {user ? initials(user.full_name) : "—"}
        </span>
      </header>

      {open ? (
        <div className="fixed inset-0 z-50 md:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-ink/35"
            aria-label="Close navigation"
            onClick={() => setOpen(false)}
          />
          <div
            id="mobile-nav"
            className="absolute inset-y-0 left-0 w-[284px] border-r border-line bg-paper-deep"
          >
            <button
              type="button"
              className="btn btn-ghost absolute right-2 top-2 h-9 w-9 p-0"
              aria-label="Close navigation"
              onClick={() => setOpen(false)}
            >
              <X size={18} aria-hidden="true" />
            </button>
            <RailBody onNavigate={() => setOpen(false)} />
          </div>
        </div>
      ) : null}

      <main className="min-w-0">
        <div className="mx-auto w-full max-w-[1200px] px-5 py-7 sm:px-8 md:px-10 md:py-10">
          {children}
        </div>
      </main>
    </div>
  );
}
