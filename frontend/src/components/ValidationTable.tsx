import type { Finding, Run } from "../lib/api";
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

  return (
    <div>
      {verdict ? (
        <div className="border-b border-line bg-paper-deep/40 px-5 py-3">
          <p className="max-w-[76ch] text-[12px] leading-relaxed text-ink-soft">{verdict}</p>
        </div>
      ) : null}

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
