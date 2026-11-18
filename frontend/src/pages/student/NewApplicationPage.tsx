import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, Plus, X } from "lucide-react";
import { clsx } from "clsx";
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

interface EducationForm {
  register_number: string;
  exam_year: string;
  board: string;
  rows: Row[];
}

type Level = 10 | 11 | 12;

const LEVELS: Level[] = [10, 11, 12];

let rowId = 0;
const newRow = (subject = "", marks = "", max = ""): Row => ({
  key: `row-${rowId++}`,
  subject,
  marks,
  max,
});

const currentYear = new Date().getFullYear();

function blankRecord(level: Level): EducationForm {
  return {
    register_number: "",
    exam_year: String(currentYear - (12 - level)),
    board: "",
    rows: [],
  };
}

function YesNo({
  label,
  name,
  value,
  onChange,
}: {
  label: string;
  name: string;
  value: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <div className="field">
      <span className="field-label">{label}</span>
      <div
        className="flex min-h-[42px] items-center gap-2"
        role="radiogroup"
        aria-label={label}
      >
        {[true, false].map((option) => (
          <label
            key={String(option)}
            className={clsx(
              "inline-flex h-[34px] cursor-pointer items-center rounded-[2px] border px-3.5 text-[12.5px] transition-colors duration-150",
              value === option
                ? "border-ink bg-ink text-paper"
                : "border-line-strong bg-raised text-ink-soft hover:border-faint",
            )}
          >
            <input
              type="radio"
              name={name}
              className="sr-only"
              checked={value === option}
              onChange={() => onChange(option)}
            />
            {option ? "Yes" : "No"}
          </label>
        ))}
      </div>
    </div>
  );
}

export function NewApplicationPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const config = useQuery({ queryKey: ["config"], queryFn: api.config });

  const [form, setForm] = useState({
    applicant_name: "",
    date_of_birth: "",
    father_name: "",
    mother_name: "",
    phone: "",
    address: "",
    is_orphan: false,
    is_first_graduate: false,
  });
  const [education, setEducation] = useState<Record<Level, EducationForm>>({
    10: blankRecord(10),
    11: blankRecord(11),
    12: blankRecord(12),
  });
  const [class11Provided, setClass11Provided] = useState(true);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [seeded, setSeeded] = useState(false);

  useEffect(() => {
    if (seeded || !config.data) return;
    const data = config.data;
    const fallback = data.subjects.required;
    setEducation((current) => {
      const next = { ...current };
      for (const level of LEVELS) {
        const subjects = data.subjects.by_class[String(level)] ?? fallback;
        next[level] = { ...next[level], rows: subjects.map((subject) => newRow(subject)) };
      }
      return next;
    });
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

  function set<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((current) => ({ ...current, [key]: value }));
    setErrors((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
  }

  function patchRecord(level: Level, patch: Partial<EducationForm>) {
    setEducation((current) => ({
      ...current,
      [level]: { ...current[level], ...patch },
    }));
  }

  function updateRow(level: Level, key: string, patch: Partial<Row>) {
    setEducation((current) => ({
      ...current,
      [level]: {
        ...current[level],
        rows: current[level].rows.map((row) =>
          row.key === key ? { ...row, ...patch } : row,
        ),
      },
    }));
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
    if (form.applicant_name.trim().length < 2) {
      next.applicant_name = "Enter your full name.";
    }
    if (!form.date_of_birth) {
      next.date_of_birth = "Enter your date of birth.";
    } else {
      const dob = new Date(form.date_of_birth);
      if (Number.isNaN(dob.getTime()) || dob > new Date()) {
        next.date_of_birth = "Enter a valid date of birth.";
      }
    }
    if (form.father_name.trim().length < 2) next.father_name = "Enter your father's name.";
    if (form.mother_name.trim().length < 2) {
      next.mother_name = "Enter your mother's or guardian's name.";
    }
    const digits = form.phone.replace(/\D/g, "");
    if (digits.length < 7 || digits.length > 15) {
      next.phone = "Enter a phone number with 7 to 15 digits.";
    }
    if (form.address.trim().length < 5) next.address = "Enter your full postal address.";

    for (const level of LEVELS) {
      if (level === 11 && !class11Provided) continue;
      const record = education[level];
      const prefix = `class_${level}`;
      if (record.register_number.trim().length < 2) {
        next[`${prefix}.register_number`] = "Enter the register number.";
      }
      const year = Number(record.exam_year);
      if (!Number.isInteger(year) || year < 1990 || year > 2100) {
        next[`${prefix}.exam_year`] = "Use a four-digit year.";
      }
      if (record.rows.length === 0) {
        next[`${prefix}.rows`] = "Add at least one subject.";
      }
      const used = new Set<string>();
      record.rows.forEach((row, index) => {
        const label = `Subject ${index + 1}`;
        if (!row.subject.trim()) {
          next[`${row.key}-subject`] = `${label}: name the subject.`;
        }
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
          if (used.has(key)) {
            next[`${row.key}-subject`] = `${label}: this subject is already listed.`;
          }
          used.add(key);
        }
      });
    }

    setErrors(next);
    return Object.keys(next).length === 0;
  }

  function payload(level: Level) {
    const record = education[level];
    return {
      register_number: record.register_number.trim().toUpperCase(),
      exam_year: Number(record.exam_year),
      board: record.board.trim(),
      marks: record.rows.map((row) => ({
        subject: row.subject.trim(),
        marks_obtained: Number(row.marks),
        max_marks: row.max === "" ? null : Number(row.max),
      })),
    };
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
      applicant_name: form.applicant_name.trim(),
      date_of_birth: form.date_of_birth,
      father_name: form.father_name.trim(),
      mother_name: form.mother_name.trim(),
      phone: form.phone.trim(),
      address: form.address.trim(),
      is_orphan: form.is_orphan,
      is_first_graduate: form.is_first_graduate,
      class_10: payload(10),
      class_11: class11Provided ? payload(11) : null,
      class_12: payload(12),
    });
  }

  function educationSection(level: Level, index: string) {
    const record = education[level];
    const optional = level === 11;
    const provided = !optional || class11Provided;
    const prefix = `class_${level}`;

    return (
      <SectionCard
        key={level}
        title={
          <span className="inline-flex items-baseline gap-2.5">
            <span className="mono text-[11px] font-normal text-faint">{index}</span>
            Class {level}
          </span>
        }
        aside={
          optional ? (
            <label className="flex cursor-pointer items-center gap-2 text-[12px] text-muted">
              <input
                type="checkbox"
                className="checkbox"
                checked={!class11Provided}
                onChange={(event) => setClass11Provided(!event.target.checked)}
              />
              Not provided
            </label>
          ) : (
            <span className="mono text-[11px] text-muted">
              {record.rows.length} subject{record.rows.length === 1 ? "" : "s"}
            </span>
          )
        }
      >
        {!provided ? (
          <div className="rounded-[2px] border border-dashed border-line-strong bg-paper-deep/40 px-4 py-5">
            <p className="text-[13px] font-medium">Class 11 will be marked “Not provided”.</p>
            <p className="mt-1 max-w-[56ch] text-[12px] leading-relaxed text-muted">
              Leave this on if you did not sit Class 11 or do not have the mark sheet. The
              checker records the class as absent, not as a failure.
            </p>
          </div>
        ) : (
          <>
            <div className="grid gap-5 sm:grid-cols-3">
              <Field
                label="Register number"
                htmlFor={`c${level}-register`}
                error={errors[`${prefix}.register_number`]}
              >
                <input
                  id={`c${level}-register`}
                  className="input mono uppercase"
                  placeholder={`REG${currentYear - (12 - level)}A014`}
                  value={record.register_number}
                  onChange={(event) =>
                    patchRecord(level, { register_number: event.target.value })
                  }
                  aria-invalid={Boolean(errors[`${prefix}.register_number`])}
                />
              </Field>
              <Field
                label="Examination year"
                htmlFor={`c${level}-year`}
                error={errors[`${prefix}.exam_year`]}
              >
                <input
                  id={`c${level}-year`}
                  className="input mono"
                  inputMode="numeric"
                  value={record.exam_year}
                  onChange={(event) =>
                    patchRecord(level, { exam_year: event.target.value })
                  }
                  aria-invalid={Boolean(errors[`${prefix}.exam_year`])}
                />
              </Field>
              <Field label="Board" htmlFor={`c${level}-board`} hint="Optional.">
                <input
                  id={`c${level}-board`}
                  className="input"
                  placeholder="State Board of Examinations"
                  value={record.board}
                  onChange={(event) => patchRecord(level, { board: event.target.value })}
                />
              </Field>
            </div>

            <div className="mt-6 border-t border-line pt-5">
              <div className="hidden gap-2 pb-2 sm:grid sm:grid-cols-[minmax(0,1.5fr)_104px_104px_36px]">
                <span className="label">Subject</span>
                <span className="label">Marks</span>
                <span className="label">Out of</span>
                <span />
              </div>

              <div className="grid gap-3">
                {record.rows.map((row, rowIndex) => (
                  <div
                    key={row.key}
                    className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_32px] items-start gap-2 border-b border-line pb-3 last:border-b-0 last:pb-0 sm:grid-cols-[minmax(0,1.5fr)_104px_104px_36px] sm:items-center sm:border-0 sm:pb-0"
                  >
                    <div className="col-span-3 sm:col-span-1">
                      <label
                        className="field-label mb-1 block sm:hidden"
                        htmlFor={`c${level}-${row.key}-subject`}
                      >
                        Subject {rowIndex + 1}
                      </label>
                      <input
                        id={`c${level}-${row.key}-subject`}
                        className="input"
                        placeholder="Mathematics"
                        aria-label={`Class ${level} subject ${rowIndex + 1}`}
                        value={row.subject}
                        onChange={(event) =>
                          updateRow(level, row.key, { subject: event.target.value })
                        }
                        aria-invalid={Boolean(errors[`${row.key}-subject`])}
                      />
                      {errors[`${row.key}-subject`] ? (
                        <p className="field-error mt-1" role="alert">
                          {errors[`${row.key}-subject`]}
                        </p>
                      ) : null}
                    </div>
                    <div>
                      <label
                        className="field-label mb-1 block sm:hidden"
                        htmlFor={`c${level}-${row.key}-marks`}
                      >
                        Marks
                      </label>
                      <input
                        id={`c${level}-${row.key}-marks`}
                        className="input mono"
                        inputMode="decimal"
                        placeholder="85"
                        aria-label={`Class ${level} marks for subject ${rowIndex + 1}`}
                        value={row.marks}
                        onChange={(event) =>
                          updateRow(level, row.key, { marks: event.target.value })
                        }
                        aria-invalid={Boolean(errors[`${row.key}-marks`])}
                      />
                      {errors[`${row.key}-marks`] ? (
                        <p className="field-error mt-1" role="alert">
                          {errors[`${row.key}-marks`]}
                        </p>
                      ) : null}
                    </div>
                    <div>
                      <label
                        className="field-label mb-1 block sm:hidden"
                        htmlFor={`c${level}-${row.key}-max`}
                      >
                        Out of
                      </label>
                      <input
                        id={`c${level}-${row.key}-max`}
                        className="input mono"
                        inputMode="decimal"
                        placeholder="100"
                        aria-label={`Class ${level} maximum marks for subject ${rowIndex + 1}`}
                        value={row.max}
                        onChange={(event) =>
                          updateRow(level, row.key, { max: event.target.value })
                        }
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
                        aria-label={`Remove Class ${level} ${
                          row.subject || `subject ${rowIndex + 1}`
                        }`}
                        onClick={() =>
                          setEducation((current) => ({
                            ...current,
                            [level]: {
                              ...current[level],
                              rows: current[level].rows.filter(
                                (item) => item.key !== row.key,
                              ),
                            },
                          }))
                        }
                        disabled={record.rows.length === 1}
                      >
                        <X size={15} aria-hidden="true" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              {errors[`${prefix}.rows`] ? (
                <p className="field-error mt-2" role="alert">
                  {errors[`${prefix}.rows`]}
                </p>
              ) : null}

              <div className="mt-4">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() =>
                    patchRecord(level, { rows: [...record.rows, newRow()] })
                  }
                >
                  <Plus size={14} aria-hidden="true" />
                  Add subject
                </Button>
              </div>
            </div>
          </>
        )}
      </SectionCard>
    );
  }

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
        description="Maatram Foundation checks these details against the documents you upload. Enter each class exactly as it appears on the mark sheet; nothing is averaged, rounded or guessed."
      />

      <form
        onSubmit={onSubmit}
        noValidate
        className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_312px]"
      >
        <div className="grid gap-6">
          {formError ? <Alert tone="error">{formError}</Alert> : null}

          <SectionCard
            title={
              <span className="inline-flex items-baseline gap-2.5">
                <span className="mono text-[11px] font-normal text-faint">01</span>
                Applicant details
              </span>
            }
          >
            <div className="grid gap-5 sm:grid-cols-3">
              <Field
                label="Full name"
                htmlFor="applicant_name"
                error={errors.applicant_name}
                className="sm:col-span-2"
              >
                <input
                  id="applicant_name"
                  className="input"
                  autoComplete="name"
                  placeholder="As printed on every document"
                  value={form.applicant_name}
                  onChange={(event) => set("applicant_name", event.target.value)}
                  aria-invalid={Boolean(errors.applicant_name)}
                />
              </Field>

              <Field
                label="Date of birth"
                htmlFor="date_of_birth"
                error={errors.date_of_birth}
              >
                <input
                  id="date_of_birth"
                  type="date"
                  className="input"
                  value={form.date_of_birth}
                  max={new Date().toISOString().slice(0, 10)}
                  onChange={(event) => set("date_of_birth", event.target.value)}
                  aria-invalid={Boolean(errors.date_of_birth)}
                />
              </Field>

              <Field
                label="Father's name"
                htmlFor="father_name"
                error={errors.father_name}
              >
                <input
                  id="father_name"
                  className="input"
                  autoComplete="off"
                  value={form.father_name}
                  onChange={(event) => set("father_name", event.target.value)}
                  aria-invalid={Boolean(errors.father_name)}
                />
              </Field>

              <Field
                label="Mother / guardian"
                htmlFor="mother_name"
                error={errors.mother_name}
                className="sm:col-span-2"
              >
                <input
                  id="mother_name"
                  className="input"
                  autoComplete="off"
                  value={form.mother_name}
                  onChange={(event) => set("mother_name", event.target.value)}
                  aria-invalid={Boolean(errors.mother_name)}
                />
              </Field>

              <Field label="Phone" htmlFor="phone" error={errors.phone}>
                <input
                  id="phone"
                  className="input mono"
                  inputMode="tel"
                  autoComplete="tel"
                  placeholder="+91 98400 22114"
                  value={form.phone}
                  onChange={(event) => set("phone", event.target.value)}
                  aria-invalid={Boolean(errors.phone)}
                />
              </Field>

              <YesNo
                label="Orphan"
                name="is_orphan"
                value={form.is_orphan}
                onChange={(value) => set("is_orphan", value)}
              />

              <YesNo
                label="First graduate in the family"
                name="is_first_graduate"
                value={form.is_first_graduate}
                onChange={(value) => set("is_first_graduate", value)}
              />

              <Field
                label="Address"
                htmlFor="address"
                error={errors.address}
                className="sm:col-span-3"
              >
                <textarea
                  id="address"
                  className="textarea"
                  rows={3}
                  autoComplete="street-address"
                  placeholder="Door number, street, locality, district, PIN"
                  value={form.address}
                  onChange={(event) => set("address", event.target.value)}
                  aria-invalid={Boolean(errors.address)}
                />
              </Field>
            </div>
          </SectionCard>

          {educationSection(10, "02")}
          {educationSection(11, "03")}
          {educationSection(12, "04")}
        </div>

        <aside className="grid content-start gap-5 lg:sticky lg:top-8">
          <div className="card p-5">
            <h2 className="text-[14px] font-semibold">Before you file</h2>
            <ul className="mt-3 grid gap-2.5">
              <Requirement>Every mark is entered exactly as printed on the sheet.</Requirement>
              <Requirement>
                Class 10 and Class 12 records are required. Class 11 is optional.
              </Requirement>
              <Requirement>
                The documents you attach next are checked against these details.
              </Requirement>
            </ul>

            <Button type="submit" block className="mt-5 h-11" busy={create.isPending}>
              File application
            </Button>
            <p className="mt-2.5 text-center text-[11px] leading-relaxed text-faint">
              Tesseract OCR and fixed rules only. No generative AI at any stage.
            </p>
          </div>

          <div className="card-flat p-5">
            <h2 className="text-[13px] font-semibold">How Maatram Foundation checks it</h2>
            <ol className="mt-3 grid gap-3 text-[12px] leading-relaxed text-muted">
              <li className="flex gap-3">
                <span className="mono text-[11px] text-faint">01</span>
                <span>Attach your mark sheets, identity and supporting documents.</span>
              </li>
              <li className="flex gap-3">
                <span className="mono text-[11px] text-faint">02</span>
                <span>The checker reads each document and measures the photograph.</span>
              </li>
              <li className="flex gap-3">
                <span className="mono text-[11px] text-faint">03</span>
                <span>
                  Clean documents verify automatically. Doubtful cases go to a reviewer with
                  the reason attached.
                </span>
              </li>
            </ol>
          </div>
        </aside>
      </form>
    </AppShell>
  );
}
