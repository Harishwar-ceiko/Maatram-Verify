import { clsx } from "clsx";
import type {
  DocumentVerdict,
  Finding,
  IdentityMatrix,
  IdentityMatrixField,
  Run,
} from "../lib/api";
import { StatusBadge } from "./ui";

function MarkTable({ findings }: { findings: Finding[] }) {
  return (
    <table className="data-table">
      <thead>
        <tr>
          <th scope="col">Subject</th>
          <th scope="col" className="text-right">
            Entered
          </th>
          <th scope="col" className="text-right">
            From sheet
          </th>
          <th scope="col" className="text-right">
            Result
          </th>
        </tr>
      </thead>
      <tbody>
        {findings.map((finding) => (
          <tr key={finding.id}>
            <td>
              <span className="font-medium">{finding.field}</span>
              {finding.detail && finding.result !== "match" ? (
                <span className="mt-0.5 block max-w-[52ch] text-[10.5px] leading-relaxed text-muted">
                  {finding.detail}
                </span>
              ) : null}
            </td>
            <td className="num">{finding.entered_value ?? "—"}</td>
            <td className="num">{finding.uploaded_value ?? "—"}</td>
            <td className="text-right align-top">
              <StatusBadge value={finding.result} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function MeasureTable({ findings }: { findings: Finding[] }) {
  return (
    <table className="data-table">
      <thead>
        <tr>
          <th scope="col">Check</th>
          <th scope="col">Measured</th>
          <th scope="col">Required</th>
          <th scope="col" className="text-right">
            Result
          </th>
        </tr>
      </thead>
      <tbody>
        {findings.map((finding) => (
          <tr key={finding.id}>
            <td>
              <span className="font-medium">{finding.field}</span>
              {finding.detail ? (
                <span className="mt-0.5 block max-w-[52ch] text-[10.5px] leading-relaxed text-muted">
                  {finding.detail}
                </span>
              ) : null}
            </td>
            <td className="mono text-[12px]">
              {finding.measured_value ?? finding.uploaded_value ?? "—"}
            </td>
            <td className="mono text-[12px] text-muted">{finding.required_value ?? "—"}</td>
            <td className="text-right align-top">
              <StatusBadge value={finding.result} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function MarkList({ findings }: { findings: Finding[] }) {
  return (
    <ul className="divide-y divide-line">
      {findings.map((finding) => (
        <li key={finding.id} className="px-5 py-3">
          <div className="flex items-start justify-between gap-3">
            <span className="text-[13px] font-medium">{finding.field}</span>
            <StatusBadge value={finding.result} />
          </div>
          <p className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-[11px] text-muted">
            <span>
              Entered <span className="mono text-ink-soft">{finding.entered_value ?? "—"}</span>
            </span>
            <span>
              Sheet <span className="mono text-ink-soft">{finding.uploaded_value ?? "—"}</span>
            </span>
          </p>
          {finding.detail && finding.result !== "match" ? (
            <p className="mt-1 max-w-[46ch] text-[11px] leading-relaxed text-muted">
              {finding.detail}
            </p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

function MeasureList({ findings }: { findings: Finding[] }) {
  return (
    <ul className="divide-y divide-line">
      {findings.map((finding) => {
        const measured = finding.measured_value ?? finding.uploaded_value;
        return (
          <li key={finding.id} className="px-5 py-3">
            <div className="flex items-start justify-between gap-3">
              <span className="text-[13px] font-medium">{finding.field}</span>
              <StatusBadge value={finding.result} />
            </div>
            <p className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-[11px] text-muted">
              <span>
                Measured <span className="mono text-ink-soft">{measured ?? "—"}</span>
              </span>
              {finding.required_value ? (
                <span>
                  Required <span className="mono text-ink-soft">{finding.required_value}</span>
                </span>
              ) : null}
            </p>
            {finding.detail ? (
              <p className="mt-1 max-w-[46ch] text-[11px] leading-relaxed text-muted">
                {finding.detail}
              </p>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

function IdentityRowValues({ field }: { field: IdentityMatrixField }) {
  const documents = field.values.filter((value) => value.kind !== "application");
  if (documents.length === 0) {
    return <span className="text-[11px] text-muted">Not printed on any document</span>;
  }
  return (
    <div className="space-y-1.5">
      {documents.map((value, index) => (
        <div
          key={`${value.kind}-${value.document_id ?? "document"}-${index}`}
          className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5"
        >
          <span
            className={clsx(
              "max-w-[42ch] text-[12px] leading-relaxed",
              value.status === "mismatch" ? "text-fail" : "text-ink-soft",
            )}
          >
            {value.value}
          </span>
          <span className="label shrink-0 text-[10.5px]">{value.source}</span>
        </div>
      ))}
    </div>
  );
}

function IdentityMatrixTable({ matrix }: { matrix: IdentityMatrix }) {
  const fields = matrix.fields.filter((field) => field.values.length > 0);
  if (fields.length === 0) return null;

  return (
    <section className="border-b border-line" aria-label="Identity consistency matrix">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-line px-5 py-2.5">
        <p className="label">Identity consistency matrix</p>
        <p className="flex flex-wrap gap-x-3 gap-y-0.5 text-[10.5px] text-muted">
          <span>
            {matrix.checked} of {fields.length} fields compared
          </span>
          <span>{matrix.mismatched} mismatched</span>
        </p>
      </div>

      <div className="hidden overflow-x-auto sm:block">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">Field</th>
              <th scope="col">Application</th>
              <th scope="col">Documents read</th>
              <th scope="col" className="text-right">
                Result
              </th>
            </tr>
          </thead>
          <tbody>
            {fields.map((field) => {
              const application = field.values.find((value) => value.kind === "application");
              return (
                <tr key={field.field}>
                  <td className="align-top">
                    <span className="font-medium">{field.label}</span>
                    <span className="mt-0.5 block max-w-[38ch] text-[10.5px] leading-relaxed text-muted">
                      {field.detail}
                    </span>
                  </td>
                  <td className="max-w-[22ch] align-top text-[12px] leading-relaxed text-ink-soft">
                    {application?.value ?? "—"}
                  </td>
                  <td className="align-top">
                    <IdentityRowValues field={field} />
                  </td>
                  <td className="text-right align-top">
                    <StatusBadge value={field.status} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <ul className="divide-y divide-line sm:hidden">
        {fields.map((field) => (
          <li key={field.field} className="px-5 py-3">
            <div className="flex items-start justify-between gap-3">
              <span className="text-[13px] font-medium">{field.label}</span>
              <StatusBadge value={field.status} />
            </div>
            <p className="mt-0.5 text-[11px] leading-relaxed text-muted">{field.detail}</p>
            <div className="mt-2 space-y-1.5">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                <span className="max-w-[38ch] text-[12px] leading-relaxed text-ink-soft">
                  {field.values.find((value) => value.kind === "application")?.value ?? "—"}
                </span>
                <span className="label shrink-0 text-[10.5px]">Application</span>
              </div>
              {field.values
                .filter((value) => value.kind !== "application")
                .map((value, index) => (
                  <div
                    key={`${value.kind}-${value.document_id ?? "document"}-${index}`}
                    className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5"
                  >
                    <span
                      className={clsx(
                        "max-w-[38ch] text-[12px] leading-relaxed",
                        value.status === "mismatch" ? "text-fail" : "text-ink-soft",
                      )}
                    >
                      {value.value}
                    </span>
                    <span className="label shrink-0 text-[10.5px]">{value.source}</span>
                  </div>
                ))}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function DocumentVerdicts({ run, documents }: { run: Run; documents: DocumentVerdict[] }) {
  const passed = documents.filter((document) => document.status === "pass").length;
  const failed = documents.filter((document) => document.status === "fail").length;
  const review = documents.filter((document) => document.status === "review").length;
  const pending = documents.filter((document) => document.status === "pending").length;

  function markCounts(document: DocumentVerdict) {
    const related = run.findings.filter(
      (finding) =>
        finding.category === "mark" &&
        Number((finding.meta ?? {}).document_id) === document.id,
    );
    return {
      matched: related.filter((finding) => finding.result === "match").length,
      mismatched: related.filter((finding) => finding.result === "mismatch").length,
      total: related.length,
    };
  }

  return (
    <section className="border-b border-line" aria-label="Document verdicts">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-line px-5 py-2.5">
        <p className="label">Document verdicts</p>
        <p className="flex flex-wrap gap-x-3 gap-y-0.5 text-[10.5px] text-muted">
          <span>{passed} passed</span>
          {review ? <span className="text-warn">{review} need review</span> : null}
          {failed ? <span className="text-fail">{failed} failed</span> : null}
          {pending ? <span>{pending} pending</span> : null}
        </p>
      </div>

      <div className="hidden overflow-x-auto sm:block">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">Document</th>
              <th scope="col">Details</th>
              <th scope="col" className="text-right">
                Checks
              </th>
              <th scope="col" className="text-right">
                Result
              </th>
            </tr>
          </thead>
          <tbody>
            {documents.map((document) => {
              const counts = markCounts(document);
              const classification =
                document.classification &&
                typeof document.classification.method === "string"
                  ? String(document.classification.method)
                  : null;
              return (
                <tr key={document.id}>
                  <td>
                    <span className="font-medium">{document.label}</span>
                    <span className="mt-0.5 block max-w-[44ch] truncate text-[10.5px] text-muted">
                      {document.filename}
                    </span>
                  </td>
                  <td className="max-w-[38ch] text-[11.5px] leading-relaxed text-muted">
                    {document.masked_aadhaar ? (
                      <span className="mono block text-ink-soft">
                        {document.masked_aadhaar}
                      </span>
                    ) : null}
                    {counts.total ? (
                      <span className="block">
                        {counts.matched} matched · {counts.mismatched} mismatched
                      </span>
                    ) : null}
                    {classification ? (
                      <span className="block">
                        {classification === "override"
                          ? "Type chosen by the applicant"
                          : "Type detected from the content"}
                      </span>
                    ) : null}
                    {!counts.total && !document.masked_aadhaar && !classification ? (
                      <span>No extra detail recorded</span>
                    ) : null}
                  </td>
                  <td className="num text-right">
                    {document.findings}
                    {document.critical ? (
                      <span className="mt-0.5 block text-[10px] font-normal text-fail">
                        {document.critical} critical
                      </span>
                    ) : document.warnings ? (
                      <span className="mt-0.5 block text-[10px] font-normal text-warn">
                        {document.warnings} warning{document.warnings === 1 ? "" : "s"}
                      </span>
                    ) : null}
                  </td>
                  <td className="text-right align-top">
                    <StatusBadge value={document.status} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <ul className="divide-y divide-line sm:hidden">
        {documents.map((document) => {
          const counts = markCounts(document);
          return (
            <li key={document.id} className="px-5 py-3">
              <div className="flex items-start justify-between gap-3">
                <span className="text-[13px] font-medium">{document.label}</span>
                <StatusBadge value={document.status} />
              </div>
              <p className="mt-0.5 truncate text-[11px] text-muted">{document.filename}</p>
              <p className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-muted">
                <span>{document.findings} checks</span>
                {counts.total ? (
                  <span>
                    {counts.matched} matched · {counts.mismatched} mismatched
                  </span>
                ) : null}
                {document.masked_aadhaar ? (
                  <span className="mono">{document.masked_aadhaar}</span>
                ) : null}
              </p>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function ValidationTable({ run }: { run: Run | null }) {
  if (!run) {
    return (
      <div className="px-5 py-8 text-center">
        <p className="text-[13px] font-medium text-ink-soft">Not checked yet</p>
        <p className="mx-auto mt-1.5 max-w-[34ch] text-[12px] leading-relaxed text-muted">
          Attach the mark sheet and photograph, then run validation. Results appear here, one row per
          check.
        </p>
      </div>
    );
  }

  if (run.status === "pending" || run.status === "running") {
    return (
      <div className="px-5 py-8 text-center">
        <p className="text-[13px] font-medium text-ink-soft">
          {run.status === "pending" ? "Queued for validation" : "Reading documents"}
        </p>
        <p className="mx-auto mt-1.5 max-w-[38ch] text-[12px] leading-relaxed text-muted">
          Pending checks resolve on their own. This page refreshes as each result lands.
        </p>
      </div>
    );
  }

  if (run.status === "failed") {
    return (
      <div className="px-5 py-6">
        <p className="text-[13px] font-medium text-fail">Validation could not finish</p>
        <p className="mt-1.5 text-[12px] leading-relaxed text-muted">
          {run.error ?? "The checker stopped before producing results."}
        </p>
      </div>
    );
  }

  const marks = run.findings.filter((finding) => finding.category === "mark");
  const photos = run.findings.filter((finding) => finding.category === "photo");
  const others = run.findings.filter(
    (finding) => finding.category !== "mark" && finding.category !== "photo",
  );
  const verdict = typeof run.summary?.verdict === "string" ? run.summary.verdict : null;
  const matrix = run.summary?.identity_matrix as IdentityMatrix | undefined;
  const documentVerdicts = Array.isArray(run.summary?.documents)
    ? (run.summary.documents as DocumentVerdict[])
    : [];

  return (
    <div>
      {verdict ? (
        <div className="border-b border-line bg-paper-deep/40 px-5 py-3">
          <p className="max-w-[76ch] text-[12px] leading-relaxed text-ink-soft">{verdict}</p>
        </div>
      ) : null}

      {documentVerdicts.length > 0 ? (
        <DocumentVerdicts run={run} documents={documentVerdicts} />
      ) : null}

      {matrix && Array.isArray(matrix.fields) ? <IdentityMatrixTable matrix={matrix} /> : null}

      {marks.length > 0 ? (
        <div>
          <p className="label border-b border-line px-5 py-2.5">Marks</p>
          <div className="hidden overflow-x-auto sm:block">
            <MarkTable findings={marks} />
          </div>
          <div className="sm:hidden">
            <MarkList findings={marks} />
          </div>
        </div>
      ) : null}

      {photos.length > 0 ? (
        <div className={marks.length > 0 ? "border-t border-line" : undefined}>
          <div className="flex items-baseline justify-between gap-3 border-b border-line px-5 py-2.5">
            <p className="label">Photograph</p>
            <p className="text-[10.5px] text-muted">Measured on the uploaded portrait</p>
          </div>
          <div className="hidden overflow-x-auto sm:block">
            <MeasureTable findings={photos} />
          </div>
          <div className="sm:hidden">
            <MeasureList findings={photos} />
          </div>
        </div>
      ) : null}

      {others.length > 0 ? (
        <div
          className={marks.length > 0 || photos.length > 0 ? "border-t border-line" : undefined}
        >
          <p className="label border-b border-line px-5 py-2.5">Documents and identity</p>
          <div className="hidden overflow-x-auto sm:block">
            <MeasureTable findings={others} />
          </div>
          <div className="sm:hidden">
            <MeasureList findings={others} />
          </div>
        </div>
      ) : null}
    </div>
  );
}
