
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import {
  ClipboardCheck,
  FileText,
  Users,
  Gauge,
  LayoutDashboard,
  LogOut,
  Menu,
  Plus,
  ScrollText,
  ShieldCheck,
  X,
  ArrowUpRight,
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
  { to: "/overview", label: "Home", icon: LayoutDashboard, end: true },
  { to: "/applications", label: "My Applications", icon: FileText, end: true },
  { to: "/applications/new", label: "New Application", icon: Plus, end: true },
];

const adminNav: NavItem[] = [
  { to: "/admin", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/admin/students", label: "Students", icon: Users, end: true },
  { to: "/admin/applications", label: "Applications", icon: FileText, end: true },
  { to: "/admin/reviews", label: "Review Queue", icon: ClipboardCheck, end: true },
  { to: "/admin/accuracy", label: "Accuracy", icon: Gauge, end: true },
  { to: "/admin/audit", label: "Audit Records", icon: ScrollText, end: true },
];

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

function Navigation({
  items,
  onNavigate,
}: {
  items: NavItem[];
  onNavigate?: () => void;
}) {
  return (
    <nav className="institutional-nav" aria-label="Main navigation">
      {items.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={onNavigate}
          className={({ isActive }) =>
            clsx("institutional-nav-link", isActive && "active")
          }
        >
          <Icon size={16} aria-hidden="true" />
          <span>{label}</span>
        </NavLink>
      ))}
    </nav>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { user, signOut } = useAuth();

  const isAdmin = user?.role === "admin";
  const navItems = isAdmin ? adminNav : studentNav;

  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!open) return;

    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };

    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  function handleSignOut() {
    signOut();
    navigate("/login", { replace: true });
  }

  return (
    <div className="institutional-shell min-h-dvh">

      {/* Top information strip */}
      <div className="institutional-utility">
        <div className="institutional-utility-inner">
          <span>MAATRAM FOUNDATION</span>
          <span className="utility-divider">|</span>
          <span>ADMISSION & DOCUMENT VERIFICATION PORTAL</span>

          <div className="utility-right">
            <span className="utility-indicator" />
            STUDENT SERVICES
          </div>
        </div>
      </div>

      {/* Main identity header */}
      <header className="institutional-header">
        <div className="institutional-header-inner">

          <div className="institutional-brand">
            <Brand />
            <div className="brand-subtitle">
              EMPOWERING EDUCATION
            </div>
          </div>

          <div className="institutional-header-center">
            <span>OFFICIAL DIGITAL PORTAL</span>
            <strong>Student Admission & Verification</strong>
          </div>

          <div className="institutional-user">

            <div className="institutional-user-avatar">
              {user ? initials(user.full_name) : "MV"}
            </div>

            <div className="institutional-user-details">
              <strong>{user?.full_name ?? "Guest"}</strong>
              <span>{isAdmin ? "Administrator" : "Applicant"}</span>
            </div>

            <button
              type="button"
              className="institutional-logout"
              onClick={handleSignOut}
              aria-label="Sign out"
              title="Sign out"
            >
              <LogOut size={17} />
            </button>
          </div>

          <button
            type="button"
            className="institutional-mobile-toggle"
            onClick={() => setOpen((value) => !value)}
            aria-label={open ? "Close navigation" : "Open navigation"}
            aria-expanded={open}
          >
            {open ? <X size={22} /> : <Menu size={22} />}
          </button>

        </div>
      </header>

      {/* Desktop navigation */}
      <div className="institutional-navigation-bar">
        <div className="institutional-navigation-inner">
          <Navigation items={navItems} />

          <div className="institutional-navigation-right">
            <ShieldCheck size={15} />
            SECURE ADMISSION PORTAL
          </div>
        </div>
      </div>

      {/* Mobile navigation */}
      {open && (
        <div className="institutional-mobile-panel">
          <Navigation
            items={navItems}
            onNavigate={() => setOpen(false)}
          />

          <button
            type="button"
            className="institutional-mobile-logout"
            onClick={handleSignOut}
          >
            <LogOut size={16} />
            Sign out
          </button>
        </div>
      )}

      {/* Main page content */}
      <main id="main-content" className="institutional-main">
        <div className="institutional-content">
          {children}
        </div>
      </main>

      {/* Institutional footer */}
      <footer className="institutional-footer">
        <div className="institutional-footer-inner">

          <div>
            <strong>MAATRAM FOUNDATION</strong>
            <p>Supporting students. Creating opportunities.</p>
          </div>

          <div className="institutional-footer-right">
            <span>MAATRAM VERIFY</span>
            <span>Digital Admission & Document Verification</span>
          </div>

          <a href="#main-content" className="back-to-top">
            Back to top <ArrowUpRight size={14} />
          </a>

        </div>
      </footer>

    </div>
  );
}
