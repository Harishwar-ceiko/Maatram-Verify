import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation, useParams } from "react-router-dom";
import { ArrowLeft, Download, FileText, ShieldCheck } from "lucide-react";
import { AppShell } from "../../components/AppShell";
import { DocumentsPanel } from "../../components/DocumentsPanel";
import { ReviewPanel } from "../../components/ReviewPanel";
import { ValidationPanel } from "../../components/ValidationPanel";
import { Alert, Button, EmptyState, PageHeader, SectionCard, Skeleton, StatusBadge } from "../../components/ui";
import { api, ApiError, reportBlob } from "../../lib/api";
import type { ApplicationDetail } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { formatDate } from "../../lib/query";

function ReportDownload({ application }: { application: ApplicationDetail }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ready = application.latest_run?.status === "completed";

  async function download() {
    setBusy(true);
    setError(null);
    try {
      const blob = await reportBlob(application.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${application.reference}-validation.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The report could not be built.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid justify-items-end gap-1.5">
      <Button
        variant="secondary"
        size="sm"
        type="button"
        onClick={download}
        disabled={!ready}
        busy={busy}
        title={
          ready
            ? "Download the validation report as a PDF"
            : "Available once the checks finish"
        }
      >
        <Download size={14} aria-hidden="true" />
        Validation report
      </Button>
      {error ? (
        <span role="alert" className="max-w-[32ch] text-right text-[11px] leading-snug text-fail">
          {error}
        </span>
      ) : !ready ? (
        <span className="text-[11px] text-muted">PDF available after the checks finish</span>
      ) : null}
    </div>
  );
}

export function ApplicationDetailPage({ adminView }: { adminView?: boolean }) {
  const { id } = useParams();
  const location = useLocation();
  const { user } = useAuth();
  const isAdmin = adminView || user?.role === "admin";
  const created = Boolean((location.state as { created?: boolean } | null)?.created);

  const application = useQuery({
    queryKey: ["application", id],
    queryFn: () => api.application(id ?? ""),
    enabled: Boolean(id),
    refetchInterval: (query) => {
      const status = query.state.data?.latest_run?.status;
      return status === "pending" || status === "running" ? 1500 : false;
    },
  });

  if (application.isLoading) {
    return (
      <AppShell>
        <div className="grid gap-4">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-10 w-[60%]" />
          <Skeleton className="h-64 w-full" />
        </div>
      </AppShell>
    );
  }

  if (application.isError || !application.data) {
    return (
      <AppShell>
        <div className="card">
          <EmptyState
            icon={<FileText size={19} aria-hidden="true" />}
            title="Application not found"
            action={
              <Link to={isAdmin ? "/admin/applications" : "/applications"} className="btn btn-secondary btn-sm">
                Back to applications
              </Link>
            }
          >
            It may have been deleted, or it belongs to another applicant.
          </EmptyState>
        </div>
      </AppShell>
    );
  }

  const data = application.data;

  return (
    <AppShell>
      <Link
        to={isAdmin ? "/admin/applications" : "/applications"}
        className="mb-6 inline-flex items-center gap-1.5 text-[12.5px] text-muted transition-colors duration-150 hover:text-ink"
      >
        <ArrowLeft size={14} aria-hidden="true" />
        {isAdmin ? "All applications" : "My applications"}
      </Link>

      {created ? (
        <div className="mb-6">
          <Alert tone="success" title="Application filed">
            Reference {data.reference}. Attach the mark sheet and photograph next; the checker will
            read them.
          </Alert>
        </div>
      ) : null}

      <PageHeader
        title={data.program}
        description={
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
            <span className="mono text-[12.5px] text-ink-soft">{data.reference}</span>
            <span className="text-line-strong" aria-hidden="true">
              /
            </span>
            <StatusBadge value={data.status} />
            <span className="text-line-strong" aria-hidden="true">
              /
            </span>
            <span>Filed {formatDate(data.created_at)}</span>
          </span>
        }
        actions={<ReportDownload application={data} />}
      />

      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_330px]">
        <div className="grid gap-6">
          {isAdmin ? <ReviewPanel application={data} /> : null}

          <SectionCard title="Entered marks" bodyClassName="p-0">
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Subject</th>
                    <th scope="col" className="text-right">
                      Marks
                    </th>
                    <th scope="col" className="text-right">
                      Out of
                    </th>
                    <th scope="col" className="text-right">
                      Share
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.marks.map((mark) => (
                    <tr key={mark.id}>
                      <td className="font-medium">{mark.subject}</td>
                      <td className="num">{mark.marks_obtained}</td>
                      <td className="num text-muted">{mark.max_marks ?? "—"}</td>
                      <td className="num text-muted">
                        {mark.max_marks
                          ? `${Math.round((mark.marks_obtained / mark.max_marks) * 100)}%`
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SectionCard>

          {data.latest_run ? <ValidationPanel application={data} readOnly={isAdmin} /> : null}

          <DocumentsPanel applicationId={data.id} documents={data.documents} readOnly={isAdmin} />

          {!data.latest_run ? <ValidationPanel application={data} readOnly={isAdmin} /> : null}
        </div>

        <aside className="grid content-start gap-6">
          <SectionCard title="Applicant">
            <dl className="grid gap-3 text-[13px]">
              <div className="flex items-start justify-between gap-4">
                <dt className="text-muted">Name</dt>
                <dd className="text-right font-medium">{data.applicant_name}</dd>
              </div>
              <div className="flex items-start justify-between gap-4">
                <dt className="text-muted">Register no.</dt>
                <dd className="mono text-right text-[12px]">{data.register_number}</dd>
              </div>
              <div className="flex items-start justify-between gap-4">
                <dt className="text-muted">Exam year</dt>
                <dd className="mono text-right text-[12px]">{data.exam_year}</dd>
              </div>
              <div className="flex items-start justify-between gap-4">
                <dt className="text-muted">Board</dt>
                <dd className="max-w-[18ch] text-right">{data.board || "—"}</dd>
              </div>
            </dl>
          </SectionCard>

          <div className="card-flat bg-paper-deep/50 p-5">
            <ShieldCheck size={17} className="text-pass" aria-hidden="true" />
            <p className="mt-2.5 text-[13px] font-medium leading-snug">What is checked</p>
            <ul className="mt-2 grid gap-1.5 text-[11.5px] leading-relaxed text-muted">
              <li>Each subject, entered against the sheet.</li>
              <li>Sheet completeness and duplicates.</li>
              <li>Photo resolution, lighting, sharpness and face detection.</li>
              <li>Name and register number consistency.</li>
            </ul>
          </div>
        </aside>
      </div>
    </AppShell>
  );
}
