import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Camera,
  Download,
  FileText,
  GraduationCap,
  IdCard,
  ImageOff,
  Loader2,
  Lock,
  Trash2,
  Upload,
  Users,
  X,
} from "lucide-react";
import { clsx } from "clsx";
import { api, documentBlob, uploadDocument, ApiError } from "../lib/api";
import type { DocumentKind, DocumentRecord } from "../lib/api";
import { formatBytes } from "../lib/query";
import { Button } from "./ui";

/* ---------------------------------------------------------------------------
   One authenticated blob per open file. A token cannot ride on <img src>, so
   every preview is fetched through the API and shown from an object URL.
--------------------------------------------------------------------------- */

function useDocumentUrl(documentId: number | null) {
  const [state, setState] = useState<{
    url: string | null;
    loading: boolean;
    failed: boolean;
  }>({ url: null, loading: Boolean(documentId), failed: false });

  useEffect(() => {
    if (!documentId) {
      setState({ url: null, loading: false, failed: false });
      return;
    }
    let alive = true;
    let created: string | null = null;
    setState({ url: null, loading: true, failed: false });
    documentBlob(documentId)
      .then((blob) => {
        if (!alive) return;
        created = URL.createObjectURL(blob);
        setState({ url: created, loading: false, failed: false });
      })
      .catch(() => {
        if (alive) setState({ url: null, loading: false, failed: true });
      });
    return () => {
      alive = false;
      if (created) URL.revokeObjectURL(created);
    };
  }, [documentId]);

  return state;
}

function isImage(document: DocumentRecord): boolean {
  return document.mime_type.startsWith("image/");
}

function kindLabel(document: DocumentRecord): string {
  return document.kind_label || document.kind.replaceAll("_", " ");
}

function classificationNote(document: DocumentRecord): string | null {
  const classification = document.classification;
  if (!classification) return null;
  if (classification.ambiguous === true) {
    return "More than one type matched. Confirm this file is in the right slot.";
  }
  const method = String(classification.method ?? "");
  if (method === "keyword") {
    const confidence =
      typeof classification.confidence === "number"
        ? ` (${Math.round(classification.confidence)}% confidence)`
        : "";
    return `Read from the printed content${confidence}.`;
  }
  if (method === "image_heuristic") return "Read as a portrait photograph.";
  if (method === "override") return "Type chosen by you.";
  return null;
}

/* ---------------------------------------------------------------------------
   Viewer
--------------------------------------------------------------------------- */

function DocumentViewer({
  file,
  onClose,
}: {
  file: DocumentRecord;
  onClose: () => void;
}) {
  const { url, loading, failed } = useDocumentUrl(file.id);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.document.addEventListener("keydown", onKey);
    const previous = window.document.body.style.overflow;
    window.document.body.style.overflow = "hidden";
    return () => {
      window.document.removeEventListener("keydown", onKey);
      window.document.body.style.overflow = previous;
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center p-4 sm:p-8"
      role="dialog"
      aria-modal="true"
      aria-label={`Preview of ${file.original_filename}`}
    >
      <button
        type="button"
        className="absolute inset-0 bg-ink/65"
        aria-label="Close preview"
        onClick={onClose}
      />
      <div className="relative flex max-h-full w-full max-w-[980px] flex-col overflow-hidden rounded-[3px] border border-line-strong bg-surface shadow-[0_32px_80px_-40px_rgb(23_22_16/0.7)]">
        <div className="flex items-center justify-between gap-4 border-b border-line px-5 py-3">
          <div className="min-w-0">
            <p className="truncate text-[13px] font-medium">{file.original_filename}</p>
            <p className="mono mt-0.5 text-[10.5px] text-muted">
              {kindLabel(file)}
              {file.masked_aadhaar ? ` · ${file.masked_aadhaar}` : ""} · {formatBytes(file.size_bytes)}
              {file.page_count > 1 ? ` · ${file.page_count} pages` : ""}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            {url ? (
              <a href={url} download={file.original_filename} className="btn btn-ghost btn-sm">
                <Download size={14} aria-hidden="true" />
                Download
              </a>
            ) : null}
            <button
              type="button"
              className="btn btn-ghost h-8 w-8 p-0"
              aria-label="Close preview"
              onClick={onClose}
            >
              <X size={17} aria-hidden="true" />
            </button>
          </div>
        </div>

        <div className="min-h-[280px] flex-1 overflow-auto bg-paper-deep/50 p-4 sm:p-6">
          {loading ? (
            <div className="grid min-h-[240px] place-items-center">
              <span className="inline-flex items-center gap-2 text-[13px] text-muted">
                <Loader2 size={15} className="animate-spin" aria-hidden="true" />
                Decrypting file
              </span>
            </div>
          ) : failed || !url ? (
            <div className="grid min-h-[240px] place-items-center text-center">
              <div>
                <ImageOff size={20} className="mx-auto text-muted" aria-hidden="true" />
                <p className="mt-2 text-[13px] font-medium">This file could not be opened</p>
                <p className="mt-1 text-[12px] text-muted">
                  The stored copy may have been removed. Ask the applicant to upload it again.
                </p>
              </div>
            </div>
          ) : isImage(file) ? (
            <img
              src={url}
              alt={file.original_filename}
              className="mx-auto max-h-[68vh] w-auto max-w-full object-contain"
            />
          ) : (
            <iframe
              src={url}
              title={file.original_filename}
              className="h-[68vh] w-full border-0 bg-white"
            />
          )}
        </div>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------------
   File furniture
--------------------------------------------------------------------------- */

function PhotoFrame({
  document,
  empty,
  active,
}: {
  document: DocumentRecord | null;
  empty: React.ReactNode;
  active?: boolean;
}) {
  const { url, loading, failed } = useDocumentUrl(document?.id ?? null);

  return (
    <div
      className={clsx(
        "relative grid aspect-[3/4] w-full place-items-center overflow-hidden rounded-[2px] border bg-paper-deep/40",
        active ? "border-accent ring-2 ring-accent/15" : "border-line-strong",
      )}
    >
      {document ? (
        loading ? (
          <Loader2 size={18} className="animate-spin text-muted" aria-hidden="true" />
        ) : url && !failed ? (
          <img
            src={url}
            alt={`Profile photo ${document.original_filename}`}
            className="h-full w-full object-cover"
          />
        ) : (
          <ImageOff size={18} className="text-muted" aria-hidden="true" />
        )
      ) : (
        empty
      )}
    </div>
  );
}

function FileGlyph({ document }: { document: DocumentRecord }) {
  return (
    <span className="grid h-9 w-9 shrink-0 place-items-center rounded-[2px] border border-line bg-paper text-muted">
      {isImage(document) ? (
        <FileText size={15} aria-hidden="true" />
      ) : (
        <span className="font-mono text-[9px] font-medium tracking-[0.04em]">PDF</span>
      )}
    </span>
  );
}

function RemoveDocument({
  document,
  onRemove,
}: {
  document: DocumentRecord;
  onRemove: (id: number) => Promise<void>;
}) {
  const [confirming, setConfirming] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function remove() {
    setRemoving(true);
    setError(null);
    try {
      await onRemove(document.id);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.detail : "The file could not be removed.");
      setRemoving(false);
    }
  }

  if (confirming) {
    return (
      <span className="flex flex-wrap items-center justify-end gap-1">
        <span className="text-[10.5px] text-muted">Remove?</span>
        <button
          type="button"
          className="btn btn-sm border border-fail/40 px-2 text-fail hover:bg-fail hover:text-white"
          disabled={removing}
          onClick={() => void remove()}
        >
          {removing ? "Removing" : "Remove"}
        </button>
        <button
          type="button"
          className="btn btn-ghost btn-sm px-2"
          disabled={removing}
          onClick={() => setConfirming(false)}
        >
          Keep
        </button>
        {error ? (
          <span className="w-full text-right text-[10.5px] text-fail" role="alert">
            {error}
          </span>
        ) : null}
      </span>
    );
  }

  return (
    <button
      type="button"
      className="btn btn-ghost h-8 w-8 p-0 text-muted hover:text-fail"
      aria-label={`Remove ${document.original_filename}`}
      onClick={() => {
        setError(null);
        setConfirming(true);
      }}
    >
      <Trash2 size={14} aria-hidden="true" />
    </button>
  );
}

function FileRow({
  document,
  readOnly,
  onView,
  onRemove,
}: {
  document: DocumentRecord;
  readOnly?: boolean;
  onView: (document: DocumentRecord) => void;
  onRemove: (id: number) => Promise<void>;
}) {
  const note = classificationNote(document);
  return (
    <li className="rounded-[2px] border border-line bg-raised px-3 py-2.5">
      <div className="flex items-start gap-3">
        <FileGlyph document={document} />
        <button
          type="button"
          className="min-w-0 flex-1 text-left"
          onClick={() => onView(document)}
          aria-label={`Open ${document.original_filename}`}
        >
          <span className="block truncate text-[13px] font-medium">
            {document.original_filename}
          </span>
          <span className="mono mt-0.5 flex flex-wrap items-center gap-x-2 text-[10.5px] text-muted">
            <span>
              {document.page_count} page{document.page_count === 1 ? "" : "s"}
            </span>
            <span className="text-line-strong" aria-hidden="true">
              ·
            </span>
            <span>{formatBytes(document.size_bytes)}</span>
            {document.width && document.height ? (
              <>
                <span className="text-line-strong" aria-hidden="true">
                  ·
                </span>
                <span>
                  {document.width} × {document.height}
                </span>
              </>
            ) : null}
            {document.masked_aadhaar ? (
              <>
                <span className="text-line-strong" aria-hidden="true">
                  ·
                </span>
                <span className="text-ink-soft">{document.masked_aadhaar}</span>
              </>
            ) : null}
            {document.duplicate_of_id ? (
              <>
                <span className="text-line-strong" aria-hidden="true">
                  ·
                </span>
                <span className="flex items-center gap-1 text-warn">
                  <AlertTriangle size={10} aria-hidden="true" />
                  Duplicate
                </span>
              </>
            ) : null}
          </span>
          {note ? (
            <span className="mt-1 block text-[10.5px] leading-relaxed text-muted">{note}</span>
          ) : null}
        </button>

        <div className="flex shrink-0 items-center gap-0.5">
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => onView(document)}
          >
            View
          </button>
          {readOnly ? null : <RemoveDocument document={document} onRemove={onRemove} />}
        </div>
      </div>
    </li>
  );
}

/* ---------------------------------------------------------------------------
   Upload helpers
--------------------------------------------------------------------------- */

type UploadKind = Exclude<DocumentKind, "other"> | "auto";

interface QueueItem {
  key: string;
  name: string;
  kind: UploadKind;
  progress: number;
  state: "uploading" | "error";
  error?: string;
}

let queueId = 0;

function useDropZone(onFiles: (files: File[]) => void, enabled: boolean) {
  const depth = useRef(0);
  const [active, setActive] = useState(false);

  return {
    active,
    handlers: {
      onDragEnter: (event: React.DragEvent) => {
        event.preventDefault();
        if (!enabled) return;
        depth.current += 1;
        setActive(true);
      },
      onDragOver: (event: React.DragEvent) => {
        event.preventDefault();
        if (enabled) event.dataTransfer.dropEffect = "copy";
      },
      onDragLeave: (event: React.DragEvent) => {
        event.preventDefault();
        depth.current = Math.max(0, depth.current - 1);
        if (depth.current === 0) setActive(false);
      },
      onDrop: (event: React.DragEvent) => {
        event.preventDefault();
        depth.current = 0;
        setActive(false);
        if (enabled) onFiles(Array.from(event.dataTransfer.files));
      },
    },
  };
}

const EXTENSIONS = ["pdf", "jpg", "jpeg", "png"];

function fileProblem(file: File, kind: UploadKind, maxMb: number): string | null {
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  if (!EXTENSIONS.includes(extension)) {
    return "Use a PDF, JPG or PNG file.";
  }
  if (kind === "photo" && extension === "pdf") {
    return "A profile photo must be a JPEG or PNG.";
  }
  if (file.size > maxMb * 1024 * 1024) {
    return `This file is ${(file.size / (1024 * 1024)).toFixed(1)} MB; the limit is ${maxMb} MB.`;
  }
  return null;
}

function singleSlot(kind: UploadKind): boolean {
  return ["photo", "aadhaar", "income_certificate", "community_certificate", "first_graduate_certificate"].includes(
    kind,
  );
}

/* ---------------------------------------------------------------------------
   Panel
--------------------------------------------------------------------------- */

const MARK_SHEET_LEVELS = [10, 11, 12] as const;

const SUPPORTING_SLOTS: {
  kind: Exclude<UploadKind, "auto" | "photo">;
  title: string;
  hint: string;
  icon: typeof IdCard;
}[] = [
  {
    kind: "aadhaar",
    title: "Aadhaar",
    hint: "Checksum and QR code are checked. Only the last four digits are shown.",
    icon: IdCard,
  },
  {
    kind: "income_certificate",
    title: "Income certificate",
    hint: "Compared with the configured income limit and validity window.",
    icon: FileText,
  },
  {
    kind: "community_certificate",
    title: "Community certificate",
    hint: "The community and issue date are read from the certificate.",
    icon: Users,
  },
  {
    kind: "first_graduate_certificate",
    title: "First graduate certificate",
    hint: "The certificate must agree with the first graduate claim.",
    icon: GraduationCap,
  },
];

export function DocumentsPanel({
  applicationId,
  documents,
  readOnly,
}: {
  applicationId: number;
  documents: DocumentRecord[];
  readOnly?: boolean;
}) {
  const queryClient = useQueryClient();
  const config = useQuery({ queryKey: ["config"], queryFn: api.config });
  const maxMb = config.data?.uploads.max_mb ?? 15;

  function documentsOf(kind: DocumentKind): DocumentRecord[] {
    if (kind === "marksheet_12") {
      return documents.filter(
        (document) => document.kind === "marksheet_12" || document.kind === "marksheet",
      );
    }
    return documents.filter((document) => document.kind === kind);
  }

  const photo = documentsOf("photo")[0] ?? null;

  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [viewing, setViewing] = useState<DocumentRecord | null>(null);
  const [pendingKind, setPendingKind] = useState<UploadKind | null>(null);

  const fileInput = useRef<HTMLInputElement>(null);
  const photoInput = useRef<HTMLInputElement>(null);
  const uploading = queue.some((item) => item.state === "uploading");

  function targetLabel(kind: UploadKind): string {
    if (kind === "auto") return "Automatic detection";
    return config.data?.documents.kinds[kind]?.label ?? kind.replaceAll("_", " ");
  }

  function updateItem(key: string, patch: Partial<QueueItem>) {
    setQueue((current) => current.map((item) => (item.key === key ? { ...item, ...patch } : item)));
  }

  function dismissItem(key: string) {
    setQueue((current) => current.filter((item) => item.key !== key));
  }

  async function startUploads(files: File[], kind: UploadKind) {
    if (readOnly || files.length === 0) return;
    setWarnings([]);

    const accepted: File[] = [];
    const rejected: QueueItem[] = [];

    for (const file of files) {
      if (singleSlot(kind) && accepted.length === 1) break;
      const problem = fileProblem(file, kind, maxMb);
      if (problem) {
        rejected.push({
          key: `reject-${queueId++}`,
          name: file.name,
          kind,
          progress: 0,
          state: "error",
          error: problem,
        });
      } else {
        accepted.push(file);
      }
    }

    if (rejected.length > 0) {
      setQueue((current) => [...current, ...rejected]);
    }

    for (const file of accepted) {
      const key = `upload-${queueId++}`;
      setQueue((current) => [
        ...current,
        { key, name: file.name, kind, progress: 0, state: "uploading" },
      ]);
      try {
        const result = await uploadDocument(applicationId, file, kind, (percent) => {
          updateItem(key, { progress: percent });
        });
        setQueue((current) => current.filter((item) => item.key !== key));
        if (result.warnings.length > 0) {
          setWarnings((current) => [...current, ...result.warnings]);
        }
        await queryClient.invalidateQueries({ queryKey: ["application", String(applicationId)] });
        await queryClient.invalidateQueries({ queryKey: ["application", applicationId] });
        await queryClient.invalidateQueries({ queryKey: ["applications"] });
      } catch (caught) {
        updateItem(key, {
          state: "error",
          error:
            caught instanceof ApiError ? caught.detail : "The upload failed before it finished.",
        });
      }
    }
  }

  async function removeDocument(documentId: number) {
    await api.deleteDocument(documentId);
    await queryClient.invalidateQueries({ queryKey: ["application", String(applicationId)] });
    await queryClient.invalidateQueries({ queryKey: ["application", applicationId] });
    await queryClient.invalidateQueries({ queryKey: ["applications"] });
  }

  function choose(kind: UploadKind) {
    if (readOnly || uploading) return;
    setPendingKind(kind);
    if (kind === "photo") {
      photoInput.current?.click();
    } else {
      fileInput.current?.click();
    }
  }

  const autoZone = useDropZone(
    (files) => void startUploads(files, "auto"),
    !readOnly && !uploading,
  );

  const supportingDocuments = SUPPORTING_SLOTS.map((slot) => ({
    ...slot,
    documents: documentsOf(slot.kind),
  }));

  return (
    <section className="card" id="documents">
      <div className="card-head">
        <h2 className="section-title">Documents</h2>
        <span className="flex items-center gap-1.5 text-[11px] text-muted">
          <Lock size={12} aria-hidden="true" />
          Encrypted at rest
        </span>
      </div>

      {readOnly ? (
        <div className="flex items-start gap-2.5 border-b border-line bg-paper-deep/35 px-5 py-3">
          <Lock size={13} className="mt-0.5 shrink-0 text-muted" aria-hidden="true" />
          <p className="text-[11.5px] leading-relaxed text-muted">
            Read-only. Documents are uploaded by the applicant. Open any file to inspect the
            original scan.
          </p>
        </div>
      ) : (
        <div className="border-b border-line p-5">
          <input
            ref={fileInput}
            type="file"
            accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
            multiple
            className="sr-only"
            tabIndex={-1}
            onChange={(event) => {
              const files = Array.from(event.target.files ?? []);
              event.target.value = "";
              const kind = pendingKind ?? "auto";
              setPendingKind(null);
              void startUploads(files, kind);
            }}
          />
          <input
            ref={photoInput}
            type="file"
            accept=".jpg,.jpeg,.png,image/jpeg,image/png"
            className="sr-only"
            tabIndex={-1}
            onChange={(event) => {
              const files = Array.from(event.target.files ?? []);
              event.target.value = "";
              setPendingKind(null);
              void startUploads(files, "photo");
            }}
          />
          <div
            {...autoZone.handlers}
            className={clsx(
              "rounded-[2px] border border-dashed px-4 py-4 transition-colors duration-150",
              autoZone.active
                ? "border-accent bg-accent-wash/60"
                : "border-line-strong bg-paper-deep/25",
            )}
          >
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
              <Upload
                size={17}
                className={clsx("mt-0.5 shrink-0", autoZone.active ? "text-accent" : "text-muted")}
                aria-hidden="true"
              />
              <div className="min-w-0 flex-1">
                <p className="text-[13px] font-medium">
                  {autoZone.active ? "Release to attach" : "Drop a document to read its type"}
                </p>
                <p className="mt-0.5 max-w-[62ch] text-[11.5px] leading-relaxed text-muted">
                  The content is read first, then placed in a slot below. If the type is wrong,
                  remove it and attach it to the correct slot. PDF, JPG or PNG, up to {maxMb} MB
                  each.
                </p>
              </div>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                className="shrink-0"
                disabled={uploading}
                onClick={() => choose("auto")}
              >
                Choose files
              </Button>
            </div>
          </div>

          {queue.length > 0 ? (
            <ul className="mt-3 grid gap-2" aria-live="polite">
              {queue.map((item) => (
                <li
                  key={item.key}
                  className={clsx(
                    "rounded-[2px] border px-3 py-2.5",
                    item.state === "error"
                      ? "border-fail/30 bg-fail-wash/60"
                      : "border-line bg-raised",
                  )}
                >
                  <div className="flex items-center gap-2">
                    <span className="min-w-0 flex-1 truncate text-[12px] font-medium">
                      {item.name}
                    </span>
                    <span className="mono shrink-0 text-[10px] text-muted">
                      {targetLabel(item.kind)}
                    </span>
                    {item.state === "uploading" ? (
                      <span className="mono text-[10.5px] text-muted">{item.progress}%</span>
                    ) : (
                      <button
                        type="button"
                        className="grid h-6 w-6 place-items-center text-muted hover:text-ink"
                        aria-label={`Dismiss error for ${item.name}`}
                        onClick={() => dismissItem(item.key)}
                      >
                        <X size={13} aria-hidden="true" />
                      </button>
                    )}
                  </div>
                  {item.state === "uploading" ? (
                    <div className="mt-2 h-[3px] w-full overflow-hidden rounded-full bg-paper-deep">
                      <div
                        className="h-full bg-accent transition-[width] duration-200 ease-out"
                        style={{ width: `${Math.max(4, item.progress)}%` }}
                      />
                    </div>
                  ) : (
                    <p className="mt-1 text-[11.5px] leading-relaxed text-fail">{item.error}</p>
                  )}
                </li>
              ))}
            </ul>
          ) : null}

          {warnings.length > 0 ? (
            <div className="mt-3 rounded-[2px] border border-warn/35 bg-warn-wash px-3 py-2.5 text-[11.5px] leading-relaxed text-warn">
              <div className="flex items-start gap-2">
                <AlertTriangle size={13} className="mt-0.5 shrink-0" aria-hidden="true" />
                <div className="flex-1">
                  {warnings.map((warning) => (
                    <p key={warning}>{warning}</p>
                  ))}
                </div>
                <button
                  type="button"
                  className="text-warn/70 hover:text-warn"
                  aria-label="Dismiss upload warning"
                  onClick={() => setWarnings([])}
                >
                  <X size={13} aria-hidden="true" />
                </button>
              </div>
            </div>
          ) : null}
        </div>
      )}

      {/* Mark sheets ------------------------------------------------------ */}
      <div className="border-b border-line p-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="text-[13.5px] font-semibold">Mark sheets</h3>
          <p className="text-[11px] text-muted">
            Class 12 is required. Class 10 helps consistency checks. Class 11 is optional.
          </p>
        </div>

        <div className="mt-3 overflow-hidden rounded-[2px] border border-line bg-paper-deep/20">
          {MARK_SHEET_LEVELS.map((level, index) => {
            const kind = `marksheet_${level}` as DocumentKind;
            const files = documentsOf(kind);
            const optional = level === 11;
            return (
              <div
                key={level}
                className={clsx("p-4", index > 0 && "border-t border-line")}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0">
                    <h4 className="flex items-center gap-2 text-[13px] font-semibold">
                      <GraduationCap size={14} className="text-muted" aria-hidden="true" />
                      Class {level} mark sheet
                    </h4>
                    <p className="mt-0.5 text-[11px] text-muted">
                      {optional
                        ? files.length
                          ? "Optional record attached."
                          : "Optional. Leave empty if Class 11 was not provided."
                        : files.length
                          ? "Record attached."
                          : level === 12
                            ? "Required before the checks can run."
                            : "Recommended for the consistency checks."}
                    </p>
                  </div>
                  {readOnly ? (
                    <span className="text-[10.5px] text-muted">
                      {files.length
                        ? `${files.length} file${files.length === 1 ? "" : "s"}`
                        : optional
                          ? "Not provided"
                          : "Not attached"}
                    </span>
                  ) : (
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      disabled={uploading}
                      onClick={() => choose(kind as UploadKind)}
                    >
                      {files.length ? "Attach another" : "Attach"}
                    </Button>
                  )}
                </div>

                {files.length > 0 ? (
                  <ul className="mt-2.5 grid gap-2">
                    {files.map((document) => (
                      <FileRow
                        key={document.id}
                        document={document}
                        readOnly={readOnly}
                        onView={setViewing}
                        onRemove={removeDocument}
                      />
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-[11.5px] leading-relaxed text-muted">
                    {optional
                      ? "No Class 11 sheet attached."
                      : "No file attached. Use the automatic drop zone or attach the file here."}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Supporting documents --------------------------------------------- */}
      <div className="p-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="text-[13.5px] font-semibold">Supporting documents</h3>
          <p className="text-[11px] text-muted">Optional. Attach only what applies.</p>
        </div>

        <div className="mt-3 grid gap-x-6 gap-y-5 sm:grid-cols-2">
          {supportingDocuments.map((slot) => {
            const document = slot.documents[0] ?? null;
            const Icon = slot.icon;
            const note = document ? classificationNote(document) : null;
            return (
              <div key={slot.kind} className="min-w-0 border-t border-line pt-3">
                <div className="flex items-start gap-2.5">
                  <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-[2px] border border-line bg-paper text-muted">
                    <Icon size={15} aria-hidden="true" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                      <h4 className="text-[12.5px] font-semibold">{slot.title}</h4>
                      <span className="text-[10.5px] text-muted">
                        {document ? "Attached" : "Not attached"}
                      </span>
                    </div>
                    <p className="mt-0.5 text-[11px] leading-relaxed text-muted">{slot.hint}</p>
                  </div>
                </div>

                {document ? (
                  <div className="mt-2.5">
                    <button
                      type="button"
                      className="block w-full min-w-0 text-left"
                      onClick={() => setViewing(document)}
                    >
                      <span className="block truncate text-[12px] font-medium">
                        {document.original_filename}
                      </span>
                      <span className="mono mt-0.5 flex flex-wrap items-center gap-x-2 text-[10.5px] text-muted">
                        <span>{formatBytes(document.size_bytes)}</span>
                        {document.masked_aadhaar ? (
                          <>
                            <span className="text-line-strong" aria-hidden="true">
                              ·
                            </span>
                            <span className="text-ink-soft">{document.masked_aadhaar}</span>
                          </>
                        ) : document.kind === "aadhaar" ? (
                          <>
                            <span className="text-line-strong" aria-hidden="true">
                              ·
                            </span>
                            <span>Number hidden until the checks run</span>
                          </>
                        ) : null}
                        {document.duplicate_of_id ? (
                          <>
                            <span className="text-line-strong" aria-hidden="true">
                              ·
                            </span>
                            <span className="flex items-center gap-1 text-warn">
                              <AlertTriangle size={10} aria-hidden="true" />
                              Duplicate
                            </span>
                          </>
                        ) : null}
                      </span>
                      {note ? (
                        <span className="mt-1 block text-[10.5px] leading-relaxed text-muted">
                          {note}
                        </span>
                      ) : null}
                    </button>
                    <div className="mt-2 flex flex-wrap items-center gap-1.5">
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => setViewing(document)}
                      >
                        View
                      </button>
                      {readOnly ? null : (
                        <>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            disabled={uploading}
                            onClick={() => choose(slot.kind as UploadKind)}
                          >
                            Replace
                          </button>
                          <RemoveDocument document={document} onRemove={removeDocument} />
                        </>
                      )}
                    </div>
                  </div>
                ) : readOnly ? (
                  <p className="mt-2 text-[11.5px] text-muted">No file was attached.</p>
                ) : (
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm mt-2.5"
                    disabled={uploading}
                    onClick={() => choose(slot.kind as UploadKind)}
                  >
                    Attach
                  </button>
                )}
              </div>
            );
          })}

          {/* Photo -------------------------------------------------------- */}
          <div className="min-w-0 border-t border-line pt-3 sm:col-span-2">
            <div className="grid gap-4 sm:grid-cols-[112px_minmax(0,1fr)]">
              <PhotoFrame
                document={photo}
                empty={
                  <span className="grid justify-items-center gap-2 px-3 text-center">
                    <Camera size={17} className="text-muted" aria-hidden="true" />
                    <span className="text-[10.5px] leading-relaxed text-muted">
                      No photograph
                    </span>
                  </span>
                }
              />
              <div className="min-w-0">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                  <h4 className="flex items-center gap-2 text-[12.5px] font-semibold">
                    <Camera size={14} className="text-muted" aria-hidden="true" />
                    Profile photograph
                  </h4>
                  <span className="text-[10.5px] text-muted">
                    {photo ? "Required record attached" : "Required"}
                  </span>
                </div>
                <p className="mt-0.5 max-w-[52ch] text-[11px] leading-relaxed text-muted">
                  Plain background, face forward. Resolution, lighting, sharpness and one frontal
                  face are checked. Minimum {config.data?.photo.min_width ?? 300} ×{" "}
                  {config.data?.photo.min_height ?? 400} px.
                </p>

                {photo ? (
                  <div className="mt-2">
                    <p className="truncate text-[12px] font-medium">{photo.original_filename}</p>
                    <p className="mono mt-0.5 text-[10.5px] text-muted">
                      {photo.width && photo.height ? `${photo.width} × ${photo.height} px · ` : ""}
                      {formatBytes(photo.size_bytes)}
                    </p>
                    {classificationNote(photo) ? (
                      <p className="mt-1 text-[10.5px] text-muted">{classificationNote(photo)}</p>
                    ) : null}
                    <div className="mt-2 flex flex-wrap items-center gap-1.5">
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => setViewing(photo)}
                      >
                        View
                      </button>
                      {readOnly ? null : (
                        <>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            disabled={uploading}
                            onClick={() => choose("photo")}
                          >
                            Replace
                          </button>
                          <RemoveDocument document={photo} onRemove={removeDocument} />
                        </>
                      )}
                    </div>
                  </div>
                ) : readOnly ? (
                  <p className="mt-2 text-[11.5px] text-muted">No photograph was attached.</p>
                ) : (
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm mt-2.5"
                    disabled={uploading}
                    onClick={() => choose("photo")}
                  >
                    Attach photograph
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>

        {!readOnly ? (
          <p className="mt-4 flex items-center gap-1.5 text-[11px] text-muted">
            <Lock size={11} aria-hidden="true" />
            Files are encrypted before they reach disk.
          </p>
        ) : null}
      </div>

      {viewing ? <DocumentViewer file={viewing} onClose={() => setViewing(null)} /> : null}
    </section>
  );
}
