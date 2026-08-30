"use client";

/**
 * Web Speech API dictation hook.
 *
 * Uses the browser-native SpeechRecognition (or webkitSpeechRecognition
 * on older Chrome/Safari).  Detected at runtime — Safari and Firefox
 * may not support it, in which case isSupported is false and the UI
 * should hide the mic button.
 *
 * Returns accumulated transcript text and controls to start/stop.
 */

import { useCallback, useEffect, useRef, useState } from "react";

// Minimal types for the Web Speech API (not in the standard TS DOM lib).
interface SpeechRecognitionResultAlt {
  transcript: string;
  confidence: number;
}
interface SpeechRecognitionResult {
  readonly [index: number]: SpeechRecognitionResultAlt;
  isFinal: boolean;
  readonly length: number;
}
interface SpeechRecognitionEvent extends Event {
  resultIndex: number;
  results: ArrayLike<SpeechRecognitionResult>;
}
interface SpeechRecognitionLike extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((ev: SpeechRecognitionEvent) => void) | null;
  onerror: ((ev: Event & { error?: string; message?: string }) => void) | null;
  onend: (() => void) | null;
  onstart: (() => void) | null;
}

type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function getCtor(): SpeechRecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export interface UseSpeechDictationOptions {
  lang?: string;
  continuous?: boolean;
}

export function useSpeechDictation(options: UseSpeechDictationOptions = {}) {
  const { lang = "en-PH", continuous = true } = options;
  const ctor = getCtor();
  const isSupported = ctor !== null;

  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const startedAtRef = useRef<number>(0);

  const start = useCallback(() => {
    if (!ctor) {
      setError("Speech recognition is not supported in this browser.");
      return;
    }
    if (recognitionRef.current) return; // already running
    setError(null);
    setTranscript("");

    const rec = new ctor();
    rec.continuous = continuous;
    rec.interimResults = false;
    rec.lang = lang;

    rec.onstart = () => {
      startedAtRef.current = Date.now();
      setIsListening(true);
    };
    rec.onresult = (ev) => {
      let combined = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const result = ev.results[i];
        if (result && result[0]) {
          combined += result[0].transcript;
        }
      }
      if (combined) {
        setTranscript((prev) => (prev ? prev + " " + combined : combined));
      }
    };
    rec.onerror = (ev) => {
      const code = ev.error ?? "unknown";
      // `aborted` fires when stop() is called programmatically — not an error.
      if (code === "aborted") return;
      setError(`Speech error: ${code}`);
    };
    rec.onend = () => {
      // Auto-restart if still within listening window and continuous
      if (recognitionRef.current && continuous && Date.now() - startedAtRef.current < 60_000) {
        try { rec.start(); return; } catch { /* fall through */ }
      }
      recognitionRef.current = null;
      setIsListening(false);
    };

    try {
      rec.start();
      recognitionRef.current = rec;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start dictation.");
      recognitionRef.current = null;
    }
  }, [ctor, continuous, lang]);

  const stop = useCallback(() => {
    const rec = recognitionRef.current;
    if (!rec) return;
    // Stop auto-restart by setting an immediate timer threshold.
    startedAtRef.current = 0;
    try { rec.stop(); } catch { /* ignore */ }
    recognitionRef.current = null;
    setIsListening(false);
  }, []);

  // Cleanup on unmount.
  useEffect(() => () => {
    const rec = recognitionRef.current;
    if (rec) {
      startedAtRef.current = 0;
      try { rec.abort(); } catch { /* ignore */ }
      recognitionRef.current = null;
    }
  }, []);

  const reset = useCallback(() => {
    setTranscript("");
    setError(null);
  }, []);

  return { isSupported, isListening, transcript, error, start, stop, reset };
}
