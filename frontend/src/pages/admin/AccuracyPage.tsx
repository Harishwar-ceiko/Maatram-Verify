import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Gauge, RefreshCw } from "lucide-react";
import { AppShell } from "../../components/AppShell";
import {
  Alert,
  Button,
  EmptyState,
  PageHeader,
  SectionCard,
  Skeleton,
} from "../../components/ui";
import { api, type AccuracyClassification, type AccuracySummary } from "../../lib/api";

function pct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function duration(ms: number | null | undefined): string {
  if (!ms) return "—";
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

function stamp(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function TargetStat({
  label,
  value,
  target,
  met,
  detail,
}: {
  label: string;
  value: number;
  target: number;
  met: boolean;
  detail: string;
}) {
  return (
    <div className="stat">
      <div className="flex items-start justify-between gap-3">
        <p className="label">{label}</p>
        <span className={`status ${met ? "status-pass" : "status-fail"}`}>
          <span className="status-mark" aria-hidden="true" />
          {met ? "Target met" : "Below target"}
        </span>
      </div>
      <p className="stat-value mt-2">{pct(value)}</p>
      <p className="mt-2 text-[11.5px] leading-relaxed text-muted">
        Target {pct(target)} · {detail}
      </p>
    </div>
  );
}

function MetricRow({
  label,
  detail,
  values,
}: {
  label: string;
  detail: string;
  values: { precision: number; recall: number; f1: number; tp: number; fp: number; fn: number };
}) {
  return (
    <tr>
      <td>
        <span className="font-medium">{label}</span>
        <span className="mt-0.5 block max-w-[46ch] text-[10.5px] leading-relaxed text-muted">
          {detail}
        </span>
      </td>
      <td className="num">{pct(values.precision)}</td>
      <td className="num">{pct(values.recall)}</td>
      <td className="num">{pct(values.f1)}</td>
      <td className="num">
        {values.tp} / {values.fp} / {values.fn}
      </td>
    </tr>
  );
}

function Matrix({ summary }: { summary: AccuracySummary }) {
  const matrix = summary.mismatch.matrix;
  const cells = [
    { label: "Correctly flagged", value: matrix.tp, tone: "text-pass" },
    { label: "False alarms", value: matrix.fp, tone: "text-fail" },
    { label: "Missed", value: matrix.fn, tone: "text-warn" },
    { label: "Correctly cleared", value: matrix.tn, tone: "text-pass" },
  ];
  return (
    <div className="mt-5 border border-line">
      <div className="grid grid-cols-2 gap-px bg-line">
        {cells.map((cell) => (
          <div key={cell.label} className="bg-surface px-3.5 py-3">
            <p className="text-[10.5px] leading-tight text-muted">{cell.label}</p>
            <p className={`mt-1 font-serif text-[24px] leading-none ${cell.tone}`}>
              {cell.value}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function ConfusionMatrix({
  classification,
}: {
  classification: AccuracyClassification;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="data-table min-w-[560px]">
        <thead>
          <tr>
            <th scope="col">Printed \ read as</th>
            {classification.labels.map((label) => (
              <th key={label.kind} scope="col" className="text-right">
                {label.short}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {classification.labels.map((label, rowIndex) => (
            <tr key={label.kind}>
              <td className="font-medium">{label.label}</td>
              {classification.matrix[rowIndex].map((count, columnIndex) => (
                <td
                  key={classification.labels[columnIndex].kind}
                  className={
                    rowIndex === columnIndex
                      ? count > 0
                        ? "num text-pass"
                        : "num text-muted"
                      : count > 0
                        ? "num text-warn"
                        : "num text-muted"
                  }
                >
                  {count}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RunDetails({ summary }: { summary: AccuracySummary }) {
  const rows = [
    ["Dataset", summary.dataset],
    [
      "Mark sheets",
      summary.mark_sheets
        ? `${summary.cases} · ${summary.mark_sheets.class_11} × Class 11`
        : String(summary.cases),
    ],
    [
      "Supporting documents",
      summary.documents ? String(summary.documents.fixtures) : "—",
    ],
    [
      "Classified correctly",
      summary.classification
        ? `${summary.classification.correct}/${summary.classification.total}`
        : "—",
    ],
    ["Mean OCR confidence", `${summary.ocr_confidence}%`],
    ["Mean read time", duration(summary.mean_duration_ms)],
    ["Finished", stamp(summary.finished_at)],
  ];
  return (
    <dl className="grid gap-2.5 text-[12px]">
      {rows.map(([label, value]) => (
        <div key={label} className="flex items-baseline justify-between gap-4">
          <dt className="text-muted">{label}</dt>
          <dd className="mono text-right text-[11.5px] text-ink-soft">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function AccuracyPage() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["admin", "accuracy"],
    queryFn: api.accuracy,
    refetchInterval: (query) => (query.state.data?.running ? 2500 : false),
  });
  const mutation = useMutation({
    mutationFn: api.runAccuracy,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "accuracy"] });
    },
  });

  const latest = query.data?.latest;
  const summary = latest?.summary;
  const running = Boolean(query.data?.running) || summary?.status === "running" || mutation.isPending;
  const failed = summary?.status === "failed";
  const error =
    mutation.error instanceof Error
      ? mutation.error.message
      : query.error instanceof Error
        ? query.error.message
        : null;

  const runButton = (
    <Button
      variant={latest ? "secondary" : "primary"}
      onClick={() => mutation.mutate()}
      disabled={running}
      busy={running}
    >
      {!running ? <RefreshCw size={14} aria-hidden="true" /> : null}
      {running ? "Running evaluation" : latest ? "Run again" : "Run evaluation"}
    </Button>
  );

  return (
    <AppShell>
      <PageHeader
        title="Accuracy"
        description="The pipeline measured against synthetic documents whose ground truth is known. No real student documents are ever used."
        actions={latest ? runButton : undefined}
      />

      {error ? (
        <div className="mb-5">
          <Alert tone="error" title="Evaluation could not be loaded">
            {error}
          </Alert>
        </div>
      ) : null}

      {query.isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <Skeleton className="h-[132px] w-full" />
          <Skeleton className="h-[132px] w-full" />
          <Skeleton className="h-[132px] w-full" />
        </div>
      ) : !latest ? (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
          <SectionCard bodyClassName="p-0">
            <EmptyState
              icon={<Gauge size={19} aria-hidden="true" />}
              title="No evaluation run yet"
              action={runButton}
            >
              Run the generator and evaluator once. This page then shows field-level extraction
              accuracy for mark sheets and supporting documents, mismatch precision and recall,
              photo-rule accuracy, the document-type confusion matrix and the cases that need
              attention.
            </EmptyState>
          </SectionCard>
          <aside className="grid content-start gap-5">
            <div className="card-flat p-5">
              <p className="text-[13px] font-medium">What gets measured</p>
              <ul className="mt-3 grid gap-2 text-[12px] leading-relaxed text-muted">
                <li>Name, register number and examination year extraction.</li>
                <li>Subject rows and obtained marks, against the printed values.</li>
                <li>Class 11 and Class 12 statements, scored side by side.</li>
                <li>Mismatch detection, against injected entry errors.</li>
                <li>Aadhaar name, birth detail, last four digits and Verhoeff checksum.</li>
                <li>Income, community and first-graduate certificate fields.</li>
                <li>Every photo rule, against labelled perturbations.</li>
                <li>Document-type classification, as a confusion matrix.</li>
              </ul>
            </div>
            <div className="card-flat bg-paper-deep/50 p-5">
              <p className="text-[12px] leading-relaxed text-muted">
                The run writes a copy to{" "}
                <span className="mono text-[11px]">reports/accuracy.md</span> and keeps the summary
                with the run.
              </p>
            </div>
          </aside>
        </div>
      ) : running ? (
        <div className="card px-5 py-10">
          <div className="mx-auto flex max-w-[46ch] flex-col items-center text-center">
            <span className="grid h-10 w-10 place-items-center rounded-[2px] bg-warn-wash text-warn">
              <Gauge size={19} className="animate-pulse" aria-hidden="true" />
            </span>
            <p className="mt-4 text-[15px] font-semibold">Reading the synthetic set</p>
            <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted">
              Tesseract is reading each mark sheet, then the comparison and photo rules are scored
              against ground truth. This usually finishes in under a minute.
            </p>
            <p className="mt-4 text-[11px] text-muted">
              Started {stamp(summary?.started_at ?? latest.created_at)} · {latest.total_cases || 30}{" "}
              mark sheets plus supporting documents
            </p>
          </div>
        </div>
      ) : failed ? (
        <Alert tone="error" title="The evaluation stopped">
          {summary.error ?? "Unknown error"}
        </Alert>
      ) : summary ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <TargetStat
              label="Field extraction"
              value={summary.field_accuracy}
              target={summary.targets.field_accuracy.target}
              met={summary.targets.field_accuracy.met}
              detail="name, register and year"
            />
            {summary.documents && summary.targets.document_field_accuracy ? (
              <TargetStat
                label="Document fields"
                value={summary.documents.field_accuracy}
                target={summary.targets.document_field_accuracy.target}
                met={summary.targets.document_field_accuracy.met}
                detail={`${summary.documents.fields_correct}/${summary.documents.fields_total} printed values`}
              />
            ) : null}
            <TargetStat
              label="Mismatch recall"
              value={summary.mismatch.recall}
              target={summary.targets.mismatch_recall.target}
              met={summary.targets.mismatch_recall.met}
              detail={`${summary.mismatch.tp} injected mismatches found`}
            />
            <TargetStat
              label="Photo rule accuracy"
              value={summary.photos.rule_accuracy}
              target={summary.targets.photo_rule_accuracy.target}
              met={summary.targets.photo_rule_accuracy.met}
              detail={`${summary.photos.labels_correct}/${summary.photos.labels_total} labelled outcomes`}
            />
          </div>

          <div className="mt-6 grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
            <div className="grid min-w-0 gap-6">
              <SectionCard
                title="Extraction by degradation"
                aside={
                  <span className="text-[11px] text-muted">{summary.cases} mark sheets</span>
                }
                bodyClassName="p-0"
              >
                <div className="overflow-x-auto">
                  <table className="data-table min-w-[620px]">
                    <thead>
                      <tr>
                        <th scope="col">Variant</th>
                        <th scope="col" className="text-right">
                          Cases
                        </th>
                        <th scope="col" className="text-right">
                          Identity
                        </th>
                        <th scope="col" className="text-right">
                          Subjects
                        </th>
                        <th scope="col" className="text-right">
                          Marks exact
                        </th>
                        <th scope="col" className="text-right">
                          Confidence
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {summary.variants.map((row) => (
                        <tr key={row.variant}>
                          <td className="font-medium capitalize">{row.variant}</td>
                          <td className="num">{row.cases}</td>
                          <td className="num">{pct(row.identity_accuracy)}</td>
                          <td className="num">{pct(row.subject_recall)}</td>
                          <td className="num">{pct(row.mark_accuracy)}</td>
                          <td className="num">{row.mean_confidence}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="border-t border-line px-5 py-3 text-[11px] leading-relaxed text-muted">
                  Variants add grain, blur, a slight tilt, uneven light and JPEG compression. Identity
                  covers name, register number and examination year.
                </div>
              </SectionCard>

              <SectionCard
                title="Mark verification"
                aside={
                  <span className="text-[11px] text-muted">
                    {summary.subjects.marks_exact}/{summary.subjects.total} marks read exactly
                  </span>
                }
                bodyClassName="p-0"
              >
                <div className="overflow-x-auto">
                  <table className="data-table min-w-[640px]">
                    <thead>
                      <tr>
                        <th scope="col">Layer</th>
                        <th scope="col" className="text-right">
                          Precision
                        </th>
                        <th scope="col" className="text-right">
                          Recall
                        </th>
                        <th scope="col" className="text-right">
                          F1
                        </th>
                        <th scope="col" className="text-right">
                          TP / FP / FN
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      <MetricRow
                        label="End to end"
                        detail="OCR extraction followed by the mark comparison rules."
                        values={summary.mismatch}
                      />
                      <MetricRow
                        label="Comparison rules alone"
                        detail="Ground-truth subject rows in, checks out. Isolates OCR error from rule error."
                        values={summary.comparison_engine}
                      />
                    </tbody>
                  </table>
                </div>
                <div className="grid gap-4 border-t border-line px-5 py-4 sm:grid-cols-[minmax(0,1fr)_220px]">
                  <div>
                    <p className="text-[12px] font-medium">Case-level decisions</p>
                    <p className="mt-1 max-w-[52ch] text-[11.5px] leading-relaxed text-muted">
                      An application is correctly flagged when at least one entered mark differs from
                      the sheet. Case accuracy is {pct(summary.mismatch.matrix.accuracy)}. Missing
                      subjects are scored separately: recall {pct(summary.missing.recall)}.
                    </p>
                    <p className="mt-2 text-[11px] text-muted">
                      Subject rows found {pct(summary.subjects.found_rate)} · extras detected{" "}
                      {summary.extras.detected}/{summary.extras.expected}
                    </p>
                  </div>
                  <Matrix summary={summary} />
                </div>
              </SectionCard>

              {summary.documents ? (
                <SectionCard
                  title="Supporting documents"
                  aside={
                    <span className="text-[11px] text-muted">
                      {summary.documents.fields_correct}/{summary.documents.fields_total} fields read
                      exactly
                    </span>
                  }
                  bodyClassName="p-0"
                >
                  <div className="overflow-x-auto">
                    <table className="data-table min-w-[560px]">
                      <thead>
                        <tr>
                          <th scope="col">Document</th>
                          <th scope="col" className="text-right">
                            Fixtures
                          </th>
                          <th scope="col" className="text-right">
                            Fields
                          </th>
                          <th scope="col" className="text-right">
                            Field accuracy
                          </th>
                          <th scope="col" className="text-right">
                            Classified
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.documents.by_kind.map((row) => (
                          <tr key={row.kind}>
                            <td className="font-medium">{row.label}</td>
                            <td className="num">{row.fixtures}</td>
                            <td className="num">
                              {row.fields_correct}/{row.fields_total}
                            </td>
                            <td className="num">{pct(row.field_accuracy)}</td>
                            <td className="num">{pct(row.classification_accuracy)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="grid gap-3 border-t border-line px-5 py-4 sm:grid-cols-2">
                    <p className="text-[11.5px] leading-relaxed text-muted">
                      Aadhaar checksum:{" "}
                      <span className="text-ink-soft">
                        {summary.documents.checksum.correct}/{summary.documents.checksum.tested}
                      </span>{" "}
                      correct. Fixtures include valid synthetic numbers and one with a broken
                      Verhoeff digit; only the last four digits are stored.
                    </p>
                    <p className="text-[11.5px] leading-relaxed text-muted">
                      Certificates are scored on name, certificate number, issue date and the
                      printed income, community or first-graduate value.
                    </p>
                  </div>
                </SectionCard>
              ) : null}

              {summary.classification ? (
                <SectionCard
                  title="Document type confusion"
                  aside={
                    <span className="text-[11px] text-muted">
                      {summary.classification.correct}/{summary.classification.total} classified
                      correctly
                    </span>
                  }
                  bodyClassName="p-0"
                >
                  <ConfusionMatrix classification={summary.classification} />
                  <div className="border-t border-line px-5 py-3 text-[11px] leading-relaxed text-muted">
                    Rows are the printed document type; columns are the deterministic keyword
                    classifier. The matrix covers every mark sheet and supporting document in the
                    run.
                  </div>
                </SectionCard>
              ) : null}

              <SectionCard
                title="Photo rules"
                aside={
                  <span className="text-[11px] text-muted">
                    {summary.photos.critical_correct}/{summary.photos.fixtures} critical sets exact
                  </span>
                }
                bodyClassName="p-0"
              >
                <div className="overflow-x-auto">
                  <table className="data-table min-w-[420px]">
                    <thead>
                      <tr>
                        <th scope="col">Rule</th>
                        <th scope="col" className="text-right">
                          Fixtures
                        </th>
                        <th scope="col" className="text-right">
                          Correct
                        </th>
                        <th scope="col" className="text-right">
                          Accuracy
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {summary.photos.rules.map((rule) => (
                        <tr key={rule.rule}>
                          <td className="font-medium">{rule.rule}</td>
                          <td className="num">{rule.tested}</td>
                          <td className="num">{rule.correct}</td>
                          <td className="num">{pct(rule.accuracy)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="border-t border-line px-5 py-3 text-[11px] leading-relaxed text-muted">
                  Fixtures are controlled perturbations of a public-domain stand-in portrait. Face
                  detection is a Haar heuristic and is scored as a warning-level rule; the other eight
                  rules use the same thresholds as production.
                </div>
              </SectionCard>

              {summary.errors.length > 0 ? (
                <SectionCard title="Cases needing attention" bodyClassName="p-0">
                  <ul className="divide-y divide-line">
                    {summary.errors.slice(0, 6).map((item) => (
                      <li key={`${item.case}-${item.error}`} className="px-5 py-3">
                        <div className="flex items-baseline justify-between gap-3">
                          <span className="mono text-[12px]">{item.case}</span>
                          <span className="text-[10.5px] capitalize text-muted">{item.variant}</span>
                        </div>
                        <p className="mt-1 text-[11.5px] leading-relaxed text-muted">{item.error}</p>
                      </li>
                    ))}
                  </ul>
                </SectionCard>
              ) : null}
            </div>

            <aside className="grid content-start gap-5">
              <SectionCard title="Run details">
                <RunDetails summary={summary} />
              </SectionCard>

              <div className="card-flat p-5">
                <p className="text-[13px] font-medium">How the set is built</p>
                <ul className="mt-3 grid gap-2 text-[11.5px] leading-relaxed text-muted">
                  <li>Fixed-seed generator; every identity and mark is fictional.</li>
                  <li>Class 12 and Class 11 statements print their class explicitly.</li>
                  <li>Aadhaar cards use synthetic Verhoeff-checked numbers, never real ones.</li>
                  <li>Certificates carry known income, community and first-graduate values.</li>
                  <li>Ground truth is written with the document, never taken from OCR.</li>
                  <li>Entry errors are injected for known mismatch labels.</li>
                  <li>Photo labels come from the perturbation, not from the detector.</li>
                </ul>
              </div>

              {query.data && query.data.history.length > 1 ? (
                <SectionCard title="Earlier runs" bodyClassName="p-0">
                  <ul className="divide-y divide-line">
                    {query.data.history.slice(1, 5).map((item) => (
                      <li key={item.id} className="px-5 py-3">
                        <div className="flex items-baseline justify-between gap-3">
                          <span className="text-[12px] font-medium capitalize">{item.status}</span>
                          <span className="text-[10.5px] text-muted">{stamp(item.created_at)}</span>
                        </div>
                        <p className="mt-1 text-[10.5px] text-muted">
                          {item.total_cases} sheets · field {pct(item.field_accuracy)} · docs{" "}
                          {pct(item.document_accuracy)} · recall {pct(item.mismatch_recall)}
                        </p>
                      </li>
                    ))}
                  </ul>
                </SectionCard>
              ) : null}
            </aside>
          </div>
        </>
      ) : null}
    </AppShell>
  );
}
