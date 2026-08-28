"use client";

import { useCallback, useRef, useState } from "react";
import { ChevronDown, ImagePlus, Paperclip, Send, X } from "lucide-react";

export interface ChatSubmission {
  notes: string;
  site: string;
  client: string;
  files: File[];
}

interface ChatInputProps {
  pending: boolean;
  onSubmit: (submission: ChatSubmission) => Promise<boolean>;
}

const ACCEPTED_MEDIA = "image/jpeg,image/png,image/webp,image/bmp,image/tiff,video/mp4,video/quicktime,video/x-msvideo,video/webm,video/mpeg";

export default function ChatInput({ pending, onSubmit }: ChatInputProps) {
  const [notes, setNotes] = useState("");
  const [site, setSite] = useState("");
  const [client, setClient] = useState("");
  const [showContext, setShowContext] = useState(false);
  const [media, setMedia] = useState<{ file: File; url: string }[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const isSubmittingRef = useRef(false);

  const addFiles = useCallback((fileList: FileList | null) => {
    if (!fileList) return;
    const incoming = Array.from(fileList).slice(0, 12 - media.length);
    setMedia((current) => [
      ...current,
      ...incoming.map((file) => ({ file, url: URL.createObjectURL(file) })),
    ]);
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

  const handleSubmit = async () => {
    if (!canSubmit) return;
    if (isSubmittingRef.current) return;          // drop concurrent invocations (Enter + button race)
    isSubmittingRef.current = true;
    const submission: ChatSubmission = { notes, site, client, files: media.map((m) => m.file) };
    try {
      const succeeded = await onSubmit(submission);
      if (succeeded) clearAll();
    } catch {
      /* Preserve the draft if an unexpected client-side failure occurs. */
    } finally {
      isSubmittingRef.current = false;
    }
  };

  return (
    <div className="relative">
      <div className="card p-3 space-y-3 shadow-sm">
        {media.length > 0 && (
          <div className="flex flex-wrap gap-2 border-b border-slate-100 pb-3">
            {media.map(({ file, url }, index) => (
              <div key={`${file.name}-${file.size}-${index}`} className="group relative">
                {file.type.startsWith("image/") ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={url}
                    alt={file.name}
                    className="h-16 w-16 rounded-md border border-slate-200 object-cover"
                  />
                ) : (
                  <video
                    src={url}
                    muted
                    playsInline
                    className="h-16 w-16 rounded-md border border-slate-200 object-cover bg-slate-100"
                  />
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
            </button>
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
            </>
          )}
        </div>
      </div>
    </div>
  );
}

