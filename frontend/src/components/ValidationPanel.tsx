import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, Loader2, Pencil, RefreshCw, ScanText, X } from "lucide-react";
import { api, ApiError } from "../lib/api";
import type { ApplicationDetail, ExtractMark, Run } from "../lib/api";
import { ValidationTable } from "./ValidationTable";
import { Button, StatusBadge } from "./ui";
import { clsx } from "clsx";

function confidenceTone(confidence: number, floor: number): "pass" | "warn" {
  return confidence >= floor ? "pass" : "warn";
}

function ExtractedMarks({
  application,
  marks,
  engine,
  floor,
  canCorrect,
}: {
  application: ApplicationDetail;
  marks: ExtractMark[];
  engine: string | null;
  floor: number;
  canCorrect: boolean;
}) {
  const queryClient = useQueryClient();
  const [editingId, setEditingId] = useState<number | null>(null);
  const [subject, setSubject] = useState("");
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  const average =
    marks.length > 0
      ? Math.round(marks.reduce((total, mark) => total + mark.confidence, 0) / marks.length)
      : 0;

  const correction = useMutation({
    mutationFn: ({
      mark,
      subject,
      marks,
    }: {
      mark: ExtractMark;
      subject: string;
      marks: number;
    }) =>
      api.correctExtractedMark(mark.document_id, mark.id, {
        subject: subject.trim() || null,
        marks_obtained: marks,
      }),
    onSuccess: async (result) => {
      setEditingId(null);
      setError(null);
      const pending: Run = {
        id: result.run.id,
        status: "pending",
        overall: null,
        summary: {},
        error: null,
        started_at: null,
        finished_at: null,
        findings: [],
      };
      const patch = (previous: ApplicationDetail | undefined) =>
        previous
          ? { ...previous, status: "processing" as const, latest_run: pending }
          : previous;
      queryClient.setQueryData<ApplicationDetail>(
        ["application", String(application.id)],
        patch,
      );
      queryClient.setQueryData<ApplicationDetail>(["application", application.id], patch);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["application"] }),
        queryClient.invalidateQueries({ queryKey: ["applications"] }),
        queryClient.invalidateQueries({ queryKey: ["admin"] }),
      ]);
    },
    onError: (caught) => {
      setError(
        caught instanceof ApiError
          ? caught.detail
          : "The correction could not be saved.",
      );
    },
  });

  function start(mark: ExtractMark) {
    setEditingId(mark.id);
    setSubject(mark.corrected_subject ?? mark.subject_raw);
    setValue(String(mark.corrected_marks ?? mark.marks_obtained ?? ""));
    setError(null);
  }

  function save(mark: ExtractMark) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric) || numeric < 0) {
      setError("Enter a mark of zero or more.");
      return;
    }
    if (mark.max_marks !== null && numeric > mark.max_marks) {
      setError(`The mark cannot be above the ${mark.max_marks} maximum printed on the sheet.`);
      return;
    }
    correction.mutate({ mark, subject, marks: numeric });
  }

  return (
    <div className="border-b border-line">
      <div className="flex flex-wrap items-center justify-between gap-x-5 gap-y-1 px-5 py-2.5">
        <h3 className="label">Read from the mark sheet</h3>
        <span className="mono text-[10.5px] text-muted">
          {marks.length} row{marks.length === 1 ? "" : "s"} · {average}% mean confidence
          {engine ? ` · ${engine}` : ""}
        </span>
      </div>
      {canCorrect ? (
        <p className="border-t border-line bg-paper-deep/35 px-5 py-2 text-[11px] leading-relaxed text-muted">
          A correction is stored beside the OCR value and logged. Saving it starts a fresh
          validation run so the comparison reflects what a person confirmed.
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="border-t border-fail/30 bg-fail-wash/60 px-5 py-2 text-[11px] text-fail">
          {error}
        </p>
      ) : null}
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
              <th scope="col" className={clsx("text-right", canCorrect ? "w-[112px]" : "w-[132px]")}>
                Confidence
              </th>
              {canCorrect ? (
                <th scope="col" className="w-[92px] text-right">
                  Correct
                </th>
              ) : null}
            </tr>
          </thead>
          <tbody>
            {marks.map((mark) => {
              const effectiveSubject =
                mark.corrected_subject ?? mark.subject_norm ?? mark.subject_raw;
              const effectiveMark = mark.corrected_marks ?? mark.marks_obtained;
              const tone = confidenceTone(mark.confidence, floor);
              const editing = canCorrect && editingId === mark.id;
              return (
                <tr key={mark.id}>
                  <td>
                    {editing ? (
                      <input
                        className="input w-full max-w-[190px]"
                        value={subject}
                        maxLength={160}
                        aria-label={`Corrected subject for ${mark.subject_raw}`}
                        onChange={(event) => setSubject(event.target.value)}
                      />
                    ) : (
                      <>
                        <span className="font-medium">{effectiveSubject}</span>
                        {mark.corrected_subject && mark.corrected_subject !== mark.subject_raw ? (
                          <span className="ml-2 text-[10px] text-accent">corrected</span>
                        ) : null}
                        {mark.subject_raw !== effectiveSubject ? (
                          <span className="mono mt-0.5 block text-[10px] text-muted">
                            printed &ldquo;{mark.subject_raw}&rdquo;
                          </span>
                        ) : null}
                      </>
                    )}
                  </td>
                  <td className="num">
                    {editing ? (
                      <input
                        className="input mono ml-auto w-[74px] text-right"
                        type="number"
                        min={0}
                        max={mark.max_marks ?? undefined}
                        step="0.5"
                        value={value}
                        aria-label={`Corrected mark for ${mark.subject_raw}`}
                        onChange={(event) => setValue(event.target.value)}
                      />
                    ) : (
                      <>
                        {effectiveMark ?? "—"}
                        {mark.corrected_marks !== null ? (
                          <span className="ml-1.5 text-[10px] text-accent">corrected</span>
                        ) : null}
                      </>
                    )}
                  </td>
                  <td className="num text-muted">{mark.max_marks ?? "—"}</td>
                  <td>
                    {editing ? (
                      <span className="block text-right text-[10.5px] text-muted">
                        re-runs checks
                      </span>
                    ) : (
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
                    )}
                  </td>
                  {canCorrect ? (
                    <td className="text-right align-top">
                      {editing ? (
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            size="sm"
                            variant="primary"
                            type="button"
                            onClick={() => save(mark)}
                            busy={correction.isPending}
                            title="Save the correction and re-run the checks"
                          >
                            {correction.isPending ? null : <Check size={13} aria-hidden="true" />}
                            Save
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            type="button"
                            onClick={() => {
                              setEditingId(null);
                              setError(null);
                            }}
                            disabled={correction.isPending}
                            title="Discard this correction"
                          >
                            <X size={13} aria-hidden="true" />
                            <span className="sr-only">Cancel</span>
                          </Button>
                        </div>
                      ) : (
                        <Button
                          size="sm"
                          variant="ghost"
                          type="button"
                          onClick={() => start(mark)}
                          title={`Correct ${effectiveSubject}`}
                        >
                          <Pencil size={12} aria-hidden="true" />
                          Edit
                        </Button>
                      )}
                    </td>
                  ) : null}
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
  canCorrect,
}: {
  application: ApplicationDetail;
  readOnly?: boolean;
  canCorrect?: boolean;
}) {
  const queryClient = useQueryClient();
  const config = useQuery({ queryKey: ["config"], queryFn: api.config });
  const floor = config.data?.ocr.low_confidence ?? 62;

  const run = application.latest_run;
  const running = run?.status === "pending" || run?.status === "running";
  const hasClass12 = application.documents.some(
    (document) => document.kind === "marksheet_12" || document.kind === "marksheet",
  );
  const hasPhoto = application.documents.some((document) => document.kind === "photo");
  const blocker = !hasClass12
    ? "Attach a Class 12 mark sheet to run the checks."
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
            {blocker} Checks compare every entered subject with its class sheet, then read the
            photograph and each attached certificate.
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
          application={application}
          marks={application.extracted_marks}
          engine={
            typeof run?.summary?.engine === "string" ? String(run.summary.engine) : null
          }
          floor={floor}
          canCorrect={Boolean(canCorrect)}
        />
      ) : null}

      <ValidationTable run={run} />
    </section>
  );
}
