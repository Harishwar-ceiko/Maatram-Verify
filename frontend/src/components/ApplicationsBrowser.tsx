import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Plus, Search } from "lucide-react";
import { ApplicationsTable } from "./ApplicationsTable";
import { Button, Skeleton } from "./ui";
import { api } from "../lib/api";
import { STATUS_LABELS } from "../lib/query";

const STATUSES = ["submitted", "processing", "needs_review", "verified", "approved", "rejected"];

export function ApplicationsBrowser({ admin }: { admin?: boolean }) {
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [status, setStatus] = useState("");

  const applications = useQuery({
    queryKey: ["applications", admin ? "all" : "mine", submitted, status],
    queryFn: () =>
      api.applications({
        q: submitted || undefined,
        status: status || undefined,
        page_size: 100,
      }),
  });

  const items = applications.data?.items ?? [];
  const total = applications.data?.total ?? 0;
  const filtered = Boolean(submitted || status);

  return (
    <div className="grid grid-cols-1 gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <form
          className="flex flex-1 flex-wrap items-center gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            setSubmitted(query.trim());
          }}
        >
          <div className="relative min-w-[220px] flex-1 sm:max-w-[340px]">
            <Search
              size={15}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted"
              aria-hidden="true"
            />
            <input
              className="input pl-9"
              placeholder="Reference, name or register number"
              aria-label="Search applications"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          <select
            className="select w-auto min-w-[160px]"
            aria-label="Filter by status"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="">All statuses</option>
            {STATUSES.map((value) => (
              <option key={value} value={value}>
                {STATUS_LABELS[value]}
              </option>
            ))}
          </select>
          <Button type="submit" variant="secondary" className="h-[42px]">
            Search
          </Button>
          {filtered ? (
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => {
                setQuery("");
                setSubmitted("");
                setStatus("");
              }}
            >
              Clear
            </button>
          ) : null}
        </form>

        {admin ? null : (
          <Link to="/applications/new">
            <Button>
              <Plus size={15} aria-hidden="true" />
              New application
            </Button>
          </Link>
        )}
      </div>

      <div className="card overflow-hidden">
        <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-3">
          <p className="text-[12.5px] text-muted">
            {applications.isLoading
              ? "Reading applications"
              : `${total} application${total === 1 ? "" : "s"}${filtered ? " matched" : ""}`}
          </p>
          {filtered && !applications.isLoading ? (
            <p className="text-[11.5px] text-faint">Filters applied</p>
          ) : null}
        </div>

        {applications.isLoading ? (
          <div className="grid gap-3 p-5">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-[75%]" />
          </div>
        ) : (
          <ApplicationsTable
            items={items}
            admin={admin}
            emptyAction={
              filtered ? (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setQuery("");
                    setSubmitted("");
                    setStatus("");
                  }}
                >
                  Clear filters
                </Button>
              ) : admin ? undefined : (
                <Link to="/applications/new">
                  <Button size="sm">Start an application</Button>
                </Link>
              )
            }
          />
        )}
      </div>
    </div>
  );
}
