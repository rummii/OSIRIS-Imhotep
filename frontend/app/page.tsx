"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertTriangle, FileText, HardHat, LogOut, ShieldCheck, Sparkles, UserRound } from "lucide-react";
import ChatInput, { type ChatSubmission } from "@/components/ChatInput";
import LoadingIndicator from "@/components/LoadingIndicator";
import SowReport from "@/components/SowReport";
import { generateSow, saveFromGeneration } from "@/lib/api";
import type { GenerateResponse } from "@/lib/types";
import { clearAuth, getCachedUser, isAuthenticated, type SessionUser } from "@/lib/auth";

type Message =
  | {
      role: "user";
      notes: string;
      site: string;
      client: string;
      media: { name: string; kind: string }[];
    }
  | { role: "assistant"; result: GenerateResponse; docId: number | undefined }
  | { role: "error"; message: string };

export default function Home() {
  const router = useRouter();
  const [authed, setAuthed] = useState(false);
  const [user, setUser] = useState<SessionUser | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [pending, setPending] = useState(false);
  const [pendingMediaCount, setPendingMediaCount] = useState(0);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace("/login");
    } else {
      setAuthed(true);
      setUser(getCachedUser());
    }
  }, [router]);

  const logout = () => {
    clearAuth();
    router.replace("/login");
  };

  const handleSubmit = useCallback(async (submission: ChatSubmission) => {
    const userMessage: Message = {
      role: "user",
      notes: submission.notes,
      site: submission.site,
      client: submission.client,
      media: submission.files.map((f) => ({
        name: f.name,
        kind: f.type.startsWith("video/") ? "video" : "image",
      })),
    };
    setMessages((prev) => [...prev, userMessage]);
    setPending(true);
    setPendingMediaCount(submission.files.length);

    try {
      const result = await generateSow(submission);
      // Auto-save so the SOW appears in the Documents list and can be re-exported.
      let docId: number | undefined;
      try {
        const saved = await saveFromGeneration(result.sow);
        docId = saved.id;
      } catch (saveErr) {
        console.warn("Auto-save failed:", saveErr);
      }
      setMessages((prev) => [...prev, { role: "assistant", result, docId }]);
      return true;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setMessages((prev) => [...prev, { role: "error", message }]);
      return false;
    } finally {
      setPending(false);
      setPendingMediaCount(0);
      requestAnimationFrame(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
      });
    }
  }, []);

  if (!authed) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white">
        <p className="text-sm text-slate-400">Checking session…</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-white">
      {/* Top bar */}
      <header className="border-b border-slate-200 bg-white px-4 py-3 sm:px-6">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-md bg-slate-900">
            <HardHat size={18} className="text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-slate-950">
              OSIRIS <span className="text-blue-700">Imhotep</span>
            </h1>
            <p className="text-[11px] text-slate-500">Engineering Scope of Work Generator</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5 sm:gap-2 text-[11px]">
          <span className="hidden md:inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-slate-500">
            @{user?.username}
          </span>
          {user?.role === "superadmin" && (
            <Link
              href="/admin"
              className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-slate-500 hover:border-violet-300 hover:text-violet-700 transition"
            >
              <ShieldCheck size={12} />
              Admin
            </Link>
          )}
          <Link
            href="/documents"
            className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-slate-500 hover:border-emerald-300 hover:text-emerald-700 transition"
          >
            <FileText size={12} />
            Documents
          </Link>
          <Link
            href="/account"
            className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-slate-500 hover:border-blue-300 hover:text-blue-700 transition"
          >
            <UserRound size={12} />
            Account
          </Link>
          <button
            type="button"
            onClick={logout}
            className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-slate-500 hover:border-red-300 hover:text-red-600 transition"
          >
            <LogOut size={12} />
            Sign out
          </button>
        </div>
        </div>
      </header>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-6xl px-4 py-7 sm:px-6 space-y-5">
          {messages.length === 0 && <EmptyState />}

          {messages.map((message, index) => (
            <div key={index} className="space-y-4">
              {message.role === "user" && <UserBubble message={message} />}
              {message.role === "error" && <ErrorBubble message={message.message} />}
              {message.role === "assistant" && (
                <SowReport
                  sow={message.result.sow}
                  model={message.result.model}
                  grounding={message.result.grounding}
                  groundingSources={message.result.grounding_sources}
                  docId={message.docId}
                />
              )}
            </div>
          ))}

          {pending && <LoadingIndicator mediaCount={pendingMediaCount} />}
        </div>
      </div>

      {/* Input */}
      <div className="sticky bottom-0 border-t border-slate-200 bg-white/95 p-4 backdrop-blur">
        <div className="mx-auto max-w-6xl">
          <ChatInput pending={pending} onSubmit={handleSubmit} />
        </div>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="mx-auto mt-6 max-w-3xl animate-fade-up">
      <div className="border-b border-slate-200 pb-8 text-center">
        <div className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-md bg-blue-50 text-blue-700">
          <Sparkles size={21} />
      </div>
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-700">Engineering workspace</p>
      <h2 className="mt-2 text-2xl font-semibold text-slate-950">Turn field notes into a clear scope of work.</h2>
      <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-slate-500">
        Add engineer field notes and optional site photos or short video clips. OSIRIS extracts visual
        evidence, to produce a structured SOW you can export to Google Docs.
      </p>
      </div>
      <div className="mt-7 grid grid-cols-1 gap-px overflow-hidden border border-slate-200 bg-slate-200 sm:grid-cols-3">
        {[
          ["Evidence", "Combine field notes with photos or video clips."],
          ["Scope", "Structure recommendations, phases, and costs."],
          ["Review", "Verify all findings before issuing the draft."],
        ].map(([icon, title, sub]) => (
          <div key={title} className="bg-white p-4 text-left">
            <p className="text-xs font-semibold text-slate-900">{icon}</p>
            <p className="mt-1 text-xs leading-5 text-slate-500">{title}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function UserBubble({ message }: { message: Extract<Message, { role: "user" }> }) {
  return (
    <div className="flex justify-end animate-fade-up">
      <div className="max-w-[85%] rounded-lg border border-blue-100 bg-blue-50 px-4 py-3">
        {message.notes.trim() && (
          <p className="whitespace-pre-wrap text-sm text-slate-800">{message.notes}</p>
        )}
        {(message.site || message.client) && (
          <p className="mt-1 text-[11px] text-slate-400">
            {[message.site && `Site: ${message.site}`, message.client && `Client: ${message.client}`]
              .filter(Boolean)
              .join("  ·  ")}
          </p>
        )}
        {message.media.length > 0 && (
          <p className="mt-2 flex flex-wrap gap-1">
            {message.media.map((m, i) => (
              <span
                key={i}
                className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] text-slate-400"
              >
                {m.kind === "video" ? "🎬" : "🖼️"} {m.name}
              </span>
            ))}
          </p>
        )}
      </div>
    </div>
  );
}

function ErrorBubble({ message }: { message: string }) {
  return (
    <div className="flex justify-center animate-fade-up">
      <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 max-w-lg">
        <AlertTriangle size={16} className="mt-0.5 shrink-0 text-red-600" />
        <div>
          <p className="text-xs font-semibold text-red-300">Analysis failed</p>
          <p className="mt-0.5 text-xs text-red-300/80">{message}</p>
        </div>
      </div>
    </div>
  );
}

