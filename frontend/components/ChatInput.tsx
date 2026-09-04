"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown, ImagePlus, Loader2, Mic, MicOff, Paperclip, Send, ShieldCheck, Upload, X } from "lucide-react";
import { addPending, deletePending, getPending, type PendingSubmission } from "@/lib/offline-db";
import { useSpeechDictation } from "@/hooks/useSpeechDictation";
import { compressImage } from "@/lib/image-compress";
import PendingQueueBanner from "@/components/PendingQueueBanner";
import { useOfflineQueue, notifyQueueMutated } from "@/hooks/useOfflineQueue";
import { COMPLIANCE_PROFILES, type ComplianceProfile } from "@/lib/types";

export interface ChatSubmission {
  notes: string;
  site: string;
  client: string;
  files: File[];
  complianceProfile: "general" | "dpwh" | "dole" | "philgeps";
}

interface ChatInputProps {
  pending: boolean;
  onSubmit: (submission: ChatSubmission) => Promise<boolean>;
}

const ACCEPTED_MEDIA = "image/jpeg,image/png,image/webp,image/bmp,image/tiff,video/mp4,video/quicktime,video/x-msvideo,video/webm,video/mpeg";

// ---------------------------------------------------------------------------
// ChatInput
// ---------------------------------------------------------------------------

export default function ChatInput({ pending, onSubmit }: ChatInputProps) {
  const [notes, setNotes] = useState("");
  const [site, setSite] = useState("");
  const [client, setClient] = useState("");
  const [showContext, setShowContext] = useState(false);
  const [media, setMedia] = useState<{ file: File; url: string; compressing?: boolean }[]>([]);
  /** Number of photos currently being compressed (used for UX feedback). */
  const [compressingCount, setCompressingCount] = useState(0);
  /** Phase 3: compliance profile for SOW generation */
  const [complianceProfile, setComplianceProfile] = useState<ComplianceProfile>("general");
  /** Phase 3: SOP / knowledge-base files to attach to the generation request */
  const [sopFiles, setSopFiles] = useState<{ file: File; uploading: boolean; error?: string }[]>([]);
  const sopFileInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const isSubmittingRef = useRef(false);

  // Single shared queue instance: both ChatInput (addPending) and
  // PendingQueueBanner (display) read from the same hook so mutations
  // in ChatInput propagate to the banner automatically.
  const queue = useOfflineQueue();

  // Auto-drain the IndexedDB queue when the browser reports it's back online.
  useEffect(() => {
    function handleOnline() {
      void (async () => {
        const items = await getPending();
        for (const item of items) {
          const files: File[] = [];
          for (const mf of item.mediaFiles) {
            try {
              const resp = await fetch(mf.blobUrl);
              if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
              files.push(new File([await resp.blob()], mf.name, { type: mf.type }));
            } catch { /* blob expired */ }
          }
          const ok = await onSubmit({ notes: item.notes, site: item.site, client: item.client, complianceProfile: "general", files });
          if (ok && item.id !== undefined) await deletePending(item.id);
        }
        await queue.reload();
      })();
    }
    window.addEventListener("online", handleOnline);
    return () => window.removeEventListener("online", handleOnline);
  }, [onSubmit, queue]);

  // Web Speech API dictation (Chrome / Edge). Hidden if unsupported.
  const { isSupported: speechSupported, isListening, transcript, start: startDict, stop: stopDict } = useSpeechDictation();
  useEffect(() => { if (transcript) setNotes((p) => (p ? p + " " + transcript : transcript)); }, [transcript]);

  /**
   * Add files from the <input type="file">.
   * Image files are compressed client-side before being added to the media list,
   * so large field photos don't eat bandwidth on cellular uploads.
   * Non-image files (video, PDF, etc.) are added immediately without compression.
   */
  const addFiles = useCallback((fileList: FileList | null) => {
    if (!fileList) return;
    const incoming = Array.from(fileList).slice(0, 12 - media.length);
    if (incoming.length === 0) return;

    // Separate images (compressible) from other types.
    const images: File[] = [];
    const nonImages: File[] = [];
    for (const f of incoming) {
      if (f.type.startsWith("image/")) images.push(f);
      else nonImages.push(f);
    }

    // Non-images: add immediately.
    if (nonImages.length > 0) {
      setMedia((current) => [
        ...current,
        ...nonImages.map((file) => ({ file, url: URL.createObjectURL(file) })),
      ]);
    }

    // Images: add with a compressing marker, then compress in background.
    if (images.length > 0) {
      const slots = images.map((file) => ({ file, url: "", compressing: true }));
      setMedia((current) => [...current, ...slots]);
      void (async () => {
        for (let i = 0; i < images.length; i++) {
          try {
            const compressed = await compressImage(images[i]);
            const newUrl = URL.createObjectURL(compressed);
            setMedia((current) => {
              const idx = current.findLastIndex(
                (m) => m.file.name === images[i].name && m.compressing,
              );
              if (idx === -1) return current;
              const updated = [...current];
              if (updated[idx].url) URL.revokeObjectURL(updated[idx].url);
              updated[idx] = { file: compressed, url: newUrl, compressing: false };
              return updated;
            });
          } catch {
            // Compression failed — keep the original file without compression.
            setMedia((current) => {
              const idx = current.findLastIndex(
                (m) => m.file.name === images[i].name && m.compressing,
              );
              if (idx === -1) return current;
              const updated = [...current];
              updated[idx] = { file: images[i], url: URL.createObjectURL(images[i]), compressing: false };
              return updated;
            });
          }
        }
      })();
    }

    if (fileInputRef.current) fileInputRef.current.value = "";
  }, [media.length]);

  const removeFile = useCallback((index: number) => {
    setMedia((current) => {
      const target = current[index];
      if (target) URL.revokeObjectURL(target.url);
      return current.filter((_, fileIndex) => fileIndex !== index);
    });
  }, []);

  const clearAll = useCallback(() => {
    setNotes("");
    setSite("");
    setClient("");
    setMedia((current) => {
      current.forEach((item) => URL.revokeObjectURL(item.url));
      return [];
    });
  }, []);

  const canSubmit = !pending && (notes.trim().length > 0 || media.length > 0);

  /**
   * Returns true when the browser is offline or when the e2e test has set
   * window.__FORCE_OFFLINE__ to true. This allows Playwright to trigger the
   * offline queue path without needing to mock navigator.onLine, which
   * Chromium reads directly from the browser engine and cannot be overridden.
   */
  function isOffline() {
    const flag = (globalThis as { __FORCE_OFFLINE__?: boolean }).__FORCE_OFFLINE__;
    const onLine = (navigator as { onLine?: boolean }).onLine;
    const result = !onLine || flag === true;
    (globalThis as { __IS_OFFLINE__?: boolean }).__IS_OFFLINE__ = result;
    return result;
  }

  const handleSubmit = async () => {
    if (!canSubmit) return;
    if (isSubmittingRef.current) return;
    isSubmittingRef.current = true;
    const submission: ChatSubmission = { notes, site, client, complianceProfile, files: media.map((m) => m.file) };
    try {
      // Queue and clear form if the browser is offline (or e2e forces offline).
      if (isOffline()) {
        const mediaFiles = await Promise.all(
          submission.files.map(async (f) => ({ name: f.name, type: f.type, size: f.size, blobUrl: URL.createObjectURL(f) })),
        );
        await addPending({
          created_at: new Date().toISOString(),
          status: "pending",
          attempts: 0,
          notes: submission.notes,
          site: submission.site,
          client: submission.client,
          mediaFiles,
        });
        // Dispatch a custom event so every useOfflineQueue() instance (including
        // PendingQueueBanner's) re-reads IndexedDB and shows the updated queue.
        notifyQueueMutated();
        clearAll();
        isSubmittingRef.current = false;
        return;
      }
      const succeeded = await onSubmit(submission);
      if (succeeded) clearAll();
    } catch {
      /* Preserve the draft on unexpected failures. */
    } finally {
      isSubmittingRef.current = false;
    }
  };

  /** Retry a single queued submission. */
  async function handleRetry(item: PendingSubmission) {
    const files: File[] = [];
    for (const mf of item.mediaFiles) {
      try {
        const resp = await fetch(mf.blobUrl);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        files.push(new File([await resp.blob()], mf.name, { type: mf.type }));
      } catch { /* blob expired */ }
    }
    return await onSubmit({ notes: item.notes, site: item.site, client: item.client, complianceProfile: "general", files });
  }

  return (
    <div className="relative">
      <div className="card p-3 space-y-3 shadow-sm">
        {media.length > 0 && (
          <div className="flex flex-wrap gap-2 border-b border-slate-100 pb-3">
            {media.map(({ file, url, compressing }, index) => (
              <div key={`${file.name}-${file.size}-${index}`} className="group relative">
                {file.type.startsWith("image/") ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={url}
                    alt={file.name}
                    className={`h-16 w-16 rounded-md border border-slate-200 object-cover ${compressing ? "opacity-40" : ""}`}
                  />
                ) : (
                  <video
                    src={url}
                    muted
                    playsInline
                    className="h-16 w-16 rounded-md border border-slate-200 object-cover bg-slate-100"
                  />
                )}
                {/* Compression in-progress indicator */}
                {compressing && (
                  <span className="absolute inset-0 flex items-center justify-center">
                    <Loader2 size={16} className="animate-spin text-slate-400" />
                  </span>
                )}
                <span className="absolute -bottom-px left-0 right-0 truncate rounded-b-md bg-slate-900/70 px-1 py-0.5 text-[9px] text-white">
                  {file.name}
                </span>
                <button
                  type="button"
                  onClick={() => removeFile(index)}
                  aria-label={`Remove ${file.name}`}
                  className="absolute -right-1.5 -top-1.5 grid h-4 w-4 place-items-center rounded-full bg-red-500 text-white shadow transition hover:bg-red-400"
                >
                  <X size={10} />
                </button>
              </div>
            ))}
          </div>
        )}
        {/* Engineer notes input */}
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && canSubmit) {
                e.preventDefault();
                void handleSubmit();
              }
            }}
            rows={2}
            placeholder="Engineer field notes — describe the site, assets, symptoms, and any constraints… (Shift+Enter for new line)"
            className="min-h-[88px] w-full flex-1 resize-none border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-600 focus:ring-2 focus:ring-blue-100 rounded-md sm:min-h-[72px]"
          />
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_MEDIA}
            multiple
            className="hidden"
            onChange={(event) => addFiles(event.target.files)}
          />
          <div className="flex w-full gap-2 sm:w-auto">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="btn-ghost flex-1 justify-center sm:flex-none"
              title="Attach site photos or video"
            >
              <ImagePlus size={16} />
              <span>Media</span>
              {media.some((m) => m.compressing) && (
                <span className="ml-1 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-amber-400 px-1 text-[9px] font-bold text-amber-900">
                  {media.filter((m) => m.compressing).length}
                </span>
              )}
            </button>
            {/* Dictation — only shown when browser supports SpeechRecognition */}
            {speechSupported && (
              <button
                type="button"
                onClick={isListening ? stopDict : startDict}
                disabled={pending}
                className={`btn-ghost justify-center sm:flex-none ${isListening ? "text-red-500 border-red-200 bg-red-50" : ""}`}
                title={isListening ? "Stop dictation" : "Voice dictation"}
              >
                {isListening ? (
                  <>
                    <span className="relative flex h-3 w-3" aria-hidden="true">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
                      <span className="relative inline-flex h-3 w-3 rounded-full bg-red-500" />
                    </span>
                    <span className="text-red-600">Dictating…</span>
                  </>
                ) : (
                  <>
                    <Mic size={16} />
                    <span>Dictate</span>
                  </>
                )}
              </button>
            )}
            <button
              type="button"
              onClick={handleSubmit}
              disabled={!canSubmit}
              className="btn-primary flex-[1.35] justify-center sm:flex-none"
            >
              {pending ? (
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-950/30 border-t-slate-950" />
              ) : (
                <Send size={16} />
              )}
              <span>{pending ? "Analyzing…" : "Generate SOW"}</span>
            </button>
          </div>
        </div>

        {/* Optional engagement context (site / client) */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1 text-xs text-slate-500">
            <Paperclip size={13} /> Photos and video are analyzed for visual evidence.
          </span>
          <button
            type="button"
            onClick={() => setShowContext((v) => !v)}
            className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-900 transition"
          >
            <ChevronDown size={14} className={showContext ? "rotate-180 transition" : "transition"} />
            Engagement context
          </button>
          {showContext && (
            <>
              <input
                value={site}
                onChange={(e) => setSite(e.target.value)}
                placeholder="Site / facility (e.g. Plant 2 – Boiler Room)"
                className="input-chip w-64"
              />
              <input
                value={client}
                onChange={(e) => setClient(e.target.value)}
                placeholder="Client name"
                className="input-chip w-48"
              />
              <span className="inline-flex items-center gap-1 text-xs text-slate-500">
                <ShieldCheck size={13} /> Compliance
              </span>
              <select
                value={complianceProfile}
                onChange={(e) => setComplianceProfile(e.target.value as ComplianceProfile)}
                title={COMPLIANCE_PROFILES[complianceProfile].description}
                className="input-chip w-56"
                aria-label="Compliance profile"
              >
                {(Object.keys(COMPLIANCE_PROFILES) as ComplianceProfile[]).map((p) => (
                  <option key={p} value={p}>
                    {COMPLIANCE_PROFILES[p].label}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => sopFileInputRef.current?.click()}
                className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 transition"
                title="Attach SOP / knowledge-base reference documents (PDF or TXT, up to 8 MB each)"
              >
                <Upload size={12} /> SOP / KB
              </button>
              <input
                ref={sopFileInputRef}
                type="file"
                multiple
                accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown"
                className="hidden"
                onChange={(e) => {
                  const list = e.target.files;
                  if (list) {
                    const added = Array.from(list).map((f) => ({ file: f, uploading: true }));
                    setSopFiles((prev) => [...prev, ...added]);
                    void Promise.all(
                      added.map(async (entry) => {
                        try {
                          const fd = new FormData();
                          fd.append("file", entry.file);
                          const res = await fetch("/api/sop/upload", { method: "POST", body: fd });
                          if (!res.ok) throw new Error(`HTTP ${res.status}`);
                          const data = (await res.json()) as { ok: boolean; source: string; chunks_added: number };
                          setSopFiles((prev) =>
                            prev.map((s) =>
                              s.file === entry.file
                                ? { file: s.file, uploading: false, error: undefined }
                                : s,
                            ),
                          );
                          // Stash the source id for the generate call
                          (entry.file as File & { __sopSource?: string }).__sopSource = data.source;
                        } catch (err) {
                          setSopFiles((prev) =>
                            prev.map((s) =>
                              s.file === entry.file
                                ? {
                                    file: s.file,
                                    uploading: false,
                                    error: err instanceof Error ? err.message : "Upload failed",
                                  }
                                : s,
                            ),
                          );
                        }
                      }),
                    );
                  }
                  e.target.value = "";
                }}
              />
              {sopFiles.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {sopFiles.map((s, i) => (
                    <span
                      key={i}
                      className={
                        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium " +
                        (s.error
                          ? "bg-red-50 text-red-700 border border-red-200"
                          : s.uploading
                          ? "bg-amber-50 text-amber-700 border border-amber-200"
                          : "bg-emerald-50 text-emerald-700 border border-emerald-200")
                      }
                      title={s.error ?? `Indexed: ${(s.file as File & { __sopSource?: string }).__sopSource ?? s.file.name}`}
                    >
                      {s.error ? "✗" : s.uploading ? "⏳" : "✓"} {s.file.name}
                      <button
                        type="button"
                        onClick={() => setSopFiles((prev) => prev.filter((_, idx) => idx !== i))}
                        className="ml-0.5 opacity-60 hover:opacity-100"
                        aria-label={`Remove ${s.file.name}`}
                      >
                        <X size={10} />
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
      <PendingQueueBanner onRetry={handleRetry} />
    </div>
  );
}

