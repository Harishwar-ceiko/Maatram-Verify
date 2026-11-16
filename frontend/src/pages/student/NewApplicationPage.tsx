import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, Plus, X } from "lucide-react";
import { AppShell } from "../../components/AppShell";
import {
  Alert,
  Button,
  Field,
  PageHeader,
  Requirement,
  SectionCard,
} from "../../components/ui";
import { api, ApiError } from "../../lib/api";

interface Row {
  key: string;
  subject: string;
  marks: string;
  max: string;
}

let rowId = 0;
const newRow = (subject = "", marks = "", max = ""): Row => ({
  key: `row-${rowId++}`,
  subject,
  marks,
  max,
});

const PROGRAMMES = [
  "B.Sc. Computer Science",
  "B.E. Electronics and Communication",
  "B.Tech Information Technology",
  "B.Com. Honours",
  "B.A. Economics",
  "B.Sc. Mathematics",
  "B.Sc. Physics",
];

export function NewApplicationPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const config = useQuery({ queryKey: ["config"], queryFn: api.config });

  const [form, setForm] = useState({
    program: "",
    applicant_name: "",
    register_number: "",
    exam_year: String(new Date().getFullYear()),
    board: "",
  });
  const [rows, setRows] = useState<Row[]>([newRow()]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [seeded, setSeeded] = useState(false);

  useEffect(() => {
    if (seeded || !config.data) return;
    setRows(config.data.subjects.required.map((subject) => newRow(subject)));
    setSeeded(true);
  }, [config.data, seeded]);

  const create = useMutation({
    mutationFn: api.createApplication,
    onSuccess: (application) => {
      queryClient.invalidateQueries({ queryKey: ["applications"] });
      navigate(`/applications/${application.id}`, {
        state: { created: true },
      });
    },
    onError: (error) => {
      setFormError(error instanceof ApiError ? error.detail : "Could not file the application.");
    },
  });

  function set<K extends keyof typeof form>(key: K, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
    setErrors((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
  }

  function updateRow(key: string, patch: Partial<Row>) {
    setRows((current) => current.map((row) => (row.key === key ? { ...row, ...patch } : row)));
    setErrors((current) => {
      const next = { ...current };
      for (const field of Object.keys(next)) {
        if (field.startsWith(`${key}-`)) delete next[field];
      }
      return next;
    });
  }

  function validate(): boolean {
    const next: Record<string, string> = {};
    if (form.program.trim().length < 2) next.program = "Choose or type the programme.";
    if (form.applicant_name.trim().length < 2) next.applicant_name = "Enter your full name.";
    if (form.register_number.trim().length < 2) next.register_number = "Enter the register number.";
    const year = Number(form.exam_year);
    if (!Number.isInteger(year) || year < 1990 || year > 2100) next.exam_year = "Use a four-digit year.";

    const used = new Map<string, number>();
    rows.forEach((row, index) => {
      const label = `Subject ${index + 1}`;
      if (!row.subject.trim()) next[`${row.key}-subject`] = `${label}: name the subject.`;
      const marks = Number(row.marks);
      if (row.marks === "" || Number.isNaN(marks) || marks < 0 || marks > 1000) {
        next[`${row.key}-marks`] = `${label}: enter the marks you scored.`;
      }
      if (row.max !== "") {
        const max = Number(row.max);
        if (Number.isNaN(max) || max <= 0 || max > 1000) {
          next[`${row.key}-max`] = `${label}: maximum must be above zero.`;
        } else if (!Number.isNaN(marks) && marks > max) {
          next[`${row.key}-marks`] = `${label}: marks are above the maximum.`;
        }
      }
      const key = row.subject.trim().toLowerCase();
      if (key) {
        if (used.has(key)) next[`${row.key}-subject`] = `${label}: this subject is already listed.`;
        used.set(key, index);
      }
    });

    if (rows.length === 0) next.rows = "Add at least one subject.";
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setFormError(null);
    if (!validate()) {
      const first = document.querySelector<HTMLElement>('[aria-invalid="true"]');
      first?.focus();
      return;
    }
    create.mutate({
      program: form.program.trim(),
      applicant_name: form.applicant_name.trim(),
      register_number: form.register_number.trim().toUpperCase(),
      exam_year: Number(form.exam_year),
      board: form.board.trim(),
      marks: rows.map((row) => ({
        subject: row.subject.trim(),
        marks_obtained: Number(row.marks),
        max_marks: row.max === "" ? null : Number(row.max),
      })),
    });
  }

  const required = config.data?.subjects.required ?? [];
  const missingRequired = required.filter(
    (subject) => !rows.some((row) => row.subject.trim().toLowerCase() === subject.toLowerCase()),
  );

  return (
    <AppShell>
      <Link
        to="/applications"
        className="mb-6 inline-flex items-center gap-1.5 text-[12.5px] text-muted transition-colors duration-150 hover:text-ink"
      >
        <ArrowLeft size={14} aria-hidden="true" />
        All applications
      </Link>

      <PageHeader
        title="New application"
        description="Type the marks exactly as they appear on your mark sheet. The checker compares this form against the sheet; it does not average, round or guess."
      />

      <form onSubmit={onSubmit} noValidate className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_312px]">
        <div className="grid gap-6">
          {formError ? <Alert tone="error">{formError}</Alert> : null}

          <SectionCard title="Applicant and programme">
            <div className="grid gap-5 sm:grid-cols-2">
              <Field
                label="Programme applied for"
                htmlFor="program"
                error={errors.program}
                className="sm:col-span-2"
              >
                <input
                  id="program"
                  list="programmes"
                  className="input"
                  placeholder="Start typing, or choose from the list"
                  value={form.program}
                  onChange={(event) => set("program", event.target.value)}
                  aria-invalid={Boolean(errors.program)}
                />
                <datalist id="programmes">
                  {PROGRAMMES.map((programme) => (
                    <option key={programme} value={programme} />
                  ))}
                </datalist>
              </Field>

              <Field label="Full name" htmlFor="applicant_name" error={errors.applicant_name}>
                <input
                  id="applicant_name"
                  className="input"
                  autoComplete="name"
                  placeholder="As printed on the mark sheet"
                  value={form.applicant_name}
                  onChange={(event) => set("applicant_name", event.target.value)}
                  aria-invalid={Boolean(errors.applicant_name)}
                />
              </Field>

              <Field
                label="Register number"
                htmlFor="register_number"
                error={errors.register_number}
                hint="Letters and digits, as printed."
              >
                <input
                  id="register_number"
                  className="input mono uppercase"
                  placeholder="REG2026A014"
                  value={form.register_number}
                  onChange={(event) => set("register_number", event.target.value)}
                  aria-invalid={Boolean(errors.register_number)}
                />
              </Field>

              <Field label="Examination year" htmlFor="exam_year" error={errors.exam_year}>
                <input
                  id="exam_year"
                  className="input mono"
                  inputMode="numeric"
                  value={form.exam_year}
                  onChange={(event) => set("exam_year", event.target.value)}
                  aria-invalid={Boolean(errors.exam_year)}
                />
              </Field>

              <Field label="Board or university" htmlFor="board" hint="Optional, but it helps a reviewer.">
                <input
                  id="board"
                  className="input"
                  placeholder="State Board of Examinations"
                  value={form.board}
                  onChange={(event) => set("board", event.target.value)}
                />
              </Field>
            </div>
          </SectionCard>

          <SectionCard
            title="Marks you entered"
            aside={
              <span className="mono text-[11px] text-muted">
                {rows.length} subject{rows.length === 1 ? "" : "s"}
              </span>
            }
          >
            <div className="hidden gap-2 pb-2 sm:grid sm:grid-cols-[minmax(0,1.5fr)_104px_104px_36px]">
              <span className="label">Subject</span>
              <span className="label">Marks</span>
              <span className="label">Out of</span>
              <span />
            </div>

            <div className="grid gap-3">
              {rows.map((row, index) => (
                <div
                  key={row.key}
                  className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_32px] items-start gap-2 border-b border-line pb-3 last:border-b-0 last:pb-0 sm:grid-cols-[minmax(0,1.5fr)_104px_104px_36px] sm:items-center sm:border-0 sm:pb-0"
                >
                  <div className="col-span-3 sm:col-span-1">
                    <label className="field-label mb-1 block sm:hidden" htmlFor={`${row.key}-subject`}>
                      Subject {index + 1}
                    </label>
                    <input
                      id={`${row.key}-subject`}
                      className="input"
                      placeholder="Mathematics"
                      aria-label={`Subject ${index + 1}`}
                      value={row.subject}
                      onChange={(event) => updateRow(row.key, { subject: event.target.value })}
                      aria-invalid={Boolean(errors[`${row.key}-subject`])}
                    />
                    {errors[`${row.key}-subject`] ? (
                      <p className="field-error mt-1" role="alert">
                        {errors[`${row.key}-subject`]}
                      </p>
                    ) : null}
                  </div>
                  <div>
                    <label className="field-label mb-1 block sm:hidden" htmlFor={`${row.key}-marks`}>
                      Marks
                    </label>
                    <input
                      id={`${row.key}-marks`}
                      className="input mono"
                      inputMode="decimal"
                      placeholder="85"
                      aria-label={`Marks for row ${index + 1}`}
                      value={row.marks}
                      onChange={(event) => updateRow(row.key, { marks: event.target.value })}
                      aria-invalid={Boolean(errors[`${row.key}-marks`])}
                    />
                    {errors[`${row.key}-marks`] ? (
                      <p className="field-error mt-1" role="alert">
                        {errors[`${row.key}-marks`]}
                      </p>
                    ) : null}
                  </div>
                  <div>
                    <label className="field-label mb-1 block sm:hidden" htmlFor={`${row.key}-max`}>
                      Out of
                    </label>
                    <input
                      id={`${row.key}-max`}
                      className="input mono"
                      inputMode="decimal"
                      placeholder="100"
                      aria-label={`Maximum marks for row ${index + 1}`}
                      value={row.max}
                      onChange={(event) => updateRow(row.key, { max: event.target.value })}
                      aria-invalid={Boolean(errors[`${row.key}-max`])}
                    />
                    {errors[`${row.key}-max`] ? (
                      <p className="field-error mt-1" role="alert">
                        {errors[`${row.key}-max`]}
                      </p>
                    ) : null}
                  </div>
                  <div className="flex items-center justify-center">
                    <button
                      type="button"
                      className="btn btn-ghost h-9 w-9 p-0 text-muted hover:text-fail"
                      aria-label={`Remove ${row.subject || `subject ${index + 1}`}`}
                      onClick={() => setRows((current) => current.filter((item) => item.key !== row.key))}
                      disabled={rows.length === 1}
                    >
                      <X size={15} aria-hidden="true" />
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {errors.rows ? (
              <p className="field-error mt-2" role="alert">
                {errors.rows}
              </p>
            ) : null}

            <div className="mt-4 flex flex-wrap items-center gap-2">
              <Button type="button" variant="secondary" size="sm" onClick={() => setRows((current) => [...current, newRow()])}>
                <Plus size={14} aria-hidden="true" />
                Add subject
              </Button>
              {missingRequired.length > 0 ? (
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() =>
                    setRows((current) => [
                      ...current,
                      ...missingRequired.map((subject) => newRow(subject)),
                    ])
                  }
                >
                  Add {missingRequired.length} missing required subject
                  {missingRequired.length === 1 ? "" : "s"}
                </button>
              ) : null}
            </div>
          </SectionCard>
        </div>

        <aside className="grid content-start gap-5 lg:sticky lg:top-8">
          <div className="card p-5">
            <h2 className="text-[14px] font-semibold">Before you file</h2>
            <ul className="mt-3 grid gap-2.5">
              <Requirement>Every mark matches the sheet exactly, not rounded.</Requirement>
              <Requirement>
                {required.length > 0
                  ? `All required subjects appear: ${required.join(", ")}.`
                  : "Every required subject appears on the sheet."}
              </Requirement>
              <Requirement>You will attach the mark sheet and photograph next.</Requirement>
            </ul>

            <Button type="submit" block className="mt-5 h-11" busy={create.isPending}>
              File application
            </Button>
            <p className="mt-2.5 text-center text-[11px] leading-relaxed text-faint">
              Nothing is submitted to a university. This is a prototype workspace.
            </p>
          </div>

          <div className="card-flat p-5">
            <h2 className="text-[13px] font-semibold">What happens after filing</h2>
            <ol className="mt-3 grid gap-3 text-[12px] leading-relaxed text-muted">
              <li className="flex gap-3">
                <span className="mono text-[11px] text-faint">01</span>
                <span>Attach your mark sheet and profile photo.</span>
              </li>
              <li className="flex gap-3">
                <span className="mono text-[11px] text-faint">02</span>
                <span>The checker reads the sheet and measures the photo.</span>
              </li>
              <li className="flex gap-3">
                <span className="mono text-[11px] text-faint">03</span>
                <span>Clean files verify automatically. Anything doubtful goes to a reviewer.</span>
              </li>
            </ol>
          </div>
        </aside>
      </form>
    </AppShell>
  );
}
