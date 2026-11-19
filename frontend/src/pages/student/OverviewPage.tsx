
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  ArrowUpRight,
  FileCheck2,
  FileText,
  Plus,
  ShieldCheck,
  Clock3,
  ScanText,
  ClipboardCheck,
} from "lucide-react";

import { AppShell } from "../../components/AppShell";
import { StatusBadge } from "../../components/ui";
import { api } from "../../lib/api";
import { formatDate } from "../../lib/query";
import { useAuth } from "../../lib/auth";

export function OverviewPage() {
  const { user } = useAuth();

  const applications = useQuery({
    queryKey: ["applications", "mine"],
    queryFn: () => api.applications({ page_size: 100 }),
  });

  const config = useQuery({
    queryKey: ["config"],
    queryFn: api.config,
  });

  const items = applications.data?.items ?? [];
  const total = applications.data?.total ?? 0;

  const needsReview = items.filter(
    (item) => item.status === "needs_review"
  ).length;

  const verified = items.filter(
    (item) => ["verified", "approved"].includes(item.status)
  ).length;

  const processing = items.filter(
    (item) => ["submitted", "processing"].includes(item.status)
  ).length;

  const latest = items.slice(0, 4);
  const firstName = user?.full_name?.split(" ")[0] ?? "there";

  return (
    <AppShell>
      <div className="dashboard-page">

        {/* TOP HEADER */}
        <div className="dashboard-topline">
          <div className="dashboard-breadcrumb">
            <span>WORKSPACE</span>
            <span className="breadcrumb-divider">/</span>
            <strong>OVERVIEW</strong>
          </div>

          <div className="dashboard-system">
            <span className="system-dot" />
            ADMISSION PORTAL
          </div>
        </div>

        {/* HERO SECTION */}
        <section className="dashboard-hero">

          <div className="dashboard-hero-copy">
            <div className="dashboard-eyebrow">
              <span className="eyebrow-line" />
              YOUR ADMISSION JOURNEY
            </div>

            <h1>
              Welcome back,
              <br />
              <span>{firstName}.</span>
            </h1>

            <p>
              Your future deserves a clear path.
              Manage your documents, track applications
              and stay informed throughout verification.
            </p>

            <div className="dashboard-hero-actions">
              <Link
                to="/applications/new"
                className="dashboard-primary-action"
              >
                <Plus size={17} />
                Start an application
                <ArrowUpRight size={16} />
              </Link>

              <Link
                to="/applications"
                className="dashboard-secondary-action"
              >
                Explore applications
                <ArrowRight size={15} />
              </Link>
            </div>
          </div>

          <div className="dashboard-hero-art" aria-hidden="true">
            <div className="hero-orbit orbit-one" />
            <div className="hero-orbit orbit-two" />
            <div className="hero-orbit orbit-three" />

            <div className="hero-emblem">
              <ShieldCheck size={54} strokeWidth={1.2} />
              <span>MV</span>
            </div>

            <div className="hero-art-label">
              <span>DOCUMENTS</span>
              <strong>VERIFIED WITH CARE</strong>
            </div>
          </div>
        </section>

        {/* STATISTICS */}
        <section className="dashboard-stats">

          <article className="dashboard-stat stat-main">
            <div className="dashboard-stat-top">
              <span>01 / TOTAL SUBMISSIONS</span>
              <FileText size={19} />
            </div>

            <div className="dashboard-stat-value">
              {applications.isLoading ? "—" : total}
            </div>

            <div className="dashboard-stat-bottom">
              <span>Applications filed</span>
              <span className="stat-arrow">
                <ArrowUpRight size={17} />
              </span>
            </div>
          </article>

          <article className="dashboard-stat stat-attention">
            <div className="dashboard-stat-top">
              <span>02 / ATTENTION</span>
              <Clock3 size={19} />
            </div>

            <div className="dashboard-stat-value">
              {applications.isLoading ? "—" : needsReview}
            </div>

            <div className="dashboard-stat-bottom">
              <span>Applications needing review</span>
              <span className="stat-indicator" />
            </div>
          </article>

          <article className="dashboard-stat stat-verified">
            <div className="dashboard-stat-top">
              <span>03 / COMPLETED</span>
              <FileCheck2 size={19} />
            </div>

            <div className="dashboard-stat-value">
              {applications.isLoading ? "—" : verified}
            </div>

            <div className="dashboard-stat-bottom">
              <span>Verified applications</span>
              <ShieldCheck size={17} />
            </div>
          </article>
        </section>

        {/* MAIN CONTENT */}
        <div className="dashboard-main-grid">

          {/* APPLICATIONS */}
          <section className="dashboard-panel">

            <div className="dashboard-panel-heading">
              <div>
                <div className="dashboard-eyebrow">
                  YOUR RECORDS
                </div>
                <h2>Recent applications</h2>
                <p>Your latest application activity.</p>
              </div>

              <Link
                to="/applications"
                className="dashboard-view-link"
              >
                View all
                <ArrowUpRight size={16} />
              </Link>
            </div>

            <div className="dashboard-application-list">

              {applications.isLoading ? (
                <p className="dashboard-loading">
                  Loading your applications...
                </p>
              ) : latest.length === 0 ? (
                <div className="dashboard-empty">
                  <FileText size={32} />
                  <h3>No applications yet</h3>
                  <p>
                    Start your first application to begin
                    the admission verification process.
                  </p>
                  <Link to="/applications/new">
                    Create application <ArrowRight size={15} />
                  </Link>
                </div>
              ) : (
                latest.map((application, index) => {
                  const class12 = application.classes.find(
                    (record) => record.class_level === 12
                  );

                  return (
                    <Link
                      key={application.id}
                      to={`/applications/${application.id}`}
                      className="dashboard-application-card"
                    >
                      <div className="application-card-index">
                        0{index + 1}
                      </div>

                      <div className="application-card-content">
                        <span className="application-reference">
                          {application.reference}
                        </span>

                        <h3>
                          Class 12 Academic Records
                        </h3>

                        <span className="application-subtitle">
                          {class12?.board ?? "Academic documents"}
                          {" · "}
                          {class12?.exam_year ?? "—"}
                        </span>

                        <span className="application-date">
                          Submitted {formatDate(application.created_at)}
                        </span>
                      </div>

                      <div className="application-card-status">
                        <StatusBadge value={application.status} />
                        <ArrowUpRight size={17} />
                      </div>
                    </Link>
                  );
                })
              )}
            </div>
          </section>

          {/* RIGHT INFORMATION AREA */}
          <aside className="dashboard-side-column">

            <section className="dashboard-panel verification-panel">
              <div className="dashboard-eyebrow">
                THE PROCESS
              </div>

              <h2>How verification works</h2>

              <p className="verification-description">
                Every submission goes through a structured
                validation process.
              </p>

              <div className="verification-steps">
                <div className="verification-step">
                  <div className="verification-step-icon">
                    <FileText size={17} />
                  </div>
                  <div>
                    <strong>Document submission</strong>
                    <span>Upload your required files</span>
                  </div>
                </div>

                <div className="verification-connector" />

                <div className="verification-step">
                  <div className="verification-step-icon">
                    <ScanText size={17} />
                  </div>
                  <div>
                    <strong>Automated checks</strong>
                    <span>OCR and information matching</span>
                  </div>
                </div>

                <div className="verification-connector" />

                <div className="verification-step">
                  <div className="verification-step-icon">
                    <ClipboardCheck size={17} />
                  </div>
                  <div>
                    <strong>Human review</strong>
                    <span>Review of flagged submissions</span>
                  </div>
                </div>

                <div className="verification-connector" />

                <div className="verification-step">
                  <div className="verification-step-icon">
                    <ShieldCheck size={17} />
                  </div>
                  <div>
                    <strong>Final decision</strong>
                    <span>Verification result published</span>
                  </div>
                </div>
              </div>
            </section>

            <section className="dashboard-progress-panel">
              <div className="dashboard-eyebrow">
                YOUR WORKSPACE
              </div>

              <h3>Stay on track.</h3>

              <p>
                {needsReview > 0
                  ? `${needsReview} application(s) currently need your attention. Open them to view the review details.`
                  : processing > 0
                    ? `${processing} application(s) are awaiting further processing.`
                    : verified > 0
                      ? "Your verified applications are available in your records."
                      : "Submit your documents to begin your verification journey."}
              </p>

              <div className="dashboard-progress-footer">
                <span>Application overview</span>
                <Link to="/applications">
                  Open records <ArrowRight size={14} />
                </Link>
              </div>
            </section>

            <div className="dashboard-method-note">
              <ShieldCheck size={19} />
              <div>
                <strong>Verification with accountability</strong>
                <p>
                  Automated checks assist the process.
                  Official verification requires appropriate
                  evidence and authorized review.
                </p>
              </div>
            </div>

            {config.data && (
              <p className="dashboard-config-note">
                Photo requirement: {config.data.photo.min_width}
                {" × "}
                {config.data.photo.min_height} px minimum.
                Accepted formats:{" "}
                {config.data.photo.allowed_formats.join(", ")}.
              </p>
            )}
          </aside>
        </div>

      </div>
    </AppShell>
  );
}
