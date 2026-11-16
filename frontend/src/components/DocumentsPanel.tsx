import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Download,
  FileText,
  ImageOff,
  Loader2,
  Lock,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { clsx } from "clsx";
import { api, documentBlob, uploadDocument, ApiError } from "../lib/api";
import type { DocumentRecord } from "../lib/api";
import { formatBytes } from "../lib/query";

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
              {file.mime_type} · {formatBytes(file.size_bytes)}
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
   Thumbnails
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

/* ---------------------------------------------------------------------------
   Upload helpers
--------------------------------------------------------------------------- */

interface QueueItem {
  key: string;
  name: string;
  kind: "marksheet" | "photo";
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

function fileProblem(file: File, kind: "marksheet" | "photo", maxMb: number): string | null {
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

/* ---------------------------------------------------------------------------
   Panel
--------------------------------------------------------------------------- */

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

  const markSheets = documents.filter((document) => document.kind === "marksheet");
  const photo = documents.find((document) => document.kind === "photo") ?? null;

  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [viewing, setViewing] = useState<DocumentRecord | null>(null);
  const [confirming, setConfirming] = useState<number | null>(null);
  const [removing, setRemoving] = useState<number | null>(null);
  const [removeError, setRemoveError] = useState<string | null>(null);

  const fileInput = useRef<HTMLInputElement>(null);
  const photoInput = useRef<HTMLInputElement>(null);
  const uploading = queue.some((item) => item.state === "uploading");

  function updateItem(key: string, patch: Partial<QueueItem>) {
    setQueue((current) => current.map((item) => (item.key === key ? { ...item, ...patch } : item)));
  }

  function dismissItem(key: string) {
    setQueue((current) => current.filter((item) => item.key !== key));
  }

  async function startUploads(files: File[], kind: "marksheet" | "photo") {
    if (readOnly || files.length === 0) return;
    setRemoveError(null);
    setWarnings([]);

    const accepted: File[] = [];
    const rejected: QueueItem[] = [];

    for (const file of files) {
      if (kind === "photo" && accepted.length === 1) break;
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
    setRemoving(documentId);
    setRemoveError(null);
    try {
      await api.deleteDocument(documentId);
      setConfirming(null);
      await queryClient.invalidateQueries({ queryKey: ["application", String(applicationId)] });
      await queryClient.invalidateQueries({ queryKey: ["application", applicationId] });
      await queryClient.invalidateQueries({ queryKey: ["applications"] });
    } catch (caught) {
      setRemoveError(caught instanceof ApiError ? caught.detail : "The file could not be removed.");
    } finally {
      setRemoving(null);
    }
  }

  const sheetZone = useDropZone((files) => void startUploads(files, "marksheet"), !readOnly && !uploading);
  const photoZone = useDropZone((files) => void startUploads(files, "photo"), !readOnly && !uploading);

  function openSheetDialog() {
    fileInput.current?.click();
  }

  return (
    <section className="card">
      <div className="card-head">
        <h2 className="section-title">Documents</h2>
        <span className="flex items-center gap-1.5 text-[11px] text-muted">
          <Lock size={12} aria-hidden="true" />
          Encrypted at rest
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_288px]">
        {/* Mark sheets ------------------------------------------------------ */}
        <div className="min-w-0 border-b border-line p-5 lg:border-b-0 lg:border-r">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-[13.5px] font-semibold">Mark sheets</h3>
            <span className="mono text-[10.5px] text-muted">
              {markSheets.length} file{markSheets.length === 1 ? "" : "s"}
            </span>
          </div>

          {markSheets.length === 0 ? (
            <p className="mt-2 max-w-[46ch] text-[12px] leading-relaxed text-muted">
              Attach the statement of marks issued to you. One PDF can hold several pages; you can
              attach more than one sheet.
            </p>
          ) : (
            <ul className="mt-3 grid gap-2">
              {markSheets.map((document) => (
                <li
                  key={document.id}
                  className="group flex items-center gap-3 rounded-[2px] border border-line bg-raised px-3 py-2.5"
                >
                  <FileGlyph document={document} />
                  <button
                    type="button"
                    className="min-w-0 flex-1 text-left"
                    onClick={() => setViewing(document)}
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
                  </button>

                  <div className="flex shrink-0 items-center gap-0.5">
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => setViewing(document)}
                    >
                      View
                    </button>
                    {readOnly ? null : confirming === document.id ? (
                      <span className="flex items-center gap-1">
                        <button
                          type="button"
                          className="btn btn-sm border border-fail/40 px-2 text-fail hover:bg-fail hover:text-white"
                          disabled={removing === document.id}
                          onClick={() => void removeDocument(document.id)}
                        >
                          {removing === document.id ? "Removing" : "Remove"}
                        </button>
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm px-2"
                          onClick={() => setConfirming(null)}
                        >
                          Keep
                        </button>
                      </span>
                    ) : (
                      <button
                        type="button"
                        className="btn btn-ghost h-8 w-8 p-0 text-muted hover:text-fail"
                        aria-label={`Remove ${document.original_filename}`}
                        onClick={() => setConfirming(document.id)}
                      >
                        <Trash2 size={14} aria-hidden="true" />
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}

          {readOnly ? (
            <p className="mt-4 flex items-center gap-1.5 text-[11.5px] text-muted">
              <Lock size={11} aria-hidden="true" />
              Read-only. Documents are uploaded by the applicant.
            </p>
          ) : (
            <div className="mt-4">
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
                  void startUploads(files, "marksheet");
                }}
              />
              <div
                {...sheetZone.handlers}
                className={clsx(
                  "rounded-[2px] border border-dashed px-4 py-5 text-center transition-colors duration-150",
                  sheetZone.active
                    ? "border-accent bg-accent-wash/60"
                    : "border-line-strong bg-paper-deep/25",
                )}
              >
                <Upload
                  size={17}
                  className={clsx("mx-auto", sheetZone.active ? "text-accent" : "text-muted")}
                  aria-hidden="true"
                />
                <p className="mt-2 text-[12.5px] font-medium">
                  {sheetZone.active ? "Release to attach" : "Drop mark sheets here"}
                </p>
                <p className="mt-0.5 text-[11px] text-muted">
                  PDF, JPG or PNG · up to {maxMb} MB each
                </p>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm mt-3"
                  onClick={openSheetDialog}
                  disabled={uploading}
                >
                  Choose files
                </button>
                <p className="mt-2 text-[10.5px] text-faint">
                  The file&rsquo;s content is checked, not just its extension.
                </p>
              </div>
            </div>
          )}

          {queue.length > 0 ? (
            <ul className="mt-4 grid gap-2" aria-live="polite">
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
                  aria-label="Dismiss duplicate warning"
                  onClick={() => setWarnings([])}
                >
                  <X size={13} aria-hidden="true" />
                </button>
              </div>
            </div>
          ) : null}

          {removeError ? (
            <p className="mt-2 text-[11.5px] text-fail" role="alert">
              {removeError}
            </p>
          ) : null}
        </div>

        {/* Photo ------------------------------------------------------------ */}
        <div className="p-5">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-[13.5px] font-semibold">Profile photo</h3>
            <span className="text-[10.5px] text-muted">{photo ? "1 file" : "Required"}</span>
          </div>

          {readOnly ? (
            <div className="mt-3">
              <PhotoFrame
                document={photo}
                empty={
                  <span className="px-4 text-center text-[11.5px] text-muted">
                    No photo was attached.
                  </span>
                }
              />
              {photo ? (
                <button
                  type="button"
                  className="btn btn-secondary btn-sm mt-3 w-full"
                  onClick={() => setViewing(photo)}
                >
                  View photo
                </button>
              ) : null}
            </div>
          ) : (
            <div className="mt-3">
              <input
                ref={photoInput}
                type="file"
                accept=".jpg,.jpeg,.png,image/jpeg,image/png"
                className="sr-only"
                tabIndex={-1}
                onChange={(event) => {
                  const files = Array.from(event.target.files ?? []);
                  event.target.value = "";
                  void startUploads(files, "photo");
                }}
              />
              <div {...photoZone.handlers}>
                <button
                  type="button"
                  className="block w-full text-left"
                  onClick={() => photoInput.current?.click()}
                  aria-label={photo ? "Replace profile photo" : "Choose profile photo"}
                  disabled={uploading}
                >
                  <PhotoFrame
                    document={photo}
                    active={photoZone.active}
                    empty={
                      <span className="grid justify-items-center gap-2 px-4 text-center">
                        <Upload
                          size={17}
                          className={photoZone.active ? "text-accent" : "text-muted"}
                          aria-hidden="true"
                        />
                        <span className="text-[11.5px] font-medium">
                          {photoZone.active ? "Release to attach" : "Drop a portrait here"}
                        </span>
                        <span className="text-[10.5px] leading-relaxed text-muted">
                          JPEG or PNG, passport style
                        </span>
                      </span>
                    }
                  />
                </button>
              </div>

              {photo ? (
                <>
                  <div className="mt-3 min-w-0">
                    <p className="truncate text-[12px] font-medium">{photo.original_filename}</p>
                    <p className="mono mt-0.5 text-[10.5px] text-muted">
                      {photo.width && photo.height ? `${photo.width} × ${photo.height} px · ` : ""}
                      {formatBytes(photo.size_bytes)}
                    </p>
                  </div>
                  <div className="mt-2.5 flex items-center gap-1.5">
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm flex-1"
                      onClick={() => setViewing(photo)}
                    >
                      View
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm flex-1"
                      onClick={() => photoInput.current?.click()}
                      disabled={uploading}
                    >
                      Replace
                    </button>
                  </div>
                  <button
                    type="button"
                    className="mt-2 text-[11px] text-muted underline decoration-line-strong underline-offset-4 hover:text-fail hover:decoration-fail"
                    onClick={() => {
                      setConfirming(photo.id);
                      setRemoveError(null);
                    }}
                  >
                    Remove photo
                  </button>
                  {confirming === photo.id ? (
                    <div className="mt-2 rounded-[2px] border border-fail/25 bg-fail-wash/60 p-2.5">
                      <p className="text-[11px] leading-relaxed text-ink-soft">
                        Remove the photo? Checks cannot run until another is attached.
                      </p>
                      <div className="mt-2 flex gap-1.5">
                        <button
                          type="button"
                          className="btn btn-sm border border-fail/40 text-fail hover:bg-fail hover:text-white"
                          disabled={removing === photo.id}
                          onClick={() => void removeDocument(photo.id)}
                        >
                          {removing === photo.id ? "Removing" : "Remove"}
                        </button>
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm"
                          onClick={() => setConfirming(null)}
                        >
                          Keep
                        </button>
                      </div>
                    </div>
                  ) : null}
                  {removeError ? (
                    <p className="mt-2 text-[11px] text-fail" role="alert">
                      {removeError}
                    </p>
                  ) : null}
                </>
              ) : (
                <p className="mt-2.5 text-[10.5px] leading-relaxed text-muted">
                  Plain background, face forward. Minimum {config.data?.photo.min_width ?? 300} ×{" "}
                  {config.data?.photo.min_height ?? 400} px.
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      {viewing ? <DocumentViewer file={viewing} onClose={() => setViewing(null)} /> : null}
    </section>
  );
}
