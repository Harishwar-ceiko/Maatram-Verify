import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Loader2, RefreshCw, ScanText } from "lucide-react";
import { api, ApiError } from "../lib/api";
import type { ApplicationDetail, ExtractMark, Run } from "../lib/api";
import { ValidationTable } from "./ValidationTable";
import { Button, StatusBadge } from "./ui";
import { clsx } from "clsx";

function confidenceTone(confidence: number, floor: number): "pass" | "warn" {
  return confidence >= floor ? "pass" : "warn";
}

function ExtractedMarks({
  marks,
  engine,
  floor,
}: {
  marks: ExtractMark[];
  engine: string | null;
  floor: number;
}) {
  const average =
    marks.length > 0
      ? Math.round(marks.reduce((total, mark) => total + mark.confidence, 0) / marks.length)
      : 0;

  return (
    <div className="border-b border-line">
      <div className="flex flex-wrap items-center justify-between gap-x-5 gap-y-1 px-5 py-2.5">
        <h3 className="label">Read from the mark sheet</h3>
        <span className="mono text-[10.5px] text-muted">
          {marks.length} row{marks.length === 1 ? "" : "s"} · {average}% mean confidence
          {engine ? ` · ${engine}` : ""}
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">Subject as read</th>
              <th scope="col" className="text-right">
                Mark
              </th>
              <th scope="col" className="text-right">
                Out of
              </th>
              <th scope="col" className="w-[132px] text-right">
                Confidence
              </th>
            </tr>
          </thead>
          <tbody>
            {marks.map((mark) => {
              const effectiveSubject =
                mark.corrected_subject ?? mark.subject_norm ?? mark.subject_raw;
              const effectiveMark = mark.corrected_marks ?? mark.marks_obtained;
              const tone = confidenceTone(mark.confidence, floor);
              return (
                <tr key={mark.id}>
                  <td>
                    <span className="font-medium">{effectiveSubject}</span>
                    {mark.corrected_subject && mark.corrected_subject !== mark.subject_raw ? (
                      <span className="ml-2 text-[10px] text-accent">corrected</span>
                    ) : null}
                    {mark.subject_raw !== effectiveSubject ? (
                      <span className="mono mt-0.5 block text-[10px] text-muted">
                        printed &ldquo;{mark.subject_raw}&rdquo;
                      </span>
                    ) : null}
                  </td>
                  <td className="num">
                    {effectiveMark ?? "—"}
                    {mark.corrected_marks !== null ? (
                      <span className="ml-1.5 text-[10px] text-accent">corrected</span>
                    ) : null}
                  </td>
                  <td className="num text-muted">{mark.max_marks ?? "—"}</td>
                  <td>
                    <div className="flex items-center justify-end gap-2">
                      <span
                        className={clsx(
                          "h-[3px] w-10 overflow-hidden rounded-full bg-paper-deep",
                          tone === "warn" && "bg-warn-wash",
                        )}
                        aria-hidden="true"
                      >
                        <span
                          className={clsx(
                            "block h-full",
                            tone === "pass" ? "bg-pass" : "bg-warn",
                          )}
                          style={{ width: `${Math.max(4, Math.min(100, mark.confidence))}%` }}
                        />
                      </span>
                      <span
                        className={clsx(
                          "mono w-9 text-right text-[10.5px]",
                          tone === "pass" ? "text-muted" : "text-warn",
                        )}
                      >
                        {Math.round(mark.confidence)}%
                      </span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function ValidationPanel({
  application,
  readOnly,
}: {
  application: ApplicationDetail;
  readOnly?: boolean;
}) {
  const queryClient = useQueryClient();
  const config = useQuery({ queryKey: ["config"], queryFn: api.config });
  const floor = config.data?.ocr.low_confidence ?? 62;

  const run = application.latest_run;
  const running = run?.status === "pending" || run?.status === "running";
  const hasMarksheet = application.documents.some((document) => document.kind === "marksheet");
  const hasPhoto = application.documents.some((document) => document.kind === "photo");
  const blocker = !hasMarksheet
    ? "Attach a mark sheet to run the checks."
    : !hasPhoto
      ? "Attach a profile photograph to run the checks."
      : null;

  const mutation = useMutation({
    mutationFn: () => api.validateApplication(application.id),
    onSuccess: (nextRun: Run) => {
      queryClient.setQueryData<ApplicationDetail>(["application", String(application.id)], (prev) =>
        prev ? { ...prev, latest_run: nextRun, status: "processing" } : prev,
      );
      void queryClient.invalidateQueries({ queryKey: ["application", String(application.id)] });
      void queryClient.invalidateQueries({ queryKey: ["application", application.id] });
      void queryClient.invalidateQueries({ queryKey: ["applications"] });
      void queryClient.invalidateQueries({ queryKey: ["admin", "overview"] });
    },
  });

  const error =
    mutation.error instanceof ApiError
      ? mutation.error.detail
      : mutation.error
        ? "The checks could not be started."
        : null;

  return (
    <section className="card">
      <div className="card-head">
        <h2 className="section-title">Validation report</h2>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          {run ? <StatusBadge value={run.overall ?? run.status} /> : (
            <span className="text-[11px] text-muted">Not run</span>
          )}
          {readOnly ? null : (
            <Button
              size="sm"
              variant={run ? "secondary" : "primary"}
              onClick={() => mutation.mutate()}
              disabled={Boolean(blocker) || running}
              busy={running || mutation.isPending}
              title={blocker ?? undefined}
            >
              {!running && !mutation.isPending ? (
                run ? (
                  <RefreshCw size={13} aria-hidden="true" />
                ) : (
                  <ScanText size={13} aria-hidden="true" />
                )
              ) : null}
              {running ? "Running checks" : run ? "Re-run checks" : "Run checks"}
            </Button>
          )}
        </div>
      </div>

      {blocker && !readOnly ? (
        <div className="flex items-start gap-2.5 border-b border-line bg-paper-deep/35 px-5 py-3">
          <AlertTriangle size={14} className="mt-0.5 shrink-0 text-warn" aria-hidden="true" />
          <p className="text-[11.5px] leading-relaxed text-ink-soft">
            {blocker} Checks compare every entered subject with the sheet, then read the
            photograph and identity fields.
          </p>
        </div>
      ) : null}

      {running ? (
        <div className="flex items-center gap-2.5 border-b border-line bg-warn-wash/50 px-5 py-2.5">
          <Loader2 size={14} className="animate-spin text-warn" aria-hidden="true" />
          <p className="text-[11.5px] leading-relaxed text-warn">
            Reading the documents at 300 DPI. Results appear here as soon as the run finishes;
            this page refreshes on its own.
          </p>
        </div>
      ) : null}

      {error ? (
        <div className="border-b border-fail/30 bg-fail-wash/60 px-5 py-2.5" role="alert">
          <p className="text-[11.5px] leading-relaxed text-fail">{error}</p>
        </div>
      ) : null}

      {application.extracted_marks.length > 0 ? (
        <ExtractedMarks
          marks={application.extracted_marks}
          engine={
            typeof run?.summary?.engine === "string" ? String(run.summary.engine) : null
          }
          floor={floor}
        />
      ) : null}

      <ValidationTable run={run} />
    </section>
  );
}
