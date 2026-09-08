/**
 * OmniCart AI — Offline Storage Layer (v3)
 * Schema-versioned localStorage with proper queue management and conflict resolution.
 * 
 * Features:
 * - Queue items are only removed AFTER successful API call
 * - Uses client-generated UUID v4
 * - Conflict resolution with timestamp comparison (server vs local last-write-wins)
 * - Corrupted cache recovery & event listener
 */

import type { CartItem, SyncMutation } from "../types";

export interface OfflineStorageSchema {
  version: number;
  items: CartItem[];
  pendingSyncQueue: SyncMutation[];
  lastSyncedAt: number | null;
}

const STORAGE_KEY = "omnicart_v3";
const CURRENT_VERSION = 3;

const EMPTY_STATE: OfflineStorageSchema = {
  version: CURRENT_VERSION,
  items: [],
  pendingSyncQueue: [],
  lastSyncedAt: null,
};

export type CorruptedCacheHandler = (recoveredCount: number) => void;
let corruptedCacheListener: CorruptedCacheHandler | null = null;

/**
 * Register a callback triggered when local storage cache corruption is detected.
 * Returns an unregister function.
 */
export function onCorruptedCache(handler: CorruptedCacheHandler): () => void {
  corruptedCacheListener = handler;
  return () => {
    if (corruptedCacheListener === handler) {
      corruptedCacheListener = null;
    }
  };
}

function isValid(data: unknown): data is OfflineStorageSchema {
  if (typeof data !== "object" || data === null) return false;
  const d = data as Partial<OfflineStorageSchema>;
  return (
    typeof d.version === "number" &&
    Array.isArray(d.items) &&
    Array.isArray(d.pendingSyncQueue)
  );
}

/** Generate a client-side UUID v4 */
export function generateId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for older browsers
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

// ── Storage API ─────────────────────────────────────────────────────────────

export const offlineStore = {
  _read(): OfflineStorageSchema {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return { ...EMPTY_STATE };

      let parsed: unknown;
      try {
        parsed = JSON.parse(raw);
      } catch {
        console.warn("[offlineStore] corrupted JSON cache, resetting");
        this._write(EMPTY_STATE);
        if (corruptedCacheListener) corruptedCacheListener(0);
        return { ...EMPTY_STATE };
      }

      if (!isValid(parsed)) {
        console.warn("[offlineStore] corrupted cache schema, attempting recovery");
        let recoveredQueue: SyncMutation[] = [];
        const candidate = parsed as Record<string, unknown> | null;
        if (candidate && Array.isArray(candidate.pendingSyncQueue)) {
          recoveredQueue = candidate.pendingSyncQueue.filter(
            (m: any) => m && typeof m === "object" && typeof m.id === "string" && m.item
          );
        }
        const recoveredState: OfflineStorageSchema = {
          version: CURRENT_VERSION,
          items: candidate && Array.isArray(candidate.items) ? (candidate.items as CartItem[]) : [],
          pendingSyncQueue: recoveredQueue,
          lastSyncedAt: typeof candidate?.lastSyncedAt === "number" ? candidate.lastSyncedAt : null,
        };
        this._write(recoveredState);
        if (corruptedCacheListener) corruptedCacheListener(recoveredQueue.length);
        return recoveredState;
      }
      return parsed;
    } catch {
      return { ...EMPTY_STATE };
    }
  },

  _write(state: OfflineStorageSchema): void {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (err) {
      console.error("[offlineStore] write failed:", err);
    }
  },

  // ── Items ───────────────────────────────────────────────────────────────

  getItems(): CartItem[] {
    return this._read().items;
  },

  saveItems(items: CartItem[]): void {
    const state = this._read();
    state.items = items;
    state.lastSyncedAt = Date.now();
    this._write(state);
  },

  addItem(item: CartItem): CartItem[] {
    const state = this._read();
    state.items.unshift(item);
    state.pendingSyncQueue.push({
      id: generateId(),
      action: "CREATE",
      item,
      clientTimestamp: Date.now(),
      retryCount: 0,
      status: "queued",
    });
    this._write(state);
    return state.items;
  },

  toggleItem(itemId: string): CartItem[] {
    const state = this._read();
    const target = state.items.find((i) => i.id === itemId);
    if (!target) return state.items;

    target.is_purchased = !target.is_purchased;
    target.updated_at = Date.now();

    state.pendingSyncQueue.push({
      id: generateId(),
      action: "UPDATE",
      item: { ...target },
      clientTimestamp: Date.now(),
      retryCount: 0,
      status: "queued",
    });

    this._write(state);
    return state.items;
  },

  removeItem(itemId: string): CartItem[] {
    const state = this._read();
    const target = state.items.find((i) => i.id === itemId);
    state.items = state.items.filter((i) => i.id !== itemId);

    if (target) {
      state.pendingSyncQueue.push({
        id: generateId(),
        action: "DELETE",
        item: target,
        clientTimestamp: Date.now(),
        retryCount: 0,
        status: "queued",
      });
    }

    this._write(state);
    return state.items;
  },

  updateItem(itemId: string, updates: Partial<CartItem>): CartItem[] {
    const state = this._read();
    const idx = state.items.findIndex((i) => i.id === itemId);
    if (idx < 0) return state.items;

    state.items[idx] = { ...state.items[idx], ...updates, updated_at: Date.now() };
    this._write(state);
    return state.items;
  },

  // ── Queue ───────────────────────────────────────────────────────────────

  getQueue(): SyncMutation[] {
    return this._read().pendingSyncQueue;
  },

  /** Remove a specific mutation from the queue (after successful sync) */
  removeMutation(mutationId: string): void {
    const state = this._read();
    state.pendingSyncQueue = state.pendingSyncQueue.filter((m) => m.id !== mutationId);
    this._write(state);
  },

  /** Mark a mutation as failed and increment retry count */
  markMutationFailed(mutationId: string): void {
    const state = this._read();
    const mut = state.pendingSyncQueue.find((m) => m.id === mutationId);
    if (mut) {
      mut.status = "failed";
      mut.retryCount += 1;
    }
    this._write(state);
  },

  /** Remove mutations that have exceeded max retries */
  pruneFailedMutations(maxRetries: number = 5): void {
    const state = this._read();
    state.pendingSyncQueue = state.pendingSyncQueue.filter(
      (m) => m.retryCount < maxRetries
    );
    this._write(state);
  },

  clearQueue(): void {
    const state = this._read();
    state.pendingSyncQueue = [];
    this._write(state);
  },

  /**
   * Reconcile server items with local pending mutations using timestamp-based conflict resolution.
   * - Server items are the source of truth for baseline state.
   * - Pending local mutations are preserved if newer than server.
   * - Server changes overwrite local state if server has a newer timestamp.
   */
  reconcile(serverItems: CartItem[]): CartItem[] {
    const state = this._read();
    const pendingCreates = state.pendingSyncQueue
      .filter((m) => m.action === "CREATE")
      .map((m) => m.item.id);

    const pendingDeletes = new Set(
      state.pendingSyncQueue
        .filter((m) => m.action === "DELETE")
        .map((m) => m.item.id)
    );

    // Map of itemId -> most recent UPDATE mutation
    const pendingUpdates = new Map<string, SyncMutation>();
    for (const m of state.pendingSyncQueue) {
      if (m.action === "UPDATE" && m.item?.id) {
        const existing = pendingUpdates.get(m.item.id);
        if (!existing || (m.clientTimestamp || 0) >= (existing.clientTimestamp || 0)) {
          pendingUpdates.set(m.item.id, m);
        }
      }
    }

    // Start with server items, filter out deleted, apply conflicts
    const merged = serverItems
      .filter((si) => !pendingDeletes.has(si.id))
      .map((si) => {
        const localMutation = pendingUpdates.get(si.id);
        if (!localMutation) {
          return si;
        }

        const serverTime = si.updated_at ?? (si.created_at ? Date.parse(si.created_at) : 0);
        const localTime = localMutation.clientTimestamp ?? localMutation.item.updated_at ?? 0;

        // If server is newer, server wins
        if (serverTime > localTime) {
          return si;
        }

        return {
          ...si,
          is_purchased: localMutation.item.is_purchased,
          quantity: localMutation.item.quantity || si.quantity,
          price_paid: localMutation.item.price_paid || si.price_paid,
          updated_at: localTime,
        };
      });

    // Add locally-created items that aren't on server yet
    for (const localId of pendingCreates) {
      if (!merged.some((m) => m.id === localId)) {
        const localItem = state.items.find((i) => i.id === localId);
        if (localItem) {
          merged.unshift(localItem);
        }
      }
    }

    state.items = merged;
    state.lastSyncedAt = Date.now();
    this._write(state);
    return merged;
  },

  clearAll(): void {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {}
  },
};

export default offlineStore;
