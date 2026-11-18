import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, X } from "lucide-react";
import type { ApplicationDetail } from "../lib/api";
import { api, ApiError } from "../lib/api";
import { formatDate } from "../lib/query";
import { Button, SectionCard, StatusBadge } from "./ui";

export function ReviewPanel({ application }: { application: ApplicationDetail }) {
  const review = application.review;
  const queryClient = useQueryClient();
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (decision: "approve" | "reject") =>
      api.decideReview(review?.id ?? 0, decision, comment),
    onSuccess: async () => {
      setComment("");
      setError(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["application"] }),
        queryClient.invalidateQueries({ queryKey: ["admin"] }),
      ]);
    },
    onError: (caught) => {
      setError(caught instanceof ApiError ? caught.message : "The decision was not saved.");
    },
  });

  if (!review) return null;

  const decided = review.status === "approved" || review.status === "rejected";
  const critical = review.priority <= 20;
  const tooShort = comment.trim().length < 3;

  return (
    <SectionCard
      title="Review decision"
      aside={
        <span className="inline-flex items-center gap-2 text-[11px] text-muted">
          <span
            className={`h-[7px] w-[7px] rounded-[1px] ${critical ? "bg-fail" : "bg-warn"}`}
            aria-hidden="true"
          />
          {critical ? "Priority · critical finding" : "Priority · warning finding"}
        </span>
      }
      bodyClassName="p-0"
    >
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 p-5">
          <p className="label">Why the checker routed it</p>
          {review.reasons.length > 0 ? (
            <ul className="mt-3 grid gap-2.5">
              {review.reasons.map((reason, index) => (
                <li
                  key={`${index}-${reason}`}
                  className="flex items-start gap-2.5 text-[12.5px] leading-relaxed text-ink-soft"
                >
                  <span
                    className="mt-[6px] h-[6px] w-[6px] flex-none rounded-[1px] bg-accent"
                    aria-hidden="true"
                  />
                  <span>{reason}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-[12.5px] text-muted">No reason was stored with this item.</p>
          )}
          <p className="mt-4 max-w-[58ch] text-[11.5px] leading-relaxed text-muted">
            Compare these against the documents and the extracted values below. Approving marks the
            application approved; rejecting marks it rejected. Either way the note and your name go
            into the append-only audit log.
          </p>
        </div>

        <div className="border-t border-line p-5 lg:border-l lg:border-t-0">
          {decided ? (
            <div>
              <div className="flex items-center justify-between gap-3">
                <p className="label">Recorded decision</p>
                <StatusBadge value={review.status} />
              </div>
              <p className="mt-3 text-[12.5px] leading-relaxed text-ink-soft">
                {review.decision_comment}
              </p>
              <p className="mt-3 text-[11px] leading-relaxed text-muted">
                {review.decided_by_email ?? "An admissions officer"} ·{" "}
                {formatDate(review.decided_at, true)}
              </p>
            </div>
          ) : (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                mutation.mutate("approve");
              }}
            >
              <label className="field-label" htmlFor="review-comment">
                Decision note
              </label>
              <textarea
                id="review-comment"
                className="textarea mt-1.5 min-h-[96px]"
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                placeholder="What did you check against the original?"
                aria-invalid={error ? true : undefined}
              />
              <p className="field-hint mt-1.5">
                Required. Recorded with your name and the time in the audit log.
              </p>
              {error ? (
                <p className="field-error" role="alert">
                  {error}
                </p>
              ) : null}
              <div className="mt-3 flex flex-wrap gap-2">
                <Button
                  type="submit"
                  size="sm"
                  busy={mutation.isPending && mutation.variables === "approve"}
                  disabled={tooShort || mutation.isPending}
                >
                  <Check size={14} aria-hidden="true" />
                  Approve record
                </Button>
                <Button
                  type="button"
                  variant="danger"
                  size="sm"
                  busy={mutation.isPending && mutation.variables === "reject"}
                  disabled={tooShort || mutation.isPending}
                  onClick={() => mutation.mutate("reject")}
                >
                  <X size={14} aria-hidden="true" />
                  Reject
                </Button>
              </div>
            </form>
          )}
        </div>
      </div>
    </SectionCard>
  );
}
