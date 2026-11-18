import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowRight, ClipboardCheck, RefreshCw, ScrollText } from "lucide-react";
import { clsx } from "clsx";
import { AppShell } from "../../components/AppShell";
import {
  Alert,
  Button,
  EmptyState,
  PageHeader,
  SectionCard,
  Skeleton,
  StatusBadge,
} from "../../components/ui";
import type { ReviewQueueItem } from "../../lib/api";
import { api } from "../../lib/api";
import { formatDate } from "../../lib/query";

const TABS = [
  { key: "active", label: "To review" },
  { key: "approved", label: "Approved" },
  { key: "rejected", label: "Rejected" },
  { key: "all", label: "All" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

function Priority({ value }: { value: number }) {
  const critical = value <= 20;
  return (
    <span className="inline-flex items-center gap-2 whitespace-nowrap">
      <span
        className={`h-[7px] w-[7px] rounded-[1px] ${critical ? "bg-fail" : "bg-warn"}`}
        aria-hidden="true"
      />
      <span className={clsx("text-[12px] font-medium", critical ? "text-fail" : "text-warn")}>
        {critical ? "Critical" : "Standard"}
      </span>
    </span>
  );
}

function QueueRow({ item }: { item: ReviewQueueItem }) {
  const total = item.matched + item.mismatched;
  const decided = item.status === "approved" || item.status === "rejected";

  return (
    <tr>
      <td className="align-top">
        <Priority value={item.priority} />
      </td>
      <td className="min-w-[190px] align-top">
        <Link
          to={`/admin/applications/${item.application_id}`}
          className="font-medium underline decoration-line-strong underline-offset-4 hover:decoration-ink"
        >
          {item.reference}
        </Link>
        <span className="mt-0.5 block text-[11.5px] text-muted">{item.applicant_name}</span>
        <span className="mt-0.5 block max-w-[34ch] truncate text-[10.5px] text-muted">
          Class 12 · {item.class_12_year ?? "—"}
        </span>
      </td>
      <td className="max-w-[300px] align-top">
        {item.reasons.length > 0 ? (
          <ul className="grid gap-1">
            {item.reasons.slice(0, 2).map((reason, index) => (
              <li key={`${index}-${reason}`} className="flex items-start gap-2 text-[11.5px] leading-snug text-ink-soft">
                <span
                  className="mt-[5px] h-[5px] w-[5px] flex-none rounded-[1px] bg-accent"
                  aria-hidden="true"
                />
                <span className="line-clamp-2">{reason}</span>
              </li>
            ))}
            {item.reasons.length > 2 ? (
              <li className="pl-[13px] text-[10.5px] text-muted">
                +{item.reasons.length - 2} more
              </li>
            ) : null}
          </ul>
        ) : (
          <span className="text-[11.5px] text-muted">No reason stored</span>
        )}
      </td>
      <td className="num align-top">
        {total ? (
          <>
            {item.matched}
            <span className="text-muted"> / {total}</span>
            <span className="mt-0.5 block text-[10px] font-normal text-muted">
              {item.mismatched ? `${item.mismatched} mismatched` : "all matched"}
            </span>
          </>
        ) : (
          <span className="text-[11.5px] text-muted">—</span>
        )}
        {item.critical || item.warnings ? (
          <span className="mt-0.5 block text-[10px] font-normal text-muted">
            {item.critical ? `${item.critical} critical` : ""}
            {item.critical && item.warnings ? " · " : ""}
            {item.warnings ? `${item.warnings} warning${item.warnings === 1 ? "" : "s"}` : ""}
          </span>
        ) : null}
      </td>
      <td className="align-top">
        <StatusBadge value={item.status} />
        {item.assigned_to_email && !decided ? (
          <span className="mt-1 block max-w-[20ch] truncate text-[10px] text-muted">
            {item.assigned_to_email}
          </span>
        ) : null}
      </td>
      <td className="mono whitespace-nowrap align-top text-[11px] text-muted">
        {decided ? (
          <>
            {formatDate(item.decided_at, true)}
            <span className="mt-0.5 block font-sans text-[10px]">
              {item.decided_by_email ?? "Admissions"}
            </span>
          </>
        ) : (
          formatDate(item.created_at, true)
        )}
      </td>
      <td className="w-8 align-top text-right">
        <Link
          to={`/admin/applications/${item.application_id}`}
          aria-label={`Open ${item.reference}`}
          className="inline-flex text-muted transition-colors duration-150 hover:text-ink"
        >
          <ArrowRight size={14} aria-hidden="true" />
        </Link>
      </td>
    </tr>
  );
}

function QueueCard({ item }: { item: ReviewQueueItem }) {
  const total = item.matched + item.mismatched;
  const decided = item.status === "approved" || item.status === "rejected";
  return (
    <article className="grid gap-3 px-4 py-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Priority value={item.priority} />
        <StatusBadge value={item.status} />
      </div>
      <div>
        <Link
          to={`/admin/applications/${item.application_id}`}
          className="font-medium underline decoration-line-strong underline-offset-4 hover:decoration-ink"
        >
          {item.reference}
        </Link>
        <p className="mt-0.5 text-[12px] text-muted">{item.applicant_name}</p>
        <p className="mt-0.5 text-[11px] text-muted">Class 12 · {item.class_12_year ?? "—"}</p>
      </div>
      {item.reasons.length > 0 ? (
        <ul className="grid gap-1.5">
          {item.reasons.slice(0, 3).map((reason, index) => (
            <li
              key={`${index}-${reason}`}
              className="flex items-start gap-2 text-[11.5px] leading-snug text-ink-soft"
            >
              <span
                className="mt-[5px] h-[5px] w-[5px] flex-none rounded-[1px] bg-accent"
                aria-hidden="true"
              />
              <span>{reason}</span>
            </li>
          ))}
          {item.reasons.length > 3 ? (
            <li className="pl-[13px] text-[10.5px] text-muted">
              +{item.reasons.length - 3} more
            </li>
          ) : null}
        </ul>
      ) : (
        <p className="text-[11.5px] text-muted">No reason stored</p>
      )}
      <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-3 border-t border-line pt-3">
        <div>
          <p className="label">Marks</p>
          <p className="num mt-1 text-[12.5px]">
            {total ? (
              <>
                {item.matched}
                <span className="text-muted"> / {total}</span>
              </>
            ) : (
              <span className="text-muted">—</span>
            )}
          </p>
          <p className="mt-0.5 text-[10.5px] text-muted">
            {item.mismatched ? `${item.mismatched} mismatched` : "all matched"}
            {item.critical ? ` · ${item.critical} critical` : ""}
            {item.warnings
              ? ` · ${item.warnings} warning${item.warnings === 1 ? "" : "s"}`
              : ""}
          </p>
        </div>
        <div className="text-right">
          <p className="label">{decided ? "Decided" : "Routed at"}</p>
          <p className="mono mt-1 text-[10.5px] text-muted">
            {decided ? formatDate(item.decided_at, true) : formatDate(item.created_at, true)}
          </p>
          {decided ? (
            <p className="mt-0.5 text-[10px] text-muted">
              {item.decided_by_email ?? "Admissions"}
            </p>
          ) : null}
        </div>
        <Link
          to={`/admin/applications/${item.application_id}`}
          aria-label={`Open ${item.reference}`}
          className="btn btn-secondary btn-sm"
        >
          Open
          <ArrowRight size={13} aria-hidden="true" />
        </Link>
      </div>
    </article>
  );
}

export function ReviewQueuePage() {
  const [tab, setTab] = useState<TabKey>("active");
  const queue = useQuery({
    queryKey: ["admin", "reviews", tab],
    queryFn: () => api.reviews(tab),
    refetchInterval: 15000,
  });

  const counts = queue.data?.counts;
  const items = queue.data?.items ?? [];
  const decided = (counts?.approved ?? 0) + (counts?.rejected ?? 0);

  return (
    <AppShell>
      <PageHeader
        title="Review queue"
        description="Every application the checker could not clear on its own, with the reasons it was routed here. Critical findings come first."
        actions={
          <Link to="/admin/audit">
            <Button variant="secondary" size="sm">
              <ScrollText size={14} aria-hidden="true" />
              Audit log
            </Button>
          </Link>
        }
      />

      <div className="grid gap-3 sm:grid-cols-3">
        <div className="stat">
          <p className="label">Awaiting first look</p>
          <p className="stat-value mt-2 text-accent-deep">
            {queue.isLoading ? "—" : counts?.open ?? 0}
          </p>
          <p className="mt-2 text-[12px] text-muted">Open items, not yet decided</p>
        </div>
        <div className="stat">
          <p className="label">In review</p>
          <p className="stat-value mt-2">{queue.isLoading ? "—" : counts?.in_review ?? 0}</p>
          <p className="mt-2 text-[12px] text-muted">Claimed by an admissions officer</p>
        </div>
        <div className="stat">
          <p className="label">Decided</p>
          <p className="stat-value mt-2 text-pass">{queue.isLoading ? "—" : decided}</p>
          <p className="mt-2 text-[12px] text-muted">
            {counts?.approved ?? 0} approved · {counts?.rejected ?? 0} rejected
          </p>
        </div>
      </div>

      <div className="mt-6">
        <SectionCard bodyClassName="p-0">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 pt-1">
            <div className="flex flex-wrap items-center" role="tablist" aria-label="Review status">
              {TABS.map((entry) => {
                const active = tab === entry.key;
                const count =
                  entry.key === "active"
                    ? counts?.active
                    : entry.key === "all"
                      ? counts?.all
                      : counts?.[entry.key];
                return (
                  <button
                    key={entry.key}
                    type="button"
                    role="tab"
                    aria-selected={active}
                    onClick={() => setTab(entry.key)}
                    className={clsx(
                      "relative px-3 py-3 text-[12.5px] font-medium transition-colors duration-150",
                      active ? "text-ink" : "text-muted hover:text-ink",
                    )}
                  >
                    {entry.label}
                    <span className="mono ml-1.5 text-[10.5px] font-normal text-muted">
                      {queue.isLoading ? "" : count ?? 0}
                    </span>
                    {active ? (
                      <span
                        className="absolute inset-x-2 bottom-0 h-[2px] bg-accent"
                        aria-hidden="true"
                      />
                    ) : null}
                  </button>
                );
              })}
            </div>
            <span className="inline-flex items-center gap-1.5 text-[11px] text-muted">
              {queue.isFetching && !queue.isLoading ? (
                <RefreshCw size={11} className="animate-spin" aria-hidden="true" />
              ) : (
                <span className="h-1.5 w-1.5 rounded-full bg-pass" aria-hidden="true" />
              )}
              Refreshes every 15 seconds
            </span>
          </div>

          {queue.isError ? (
            <div className="p-5">
              <Alert tone="error" title="The queue could not be loaded">
                <p>{queue.error instanceof Error ? queue.error.message : "Try again in a moment."}</p>
                <div className="mt-3">
                  <Button variant="secondary" size="sm" onClick={() => queue.refetch()}>
                    <RefreshCw size={13} aria-hidden="true" />
                    Try again
                  </Button>
                </div>
              </Alert>
            </div>
          ) : queue.isLoading ? (
            <div className="grid gap-3 p-5">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-[70%]" />
            </div>
          ) : items.length === 0 ? (
            <EmptyState
              icon={<ClipboardCheck size={19} aria-hidden="true" />}
              title={
                tab === "active"
                  ? "The queue is clear"
                  : tab === "approved"
                    ? "No approved reviews yet"
                    : tab === "rejected"
                      ? "No rejected reviews yet"
                      : "No review items yet"
              }
            >
              {tab === "active"
                ? "No application is waiting for a person. New validation runs land here automatically when a rule needs confirmation."
                : "Decisions appear here after an admissions officer approves or rejects a review. Every decision is kept in the audit log."}
            </EmptyState>
          ) : (
            <>
              <div className="divide-y divide-line xl:hidden">
                {items.map((item) => (
                  <QueueCard key={item.id} item={item} />
                ))}
              </div>
              <div className="hidden overflow-x-auto xl:block">
                <table className="data-table min-w-[940px]">
                  <thead>
                    <tr>
                      <th scope="col">Priority</th>
                      <th scope="col">Application</th>
                      <th scope="col">Routed because</th>
                      <th scope="col" className="text-right">
                        Marks
                      </th>
                      <th scope="col">Status</th>
                      <th scope="col">{tab === "active" ? "Routed at" : "Decided"}</th>
                      <th scope="col" aria-label="Open" />
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item) => (
                      <QueueRow key={item.id} item={item} />
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          <div className="flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-line px-5 py-3 text-[11px] text-muted">
            <span className="inline-flex items-center gap-1.5">
              <span className="h-[6px] w-[6px] rounded-[1px] bg-fail" aria-hidden="true" />
              Critical findings first
            </span>
            <span>Oldest first within a priority</span>
            <span>Every decision is appended to the audit log</span>
          </div>
        </SectionCard>
      </div>
    </AppShell>
  );
}
