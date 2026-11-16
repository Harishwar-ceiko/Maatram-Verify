import { useQuery } from "@tanstack/react-query";
import { ScrollText } from "lucide-react";
import { AppShell } from "../../components/AppShell";
import { EmptyState, PageHeader, SectionCard, Skeleton } from "../../components/ui";
import { api } from "../../lib/api";
import { formatDate } from "../../lib/query";

export function AuditPage() {
  const audit = useQuery({ queryKey: ["admin", "audit"], queryFn: () => api.audit() });
  const items = audit.data?.items ?? [];

  return (
    <AppShell>
      <PageHeader
        title="Audit log"
        description="Every sign-in, upload, correction and decision, in the order it happened. Entries are never edited."
      />

      <SectionCard
        title="Recent activity"
        aside={<span className="mono text-[11px] text-muted">{audit.data?.total ?? 0} entries</span>}
        bodyClassName="p-0"
      >
        {audit.isLoading ? (
          <div className="grid gap-3 p-5">
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-[65%]" />
          </div>
        ) : items.length === 0 ? (
          <EmptyState icon={<ScrollText size={19} aria-hidden="true" />} title="No entries recorded">
            Actions are logged as soon as anyone signs in or touches an application.
          </EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">When</th>
                  <th scope="col">Action</th>
                  <th scope="col">Actor</th>
                  <th scope="col">Entity</th>
                  <th scope="col">Detail</th>
                </tr>
              </thead>
              <tbody>
                {items.map((entry) => (
                  <tr key={entry.id}>
                    <td className="mono whitespace-nowrap text-[11.5px] text-muted">
                      {formatDate(entry.created_at, true)}
                    </td>
                    <td>
                      <span className="mono text-[11.5px]">{entry.action}</span>
                    </td>
                    <td className="text-[12px]">{entry.actor_email ?? "system"}</td>
                    <td className="mono text-[11.5px] text-muted">
                      {entry.entity_type}
                      {entry.entity_id ? ` #${entry.entity_id}` : ""}
                    </td>
                    <td className="max-w-[280px] truncate text-[11.5px] text-muted">
                      {Object.entries(entry.detail ?? {})
                        .map(([key, value]) => `${key}: ${String(value)}`)
                        .join(" · ") || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </AppShell>
  );
}
