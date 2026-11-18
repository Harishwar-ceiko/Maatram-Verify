import { Link } from "react-router-dom";
import { ChevronRight, FileText } from "lucide-react";
import type { Application } from "../lib/api";
import { formatDate } from "../lib/query";
import { EmptyState, StatusBadge } from "./ui";

export function ApplicationsTable({
  items,
  admin,
  emptyAction,
}: {
  items: Application[];
  admin?: boolean;
  emptyAction?: React.ReactNode;
}) {
  if (items.length === 0) {
    return (
      <EmptyState
        icon={<FileText size={19} aria-hidden="true" />}
        title="No applications yet"
        action={emptyAction}
      >
        {admin
          ? "Nothing has been filed in this view. Adjust the filters or wait for the next submission."
          : "File your first application. Enter your details and marks, attach the documents, and the checker does the rest."}
      </EmptyState>
    );
  }

  return (
    <>
      <div className="hidden overflow-x-auto md:block">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">Reference</th>
              <th scope="col">Class 12</th>
              {admin ? <th scope="col">Applicant</th> : null}
              <th scope="col">Submitted</th>
              <th scope="col">Status</th>
              <th scope="col" className="w-10">
                <span className="sr-only">Open</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((application) => {
              const class12 = application.classes.find(
                (record) => record.class_level === 12,
              );
              return (
                <tr key={application.id}>
                  <td>
                    <Link
                      to={`${admin ? "/admin" : ""}/applications/${application.id}`}
                      className="mono text-[12.5px] font-medium underline decoration-transparent underline-offset-4 transition-colors duration-150 hover:decoration-line-strong"
                    >
                      {application.reference}
                    </Link>
                  </td>
                  <td className="max-w-[220px]">
                    {class12 ? (
                      <>
                        <span className="block">{class12.exam_year}</span>
                        <span className="mono block text-[11px] text-muted">
                          {class12.register_number}
                        </span>
                      </>
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </td>
                  {admin ? (
                    <td>
                      <span className="block truncate">{application.applicant_name}</span>
                    </td>
                  ) : null}
                  <td className="whitespace-nowrap text-muted">
                    {formatDate(application.created_at)}
                  </td>
                  <td>
                    <StatusBadge value={application.status} />
                  </td>
                  <td>
                    <Link
                      to={`${admin ? "/admin" : ""}/applications/${application.id}`}
                      className="grid h-8 w-8 place-items-center rounded-[2px] text-muted transition-colors duration-150 hover:bg-paper-deep hover:text-ink"
                      aria-label={`Open ${application.reference}`}
                    >
                      <ChevronRight size={16} aria-hidden="true" />
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <ul className="grid gap-3 p-4 md:hidden">
        {items.map((application) => {
          const class12 = application.classes.find((record) => record.class_level === 12);
          return (
            <li key={application.id}>
              <Link
                to={`${admin ? "/admin" : ""}/applications/${application.id}`}
                className="block rounded-[2px] border border-line bg-raised p-4 transition-colors duration-150 hover:border-line-strong"
              >
                <span className="flex items-start justify-between gap-3">
                  <span className="mono text-[12px] text-muted">{application.reference}</span>
                  <StatusBadge value={application.status} />
                </span>
                <span className="mt-2 block text-[14px] font-medium leading-snug">
                  {admin
                    ? application.applicant_name
                    : `Class 12 · ${class12?.exam_year ?? "—"}`}
                </span>
                <span className="mt-1 flex items-center justify-between gap-3 text-[12px] text-muted">
                  <span>
                    {admin ? `Class 12 · ${class12?.exam_year ?? "—"} · ` : ""}
                    {formatDate(application.created_at)}
                  </span>
                  <ChevronRight size={14} aria-hidden="true" />
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </>
  );
}
