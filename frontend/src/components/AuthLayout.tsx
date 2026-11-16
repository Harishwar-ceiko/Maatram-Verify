import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Brand } from "./ui";

function SpecimenReport() {
  return (
    <figure className="specimen enter-late m-0">
      <div className="flex items-start justify-between gap-3 border-b border-line px-4 py-3">
        <figcaption>
          <p className="text-[12.5px] font-semibold leading-tight">Validation report</p>
          <p className="mono mt-1 text-[10.5px] text-muted">MH26-4K2QF · 14 Nov 2026</p>
        </figcaption>
        <span className="stamp stamp-fail mt-0.5">Needs review</span>
      </div>

      <table className="specimen-table">
        <thead>
          <tr>
            <th scope="col">Subject</th>
            <th scope="col" className="text-right">
              Entered
            </th>
            <th scope="col" className="text-right">
              Uploaded
            </th>
            <th scope="col" className="text-right">
              Result
            </th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Mathematics</td>
            <td className="mono text-right">85</td>
            <td className="mono text-right">88</td>
            <td className="text-right">
              <span className="stamp stamp-fail">Mismatch</span>
            </td>
          </tr>
          <tr>
            <td>English</td>
            <td className="mono text-right">92</td>
            <td className="mono text-right">92</td>
            <td className="text-right">
              <span className="stamp stamp-pass">Match</span>
            </td>
          </tr>
          <tr>
            <td>Completeness</td>
            <td className="mono text-right text-faint">—</td>
            <td className="text-right text-[11.5px] text-muted">4 of 4 subjects</td>
            <td className="text-right">
              <span className="stamp stamp-pass">Pass</span>
            </td>
          </tr>
        </tbody>
      </table>

      <div className="flex items-center justify-between gap-4 border-t border-line px-4 py-2.5">
        <p className="text-[11px] text-muted">Photo · 180 × 220 px</p>
        <p className="flex items-center gap-2 text-[11px] text-fail">
          <span className="status status-fail">
            <span className="status-mark" aria-hidden="true" />
            Fail
          </span>
          <span className="text-faint">min 300 × 400</span>
        </p>
      </div>
    </figure>
  );
}

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[1.06fr_0.94fr]">
      <section className="relative flex flex-col bg-paper px-6 pb-10 pt-7 sm:px-10 lg:px-14 lg:pb-8 lg:pt-9">
        <Link to="/login" className="w-fit" aria-label="Maatram Verify home">
          <Brand />
        </Link>

        <div className="enter mt-11 max-w-[560px] lg:my-auto lg:mt-0 lg:py-10">
          <p className="mono text-[11px] text-muted">
            Maatram HackForge 2026-27 · MH26-01
          </p>
          <h1 className="display mt-4 text-[clamp(2.6rem,5.4vw,4.15rem)]">
            Every mark,
            <br />
            checked twice.
          </h1>
          <p className="mt-5 max-w-[46ch] text-[15px] leading-relaxed text-ink-soft">
            Applicants type their marks. The mark sheet has the final word. Maatram reads the sheet,
            compares it subject by subject, checks the photograph, and sends anything doubtful to a
            person.
          </p>

          <div className="mt-8 hidden lg:block">
            <SpecimenReport />
          </div>

          <p className="mt-5 text-[11.5px] leading-relaxed text-muted">
            Read by Tesseract OCR. Judged by fixed rules. No generative AI.
          </p>
        </div>

        <div className="mt-10 flex items-center justify-between gap-4 border-t border-line pt-4 lg:mt-0">
          <p className="text-[11px] text-muted">© 2026 Maatram Admissions</p>
          <p className="mono text-[10.5px] text-faint">v0.1 · deterministic</p>
        </div>
      </section>

      <section className="flex items-center justify-center border-t border-line bg-surface px-6 py-12 sm:px-10 lg:border-l lg:border-t-0 lg:px-12">
        <div className="w-full max-w-[404px] enter-late">{children}</div>
      </section>
    </div>
  );
}
