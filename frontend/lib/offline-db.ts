/**
 * IndexedDB queue for offline SOW submission persistence.
 *
 * When the network is unavailable and the user submits a new SOW, the
 * submission is stored here so the user can review it and retry once
 * connectivity is restored.  The queue is intentionally manual-retry only
 * (no automatic background retry) to avoid duplicating submissions.
 */

const DB_NAME = "osiris-offline";
const DB_VERSION = 1;
const STORE_NAME = "pending-submissions";

export interface PendingSubmission {
  id?: number;          // auto-incremented by IndexedDB
  created_at: string;   // ISO timestamp
  status: "pending" | "processing" | "failed";
  attempts: number;
  lastError?: string;
  notes: string;
  site: string;
  client: string;
  /** File objects cannot be serialised, so we store them as Blob URLs */
  mediaFiles: { name: string; type: string; size: number; blobUrl: string }[];
}

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (ev) => {
      const db = (ev.target as IDBOpenDBRequest).result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "id", autoIncrement: true });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function addPending(submission: Omit<PendingSubmission, "id">): Promise<number> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const req = tx.objectStore(STORE_NAME).add(submission);
    req.onsuccess = () => resolve(req.result as number);
    req.onerror = () => reject(req.error);
    tx.oncomplete = () => db.close();
  });
}

export async function getPending(): Promise<PendingSubmission[]> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readonly");
    const req = tx.objectStore(STORE_NAME).getAll();
    req.onsuccess = () => resolve(req.result as PendingSubmission[]);
    req.onerror = () => reject(req.error);
    tx.oncomplete = () => db.close();
  });
}

export async function updatePending(
  id: number,
  changes: Partial<Omit<PendingSubmission, "id">>,
): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const store = tx.objectStore(STORE_NAME);
    const getReq = store.get(id);
    getReq.onsuccess = () => {
      const record = { ...(getReq.result as PendingSubmission), ...changes };
      const putReq = store.put(record);
      putReq.onerror = () => reject(putReq.error);
      putReq.onsuccess = () => resolve();
    };
    getReq.onerror = () => reject(getReq.error);
    tx.oncomplete = () => db.close();
  });
}

export async function deletePending(id: number): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const req = tx.objectStore(STORE_NAME).delete(id);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
    tx.oncomplete = () => db.close();
  });
}

export async function clearAll(): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const req = tx.objectStore(STORE_NAME).clear();
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
    tx.oncomplete = () => db.close();
  });
}
