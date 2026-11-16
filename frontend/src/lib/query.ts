import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export function formatDate(value: string | null | undefined, withTime = false): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  }).format(date);
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  submitted: "Submitted",
  processing: "Processing",
  needs_review: "Needs review",
  verified: "Verified",
  approved: "Approved",
  rejected: "Rejected",
  match: "Match",
  mismatch: "Mismatch",
  pass: "Pass",
  fail: "Fail",
  pending: "Pending",
  missing_upload: "Missing in upload",
  missing_entry: "Missing in entry",
  skipped: "Skipped",
  review: "Review",
  completed: "Completed",
  open: "Open",
  in_review: "In review",
};

export function statusLabel(value: string): string {
  return STATUS_LABELS[value] ?? value.replaceAll("_", " ");
}
