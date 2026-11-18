import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowRight, ClipboardCheck, Plus } from "lucide-react";
import { AppShell } from "../../components/AppShell";
import { ApplicationsTable } from "../../components/ApplicationsTable";
import { Button, PageHeader, SectionCard, Skeleton } from "../../components/ui";
import { api } from "../../lib/api";
import { formatDate } from "../../lib/query";

export function OverviewPage() {
  const applications = useQuery({
    queryKey: ["applications", "mine"],
    queryFn: () => api.applications({ page_size: 100 }),
  });
  const config = useQuery({ queryKey: ["config"], queryFn: api.config });

  const items = applications.data?.items ?? [];
  const total = applications.data?.total ?? 0;
  const needsReview = items.filter((item) => item.status === "needs_review").length;
  const verified = items.filter((item) => ["verified", "approved"].includes(item.status)).length;
  const latest = items.slice(0, 4);

  return (
    <AppShell>
      <PageHeader
        title="Your applications"
        description="One file per student. Enter your details and school records, attach the documents, and each check resolves on this page."
        actions={
          <Link to="/applications/new">
            <Button>
              <Plus size={15} aria-hidden="true" />
              New application
            </Button>
          </Link>
        }
      />

      <div className="grid grid-cols-3 gap-3">
        <div className="stat p-3.5 sm:p-[18px_20px]">
          <p className="label">Applications filed</p>
          <p className="stat-value mt-2 text-[1.6rem] sm:text-[2rem]">
            {applications.isLoading ? "—" : total}
          </p>
          <p className="mt-2 hidden text-[12px] text-muted sm:block">
            {total === 0 ? "Your first one takes about five minutes." : "Across all applications."}
          </p>
        </div>
        <div className="stat p-3.5 sm:p-[18px_20px]">
          <p className="label">Waiting on you</p>
          <p className="stat-value mt-2 text-[1.6rem] text-accent-deep sm:text-[2rem]">
            {applications.isLoading ? "—" : needsReview}
          </p>
          <p className="mt-2 hidden text-[12px] text-muted sm:block">
            {needsReview > 0 ? "Open these to see what a reviewer needs." : "Nothing needs your attention."}
          </p>
        </div>
        <div className="stat p-3.5 sm:p-[18px_20px]">
          <p className="label">Verified</p>
          <p className="stat-value mt-2 text-[1.6rem] text-pass sm:text-[2rem]">
            {applications.isLoading ? "—" : verified}
          </p>
          <p className="mt-2 hidden text-[12px] text-muted sm:block">Every check passed and closed.</p>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_318px]">
        <SectionCard
          title="Recent activity"
          aside={
            <Link to="/applications" className="text-[12.5px] text-muted underline decoration-line-strong underline-offset-4 hover:text-ink hover:decoration-ink">
              View all
            </Link>
          }
          bodyClassName="p-0"
        >
          {applications.isLoading ? (
            <div className="grid gap-3 p-5">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-[80%]" />
            </div>
          ) : (
            <ApplicationsTable
              items={latest}
              emptyAction={
                <Link to="/applications/new">
                  <Button size="sm">Start an application</Button>
                </Link>
              }
            />
          )}
        </SectionCard>

        <aside className="grid content-start gap-6">
          <SectionCard title="What the checker reads">
            <ul className="grid gap-3">
              <li className="border-b border-line pb-3">
                <p className="text-[13px] font-medium">Marks, subject by subject</p>
                <p className="mt-1 text-[12px] leading-relaxed text-muted">
                  Your typed numbers are compared with the uploaded sheet. A difference of one mark
                  is a mismatch.
                </p>
              </li>
              <li className="border-b border-line pb-3">
                <p className="text-[13px] font-medium">The photograph</p>
                <p className="mt-1 text-[12px] leading-relaxed text-muted">
                  {config.data
                    ? `At least ${config.data.photo.min_width} × ${config.data.photo.min_height} px, portrait, sharp, evenly lit, ${config.data.photo.allowed_formats.join(" or ")}.`
                    : "Resolution, aspect ratio, format, brightness and blur are measured, not guessed."}
                </p>
              </li>
              <li>
                <p className="text-[13px] font-medium">Complete or missing</p>
                <p className="mt-1 text-[12px] leading-relaxed text-muted">
                  {config.data
                    ? `Class 12 subjects: ${config.data.subjects.required.join(", ")}.`
                    : "Required subjects, duplicate files and identity conflicts are checked too."}
                </p>
              </li>
            </ul>
          </SectionCard>

          <div className="card-flat bg-paper-deep/50 p-5">
            <ClipboardCheck size={18} className="text-accent" aria-hidden="true" />
            <p className="mt-3 text-[13.5px] font-medium leading-snug">
              No generative AI touches a decision.
            </p>
            <p className="mt-1.5 text-[12px] leading-relaxed text-muted">
              OCR, OpenCV and fixed rules produce every result. A person makes every approval.
            </p>
            <Link
              to="/applications/new"
              className="mt-3 inline-flex items-center gap-1.5 text-[12.5px] font-medium text-ink underline decoration-line-strong underline-offset-4 hover:decoration-ink"
            >
              File an application
              <ArrowRight size={13} aria-hidden="true" />
            </Link>
          </div>

          <p className="px-1 text-[11px] leading-relaxed text-faint">
            Last refreshed {applications.dataUpdatedAt ? formatDate(new Date(applications.dataUpdatedAt).toISOString(), true) : "—"}
          </p>
        </aside>
      </div>
    </AppShell>
  );
}
