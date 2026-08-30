// Phase: 1
// Offline queue state management. Encapsulates IndexedDB reads and exposes
// queue operations so consumers (PendingQueueBanner, future queue pages) stay
// decoupled from the storage implementation.
import { useCallback, useEffect, useState } from "react";
import { clearAll as dbClearAll, deletePending, getPending, type PendingSubmission } from "@/lib/offline-db";

export interface UseOfflineQueueResult {
  /** Current pending submissions loaded from IndexedDB. */
  queue: PendingSubmission[];
  /** Reload queue from IndexedDB. Call after any external mutation. */
  reload: () => Promise<void>;
  /**
   * Increment the version counter to force a re-read of IndexedDB.
   * Call this after mutations made outside the hook (e.g., ChatInput.addPending).
   */
  bump: () => void;
  /**
   * Retry a single pending submission.
   * Calls `onRetry(sub)` then removes the item from the queue on success.
   */
  retry: (sub: PendingSubmission, onRetry: (s: PendingSubmission) => Promise<boolean>) => Promise<void>;
  /** Remove a single item from the queue. */
  discard: (id: number) => Promise<void>;
  /** Remove all pending items from the queue. */
  discardAll: () => Promise<void>;
}

export function useOfflineQueue(): UseOfflineQueueResult {
  const [queue, setQueue] = useState<PendingSubmission[]>([]);
  // Bumped after any mutation so the effect re-fires and re-reads IndexedDB.
  // Without this the banner would never re-render when ChatInput adds a pending
  // submission from outside this hook.
  const [version, setVersion] = useState(0);

  const reload = useCallback(async () => {
    try {
      setQueue(await getPending());
    } catch {
      /* IndexedDB unavailable in this context */
    }
  }, []);

  const discard = useCallback(
    async (id: number) => {
      await deletePending(id);
      await reload();
      setVersion((v) => v + 1);
    },
    [reload]
  );

  const discardAll = useCallback(async () => {
    await dbClearAll();
    await reload();
    setVersion((v) => v + 1);
  }, [reload]);

  const retry = useCallback(
    async (sub: PendingSubmission, onRetry: (s: PendingSubmission) => Promise<boolean>) => {
      await onRetry(sub);
      if (sub.id !== undefined) await discard(sub.id);
    },
    [discard]
  );

  // Bump the version counter to force the useEffect to re-fire.
  const bump = useCallback(() => { setVersion((v) => v + 1); }, []);

  // Initial load + re-load whenever version changes (bump) or reload changes.
  useEffect(() => { void reload(); }, [reload, version]);

  // Also re-load when any instance of the hook mutates the queue (via
  // notifyQueueMutated). This decouples ChatInput (which writes via
  // addPending) from PendingQueueBanner (which reads via useOfflineQueue).
  useEffect(() => {
    function onMutated() { void reload(); }
    window.addEventListener("osiris:offline-queue-mutated", onMutated);
    return () => window.removeEventListener("osiris:offline-queue-mutated", onMutated);
  }, [reload]);

  return { queue, reload, bump, retry, discard, discardAll };
}

/**
 * Broadcast a mutation to every mounted useOfflineQueue() instance.
 * Call after any IndexedDB write made outside the hook
 * (e.g. ChatInput.handleSubmit -> addPending).
 */
export function notifyQueueMutated(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("osiris:offline-queue-mutated"));
  }
}
