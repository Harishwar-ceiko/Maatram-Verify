import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ArrowRight, ClipboardCheck, Loader2, ScanText } from "lucide-react";
import { AppShell } from "../../components/AppShell";
import { ApplicationsTable } from "../../components/ApplicationsTable";
import {
  Button,
  EmptyState,
  PageHeader,
  SectionCard,
  Skeleton,
  StatusBadge,
} from "../../components/ui";
import type { AdminActivity } from "../../lib/api";
import { api } from "../../lib/api";
import { formatDate, statusLabel } from "../../lib/query";

const ORDER = ["submitted", "processing", "needs_review", "verified", "approved", "rejected"];

function clock(value: number): string {
  if (!value) return "—";
  return new Date(value).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function ActivityRow({ entry }: { entry: AdminActivity }) {
  const flagged = entry.critical + entry.warnings;
  const total = entry.matched + entry.mismatched;
  return (
    <tr>
      <td className="mono whitespace-nowrap text-[11px] text-muted">
        {entry.finished_at ? formatDate(entry.finished_at, true) : "—"}
      </td>
      <td>
        <Link
          to={`/admin/applications/${entry.application_id}`}
          className="font-medium underline decoration-line-strong underline-offset-4 hover:decoration-ink"
        >
          {entry.reference}
        </Link>
        <span className="mt-0.5 block text-[11px] text-muted">{entry.applicant_name}</span>
      </td>
      <td>
        {entry.status === "failed" ? (
          <StatusBadge value="fail" />
        ) : entry.overall ? (
          <StatusBadge value={entry.overall} />
        ) : (
          <span className="text-[11.5px] text-muted">—</span>
        )}
      </td>
      <td className="num">
        {total ? (
          <>
            {entry.matched}
            <span className="text-muted"> / {total}</span>
          </>
        ) : (
          "—"
        )}
        <span className="mt-0.5 block text-[10px] font-normal text-muted">
          {entry.mismatched
            ? `${entry.mismatched} mismatched`
            : entry.matched
              ? "all matched"
              : "no marks compared"}
        </span>
      </td>
      <td className="num">
        {flagged ? (
          <>
            <span className={entry.critical ? "text-fail" : "text-warn"}>{flagged}</span>
            <span className="mt-0.5 block text-[10px] font-normal text-muted">
              {entry.critical ? `${entry.critical} critical` : "warnings"}
              {entry.warnings ? ` · ${entry.warnings} warning${entry.warnings === 1 ? "" : "s"}` : ""}
            </span>
          </>
        ) : (
          <span className="text-pass">clear</span>
        )}
      </td>
      <td className="num text-muted">
        {typeof entry.ocr_confidence === "number" ? `${Math.round(entry.ocr_confidence)}%` : "—"}
      </td>
      <td className="w-8 text-right">
        <Link
          to={`/admin/applications/${entry.application_id}`}
          aria-label={`Open ${entry.reference}`}
          className="inline-flex text-muted transition-colors duration-150 hover:text-ink"
        >
          <ArrowRight size={14} aria-hidden="true" />
        </Link>
      </td>
    </tr>
  );
}

export function AdminOverviewPage() {
  const overview = useQuery({
    queryKey: ["admin", "overview"],
    queryFn: api.adminOverview,
    refetchInterval: 5000,
  });

  const data = overview.data;
  const processing = data?.processing ?? 0;
  const chart = ORDER.map((status) => ({
    status: statusLabel(status),
    full: statusLabel(status),
    count: data?.by_status?.[status] ?? 0,
  }));

  return (
    <AppShell>
      <PageHeader
        title="Admissions overview"
        description="What the checker found across every application, and what still needs a person."
        actions={
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <span className="inline-flex items-center gap-2 text-[11px] text-muted">
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  processing ? "animate-pulse bg-warn" : "bg-pass"
                }`}
                aria-hidden="true"
              />
              {processing
                ? `${processing} being read`
                : `Live · updated ${clock(overview.dataUpdatedAt)}`}
            </span>
            <Link to="/admin/reviews">
              <Button variant="secondary">
                Open review queue
                <ArrowRight size={15} aria-hidden="true" />
              </Button>
            </Link>
          </div>
        }
      />

      {processing ? (
        <div className="mb-5 flex items-start gap-2.5 border border-warn/35 bg-warn-wash/50 px-4 py-3">
          <Loader2 size={14} className="mt-0.5 shrink-0 animate-spin text-warn" aria-hidden="true" />
          <p className="text-[12px] leading-relaxed text-warn">
            {processing === 1
              ? "One application is being read now."
              : `${processing} applications are being read now.`}{" "}
            This page refreshes every five seconds; finished runs appear below without a reload.
          </p>
        </div>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="stat">
          <p className="label">Applications</p>
          <p className="stat-value mt-2">{overview.isLoading ? "—" : data?.total_applications}</p>
          <p className="mt-2 text-[12px] text-muted">{data?.students ?? 0} applicants registered</p>
        </div>
        <div className="stat">
          <p className="label">Needs review</p>
          <p className="stat-value mt-2 text-accent-deep">{overview.isLoading ? "—" : data?.by_status?.needs_review ?? 0}</p>
          <p className="mt-2 text-[12px] text-muted">
            {data?.open_reviews ?? 0} item{(data?.open_reviews ?? 0) === 1 ? "" : "s"} open in the queue
          </p>
        </div>
        <div className="stat">
          <p className="label">Verified</p>
          <p className="stat-value mt-2 text-pass">{overview.isLoading ? "—" : data?.verified}</p>
          <p className="mt-2 text-[12px] text-muted">Every check passed</p>
        </div>
        <div className="stat">
          <p className="label">Findings</p>
          <p className="stat-value mt-2">
            {overview.isLoading ? "—" : (data?.mismatch_findings ?? 0) + (data?.photo_failures ?? 0)}
          </p>
          <p className="mt-2 text-[12px] text-muted">
            {data?.mismatch_findings ?? 0} mark mismatches · {data?.photo_failures ?? 0} photo failures
          </p>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,0.65fr)]">
        <SectionCard title="Applications by status">
          {overview.isLoading ? (
            <Skeleton className="h-[220px] w-full" />
          ) : (
            <div className="h-[232px] w-full" aria-label="Bar chart of applications by status" role="img">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chart} margin={{ top: 8, right: 4, bottom: 0, left: -18 }}>
                  <CartesianGrid vertical={false} stroke="var(--color-line)" strokeDasharray="2 4" />
                  <XAxis
                    dataKey="status"
                    tickLine={false}
                    axisLine={{ stroke: "var(--color-line)" }}
                    tick={{ fill: "var(--color-muted)", fontSize: 11 }}
                  />
                  <YAxis
                    allowDecimals={false}
                    tickLine={false}
                    axisLine={false}
                    tick={{ fill: "var(--color-muted)", fontSize: 11 }}
                  />
                  <Tooltip
                    cursor={{ fill: "var(--color-paper-deep)", opacity: 0.6 }}
                    contentStyle={{
                      background: "var(--color-surface)",
                      border: "1px solid var(--color-line-strong)",
                      borderRadius: 2,
                      fontSize: 12,
                      color: "var(--color-ink)",
                    }}
                    labelFormatter={(_, payload) => payload?.[0]?.payload?.full ?? ""}
                  />
                  <Bar
                    dataKey="count"
                    fill="var(--color-accent)"
                    radius={0}
                    barSize={30}
                    isAnimationActive={false}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </SectionCard>

        <div className="grid content-start gap-6">
          <SectionCard title="Work queue">
            <div className="grid gap-4">
              <div className="flex items-end justify-between gap-4 border-b border-line pb-3">
                <div>
                  <p className="text-[12.5px] font-medium">Flagged applications</p>
                  <p className="mt-0.5 text-[11.5px] text-muted">Routed for a manual decision</p>
                </div>
                <p className="font-serif text-[26px] leading-none">{data?.open_reviews ?? 0}</p>
              </div>
              <div className="flex items-end justify-between gap-4 border-b border-line pb-3">
                <div>
                  <p className="text-[12.5px] font-medium">Mark mismatches</p>
                  <p className="mt-0.5 text-[11.5px] text-muted">Entered differs from the sheet</p>
                </div>
                <p className="font-serif text-[26px] leading-none">{data?.mismatch_findings ?? 0}</p>
              </div>
              <div className="flex items-end justify-between gap-4">
                <div>
                  <p className="text-[12.5px] font-medium">Photo failures</p>
                  <p className="mt-0.5 text-[11.5px] text-muted">Below a measurable rule</p>
                </div>
                <p className="font-serif text-[26px] leading-none">{data?.photo_failures ?? 0}</p>
              </div>
            </div>
            <Link
              to="/admin/reviews"
              className="mt-5 inline-flex items-center gap-1.5 text-[12.5px] font-medium text-ink underline decoration-line-strong underline-offset-4 hover:decoration-ink"
            >
              Review flagged files
              <ArrowRight size={13} aria-hidden="true" />
            </Link>
          </SectionCard>

          <div className="card-flat bg-paper-deep/50 p-5">
            <ClipboardCheck size={17} className="text-accent" aria-hidden="true" />
            <p className="mt-2.5 text-[13px] font-medium leading-snug">Every decision is logged</p>
            <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted">
              Who corrected a value, who approved or rejected, and when. The audit log is append-only.
            </p>
          </div>
        </div>
      </div>

      <div className="mt-6">
        <SectionCard
          title="Validation activity"
          aside={
            <span className="inline-flex items-center gap-1.5 text-[11px] text-muted">
              <ScanText size={12} aria-hidden="true" />
              {data?.activity?.length ?? 0} recent run{data?.activity?.length === 1 ? "" : "s"}
            </span>
          }
          bodyClassName="p-0"
        >
          {overview.isLoading ? (
            <div className="grid gap-3 p-5">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-[70%]" />
            </div>
          ) : !data?.activity?.length ? (
            <EmptyState icon={<ScanText size={19} aria-hidden="true" />} title="No validation runs yet">
              Open an application and run the checks; the outcome, mark comparisons and flags appear
              here as the run completes.
            </EmptyState>
          ) : (
            <div className="overflow-x-auto">
              <table className="data-table min-w-[760px]">
                <thead>
                  <tr>
                    <th scope="col">Read at</th>
                    <th scope="col">Application</th>
                    <th scope="col">Outcome</th>
                    <th scope="col" className="text-right">Marks</th>
                    <th scope="col" className="text-right">Flags</th>
                    <th scope="col" className="text-right">OCR</th>
                    <th scope="col" aria-label="Open" />
                  </tr>
                </thead>
                <tbody>
                  {data.activity.map((entry) => (
                    <ActivityRow key={entry.id} entry={entry} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>
      </div>

      <div className="mt-6">
        <SectionCard
          title="Recently filed"
          aside={
            <Link to="/admin/applications" className="text-[12.5px] text-muted underline decoration-line-strong underline-offset-4 hover:text-ink hover:decoration-ink">
              All applications
            </Link>
          }
          bodyClassName="p-0"
        >
          {overview.isLoading ? (
            <div className="grid gap-3 p-5">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-[70%]" />
            </div>
          ) : (
            <ApplicationsTable items={data?.recent ?? []} admin />
          )}
        </SectionCard>
      </div>
    </AppShell>
  );
}
