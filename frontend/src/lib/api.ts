const TOKEN_KEY = "maatram.token";

/**
 * Backend origin from VITE_API_URL, without a trailing slash and without
 * `/api` (each request below appends it). When the variable is unset — the
 * normal local development case — requests stay relative so the Vite proxy
 * forwards `/api` to http://127.0.0.1:8000.
 */
const API_ORIGIN = (import.meta.env.VITE_API_URL ?? "").replace(/\/+$/, "");
const API_BASE = `${API_ORIGIN}/api`;

export type Role = "student" | "admin";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  created_at: string;
}

export interface Mark {
  id: number;
  subject: string;
  marks_obtained: number;
  max_marks: number | null;
  grade: string | null;
}

export interface EducationSummary {
  id: number;
  class_level: number;
  register_number: string;
  exam_year: number;
  board: string;
}

export interface EducationRecord extends EducationSummary {
  marks: Mark[];
}

export interface EducationRecordInput {
  register_number: string;
  exam_year: number;
  board: string;
  marks: { subject: string; marks_obtained: number; max_marks: number | null }[];
}

export type DocumentKind =
  | "marksheet_10"
  | "marksheet_11"
  | "marksheet_12"
  | "marksheet"
  | "aadhaar"
  | "income_certificate"
  | "community_certificate"
  | "first_graduate_certificate"
  | "photo"
  | "other";

export interface DocumentRecord {
  id: number;
  kind: DocumentKind;
  kind_label: string;
  classification: Record<string, unknown> | null;
  masked_aadhaar: string | null;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  page_count: number;
  width: number | null;
  height: number | null;
  duplicate_of_id: number | null;
  created_at: string;
}

export interface UploadResult {
  document: DocumentRecord;
  warnings: string[];
}

export interface Finding {
  id: number;
  category: string;
  field: string;
  subject_norm: string | null;
  result: string;
  entered_value: string | null;
  uploaded_value: string | null;
  measured_value: string | null;
  required_value: string | null;
  difference: number | null;
  detail: string | null;
  severity: string;
  confidence: number | null;
  meta: Record<string, unknown> | null;
}

export interface IdentityMatrixValue {
  source: string;
  kind: string;
  document_id: number | null;
  filename: string | null;
  value: string;
  status: string;
  similarity: number | null;
}

export interface IdentityMatrixField {
  field: string;
  label: string;
  status: string;
  detail: string;
  values: IdentityMatrixValue[];
}

export interface IdentityMatrix {
  fields: IdentityMatrixField[];
  checked: number;
  mismatched: number;
}

export interface Run {
  id: number;
  status: string;
  overall: string | null;
  summary: Record<string, unknown>;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
  findings: Finding[];
}

export type ApplicationStatus =
  | "draft"
  | "submitted"
  | "processing"
  | "needs_review"
  | "verified"
  | "approved"
  | "rejected";

export interface Application {
  id: number;
  reference: string;
  applicant_name: string;
  date_of_birth: string;
  father_name: string;
  mother_name: string;
  phone: string;
  address: string;
  is_orphan: boolean;
  is_first_graduate: boolean;
  status: ApplicationStatus;
  created_at: string;
  submitted_at: string | null;
  classes: EducationSummary[];
}

export interface ExtractMark {
  id: number;
  document_id: number;
  subject_raw: string;
  subject_norm: string | null;
  marks_obtained: number | null;
  max_marks: number | null;
  grade: string | null;
  confidence: number;
  page: number;
  corrected_subject: string | null;
  corrected_marks: number | null;
}

export interface DocumentVerdict {
  id: number;
  kind: string;
  label: string;
  filename: string;
  status: "pass" | "review" | "fail" | "pending";
  findings: number;
  critical: number;
  warnings: number;
  classification: Record<string, unknown> | null;
  masked_aadhaar: string | null;
}

export interface MarkCorrectionResult {
  mark: ExtractMark;
  run: { id: number; status: string };
}

export interface ApplicationReview {
  id: number;
  status: string;
  priority: number;
  reasons: string[];
  run_id: number | null;
  assigned_to_email: string | null;
  decision_comment: string | null;
  decided_by_email: string | null;
  decided_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApplicationDetail extends Application {
  education: EducationRecord[];
  documents: DocumentRecord[];
  latest_run: Run | null;
  extracted_marks: ExtractMark[];
  review: ApplicationReview | null;
}

export interface ReviewQueueItem {
  id: number;
  application_id: number;
  reference: string;
  applicant_name: string;
  class_12_year: number | null;
  application_status: string;
  status: string;
  priority: number;
  reasons: string[];
  run_id: number | null;
  overall: string | null;
  matched: number;
  mismatched: number;
  critical: number;
  warnings: number;
  ocr_confidence: number | null;
  assigned_to_email: string | null;
  decided_by_email: string | null;
  decision_comment: string | null;
  decided_at: string | null;
  created_at: string;
  updated_at: string;
  run_finished_at: string | null;
}

export interface ReviewQueue {
  items: ReviewQueueItem[];
  counts: Record<string, number>;
  total: number;
  page: number;
  page_size: number;
  generated_at: string;
}

export interface ApplicationList {
  items: Application[];
  total: number;
}

export interface AdminActivity {
  id: number;
  application_id: number;
  reference: string;
  applicant_name: string;
  class_12_year: number | null;
  status: string;
  overall: string | null;
  verdict: string | null;
  matched: number;
  mismatched: number;
  critical: number;
  warnings: number;
  engine: string | null;
  ocr_confidence: number | null;
  finished_at: string | null;
  error: string | null;
}

export interface AdminOverview {
  total_applications: number;
  students: number;
  by_status: Record<string, number>;
  open_reviews: number;
  mismatch_findings: number;
  photo_failures: number;
  recent: Application[];
  verified: number;
  processing: number;
  activity: AdminActivity[];
  generated_at: string;
}

export interface AccuracyTarget {
  value: number;
  target: number;
  met: boolean;
}

export interface AccuracyVariant {
  variant: string;
  cases: number;
  identity_accuracy: number;
  subject_recall: number;
  mark_accuracy: number;
  mean_confidence: number;
}

export interface AccuracyRule {
  rule: string;
  tested: number;
  correct: number;
  accuracy: number;
}

export interface AccuracyDocumentKind {
  kind: string;
  label: string;
  short: string;
  fixtures: number;
  fields_total: number;
  fields_correct: number;
  field_accuracy: number;
  classification_accuracy: number;
}

export interface AccuracyDocumentSummary {
  fixtures: number;
  fields_total: number;
  fields_correct: number;
  field_accuracy: number;
  classification_accuracy: number;
  checksum: { tested: number; correct: number; accuracy: number };
  by_kind: AccuracyDocumentKind[];
}

export interface AccuracyClassificationLabel {
  kind: string;
  label: string;
  short: string;
}

export interface AccuracyClassification {
  labels: AccuracyClassificationLabel[];
  matrix: number[][];
  correct: number;
  total: number;
  accuracy: number;
  by_expected: {
    kind: string;
    label: string;
    short: string;
    correct: number;
    total: number;
    accuracy: number;
  }[];
}

export interface AccuracySummary {
  status: string;
  dataset: string;
  cases: number;
  field_accuracy: number;
  fields: { name: number; register_number: number; exam_year: number };
  mark_sheets?: {
    total: number;
    class_10: number;
    class_11: number;
    class_12: number;
  };
  subjects: {
    total: number;
    found: number;
    found_rate: number;
    marks_exact: number;
    mark_accuracy: number;
    rows_exact: number;
    max_marks_exact: number;
  };
  mismatch: {
    precision: number;
    recall: number;
    f1: number;
    tp: number;
    fp: number;
    fn: number;
    matrix: { tp: number; fp: number; fn: number; tn: number; accuracy: number };
  };
  comparison_engine: { precision: number; recall: number; f1: number; tp: number; fp: number; fn: number };
  missing: { precision: number; recall: number; f1: number; tp: number; fp: number; fn: number };
  extras: { expected: number; detected: number };
  ocr_confidence: number;
  mean_duration_ms: number;
  photos: {
    rule_accuracy: number;
    labels_correct: number;
    labels_total: number;
    critical_accuracy: number;
    critical_correct: number;
    fixtures: number;
    rules: AccuracyRule[];
    cases: {
      id: string;
      note: string;
      expected: Record<string, string>;
      actual: Record<string, string>;
      faces: number | null;
      expected_critical: string[];
      actual_critical: string[];
      critical_match: boolean;
      wrong: string[];
      error: string | null;
    }[];
  };
  documents?: AccuracyDocumentSummary;
  classification?: AccuracyClassification;
  counts?: {
    class_12: number;
    class_11: number;
    mark_sheets: number;
    documents: number;
    photos: number;
  } | null;
  variants: AccuracyVariant[];
  targets: Record<
    "field_accuracy" | "document_field_accuracy" | "mismatch_recall" | "photo_rule_accuracy",
    AccuracyTarget
  >;
  errors: { case: string; variant: string; error: string }[];
  error?: string;
  finished_at?: string;
  started_at?: string | null;
}

export interface AccuracyRun {
  id: number;
  dataset: string;
  total_cases: number;
  status: string;
  summary: AccuracySummary;
  created_at: string;
  report_path: string;
}

export interface AccuracyHistoryEntry {
  id: number;
  dataset: string;
  total_cases: number;
  status: string;
  created_at: string;
  field_accuracy: number | null;
  document_accuracy: number | null;
  mismatch_recall: number | null;
  photo_accuracy: number | null;
}

export interface AccuracyResponse {
  latest: AccuracyRun | null;
  history: AccuracyHistoryEntry[];
  running: boolean;
}

export interface DocumentKindConfig {
  label: string;
  short: string;
  extractor: string;
  class_level?: number;
  slot: "single" | "multiple";
  required_fields: string[];
  generic_required?: boolean;
}

export interface MetaConfig {
  app: { name: string; programme: string; problem: string; timezone: string };
  subjects: {
    required: string[];
    by_class: Record<string, string[]>;
    known: string[];
    fuzzy_threshold: number;
  };
  uploads: { max_mb: number; extensions: string[]; max_pages: number };
  photo: {
    min_width: number;
    min_height: number;
    max_width: number;
    max_height: number;
    min_aspect_ratio: number;
    max_aspect_ratio: number;
    min_size_kb: number;
    max_size_kb: number;
    allowed_formats: string[];
    min_sharpness: number;
    min_brightness: number;
    max_brightness: number;
    face_check: boolean;
  };
  ocr: { engine: string; low_confidence: number };
  documents: {
    kinds: Record<string, DocumentKindConfig>;
    field_labels: Record<string, string>;
    classifier: { min_score: number; ambiguous_margin: number };
    aadhaar: {
      number_length: number;
      mask_prefix: string;
      qr: { required: boolean; mismatch_severity: string };
    };
    income: {
      max_annual_income: number;
      validity_months: number;
      future_tolerance_days: number;
    };
    community: { known_values: string[]; future_tolerance_days: number };
    first_graduate: { future_tolerance_days: number };
  };
}

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Check that the API is running.");
  }

  if (response.status === 401) {
    setToken(null);
    window.dispatchEvent(new Event("maatram:unauthorized"));
  }

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }

  if (!response.ok) {
    const detail =
      typeof body === "object" && body && "detail" in body
        ? formatDetail((body as { detail: unknown }).detail)
        : `Request failed (${response.status})`;
    throw new ApiError(response.status, detail);
  }

  return body as T;
}

function formatDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item) {
          const field = "loc" in item ? String((item.loc as unknown[]).slice(-1)[0]) : "field";
          return `${field}: ${String((item as { msg: unknown }).msg)}`;
        }
        return String(item);
      })
      .join(". ");
  }
  return "Something went wrong. Try again.";
}

/**
 * Uploads with XMLHttpRequest rather than fetch: file uploads are the one
 * place where real progress matters, and fetch still cannot report it.
 */
export function uploadDocument(
  applicationId: number | string,
  file: File,
  kind: Exclude<DocumentKind, "other"> | "auto",
  onProgress?: (percent: number) => void,
): Promise<UploadResult> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${API_BASE}/applications/${applicationId}/documents`);
    const token = getToken();
    if (token) request.setRequestHeader("Authorization", `Bearer ${token}`);

    request.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    });

    request.addEventListener("load", () => {
      let body: unknown = null;
      try {
        body = JSON.parse(request.responseText);
      } catch {
        body = null;
      }
      if (request.status >= 200 && request.status < 300) {
        resolve(body as UploadResult);
        return;
      }
      if (request.status === 401) {
        setToken(null);
        window.dispatchEvent(new Event("maatram:unauthorized"));
      }
      const detail =
        body && typeof body === "object" && "detail" in body
          ? formatDetail((body as { detail: unknown }).detail)
          : `Upload failed (${request.status})`;
      reject(new ApiError(request.status, detail));
    });

    request.addEventListener("error", () => {
      reject(new ApiError(0, "Cannot reach the server. Check that the API is running."));
    });

    const form = new FormData();
    form.append("kind", kind);
    form.append("file", file);
    request.send(form);
  });
}

export async function documentBlob(documentId: number): Promise<Blob> {
  const headers = new Headers();
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_BASE}/documents/${documentId}/file`, { headers });
  if (!response.ok) {
    throw new ApiError(response.status, "Could not open the stored file.");
  }
  return response.blob();
}

export async function reportBlob(applicationId: number | string): Promise<Blob> {
  const headers = new Headers();
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_BASE}/applications/${applicationId}/report.pdf`, { headers });
  if (!response.ok) {
    if (response.status === 401) {
      setToken(null);
      window.dispatchEvent(new Event("maatram:unauthorized"));
    }
    let detail = "The report could not be built.";
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (body?.detail) detail = formatDetail(body.detail);
    } catch {
      /* the server did not send JSON */
    }
    throw new ApiError(response.status, detail);
  }
  return response.blob();
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string; token_type: string; user: User }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  register: (full_name: string, email: string, password: string) =>
    request<{ access_token: string; token_type: string; user: User }>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ full_name, email, password }),
    }),
  me: () => request<User>("/auth/me"),
  config: () => request<MetaConfig>("/meta/config"),
  applications: (params?: { q?: string; status?: string; page?: number; page_size?: number }) => {
    const query = new URLSearchParams();
    if (params?.q) query.set("q", params.q);
    if (params?.status) query.set("status", params.status);
    if (params?.page) query.set("page", String(params.page));
    if (params?.page_size) query.set("page_size", String(params.page_size));
    const suffix = query.toString() ? `?${query}` : "";
    return request<ApplicationList>(`/applications${suffix}`);
  },
  application: (id: number | string) => request<ApplicationDetail>(`/applications/${id}`),
  validateApplication: (id: number | string) =>
    request<Run>(`/applications/${id}/validate`, { method: "POST" }),
  deleteDocument: (documentId: number) =>
    request<void>(`/documents/${documentId}`, { method: "DELETE" }),
  correctExtractedMark: (
    documentId: number,
    markId: number,
    payload: { subject: string | null; marks_obtained: number },
  ) =>
    request<MarkCorrectionResult>(`/admin/documents/${documentId}/marks/${markId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  createApplication: (payload: {
    applicant_name: string;
    date_of_birth: string;
    father_name: string;
    mother_name: string;
    phone: string;
    address: string;
    is_orphan: boolean;
    is_first_graduate: boolean;
    class_10: EducationRecordInput;
    class_11: EducationRecordInput | null;
    class_12: EducationRecordInput;
  }) =>
    request<ApplicationDetail>("/applications", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  adminOverview: () => request<AdminOverview>("/admin/overview"),
  reviews: (status = "active", page = 1) =>
    request<ReviewQueue>(`/admin/reviews?status=${status}&page=${page}`),
  decideReview: (reviewId: number, decision: "approve" | "reject", comment: string) =>
    request<{
      id: number;
      status: string;
      application_id: number;
      application_status: string;
      decided_at: string;
      decided_by_email: string;
    }>(`/admin/reviews/${reviewId}/${decision}`, {
      method: "POST",
      body: JSON.stringify({ comment }),
    }),
  accuracy: () => request<AccuracyResponse>("/admin/accuracy"),
  runAccuracy: () =>
    request<{ id: number; status: string }>("/admin/accuracy/run", { method: "POST" }),
  audit: (page = 1, applicationId?: number) =>
    request<{ total: number; items: AuditEntry[] }>(
      `/admin/audit?page=${page}${applicationId ? `&application_id=${applicationId}` : ""}`,
    ),
};

export interface AuditEntry {
  id: number;
  action: string;
  entity_type: string;
  entity_id: number | null;
  application_id: number | null;
  actor_email: string | null;
  detail: Record<string, unknown>;
  ip: string | null;
  created_at: string;
}
