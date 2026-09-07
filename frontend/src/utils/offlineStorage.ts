/**
 * OmniCart AI — Resilient Offline Storage & Sync Queue (v2).
 * Guarantees zero-latency bazaar interactions in low-connectivity areas.
 * Features:
 * - Schema versioning and corrupt JSON recovery (prevents white screens)
 * - Structured pending sync queue (CREATE, UPDATE, DELETE) with client timestamps
 * - Atomic snapshot persistence and queue flushing on network recovery
 */

export interface CartItem {
  id: string;
  item_name: string;
  category: string;
  quantity: string;
  unit: string;
  price_paid: string;
  currency_code: string;
  store_name?: string;
  is_purchased: boolean;
  created_at: string;
  updated_at?: number;
}

export type ShoppingItem = CartItem;

export interface SyncMutation {
  action: "CREATE" | "UPDATE" | "DELETE";
  item: CartItem;
  clientTimestamp: number;
}

export interface OfflineStorageSchema {
  version: number;
  items: CartItem[];
  pendingSyncQueue: SyncMutation[];
  lastSyncedAt: number | null;
}

const STORAGE_KEY = "omnicart_offline_cache_v2";
const CURRENT_SCHEMA_VERSION = 2;

const INITIAL_STATE: OfflineStorageSchema = {
  version: CURRENT_SCHEMA_VERSION,
  items: [],
  pendingSyncQueue: [],
  lastSyncedAt: null,
};

function isValidSchema(data: unknown): data is OfflineStorageSchema {
  if (typeof data !== "object" || data === null) {
    return false;
  }
  const candidate = data as Partial<OfflineStorageSchema>;
  return (
    typeof candidate.version === "number" &&
    Array.isArray(candidate.items) &&
    Array.isArray(candidate.pendingSyncQueue)
  );
}

export const OfflineStorage = {
  getSnapshot(): OfflineStorageSchema {
    try {
      const rawData = localStorage.getItem(STORAGE_KEY);
      if (!rawData) {
        this.saveSnapshot(INITIAL_STATE);
        return INITIAL_STATE;
      }

      const parsed = JSON.parse(rawData);
      if (!isValidSchema(parsed)) {
        console.warn("[OfflineStorage] Cache schema corrupted or outdated. Resetting to initial state.");
        this.saveSnapshot(INITIAL_STATE);
        return INITIAL_STATE;
      }

      return parsed;
    } catch (error) {
      console.error("[OfflineStorage] Failed to read localStorage:", error);
      return INITIAL_STATE;
    }
  },

  saveSnapshot(state: OfflineStorageSchema): boolean {
    try {
      const serialized = JSON.stringify(state);
      localStorage.setItem(STORAGE_KEY, serialized);
      return true;
    } catch (error) {
      console.error("[OfflineStorage] Failed to write localStorage:", error);
      return false;
    }
  },

  getItems(): CartItem[] {
    return this.getSnapshot().items;
  },

  saveItems(items: CartItem[]): boolean {
    const state = this.getSnapshot();
    state.items = items;
    return this.saveSnapshot(state);
  },

  upsertItem(item: CartItem): void {
    const state = this.getSnapshot();
    const existingIndex = state.items.findIndex((i) => i.id === item.id);
    const updatedItem = { ...item, updated_at: Date.now() };

    if (existingIndex >= 0) {
      state.items[existingIndex] = updatedItem;
    } else {
      state.items.unshift(updatedItem);
    }

    state.pendingSyncQueue.push({
      action: existingIndex >= 0 ? "UPDATE" : "CREATE",
      item: updatedItem,
      clientTimestamp: Date.now(),
    });

    this.saveSnapshot(state);
  },

  addItem(item: CartItem): CartItem[] {
    this.upsertItem(item);
    return this.getItems();
  },

  toggleCheck(itemId: string): boolean {
    const state = this.getSnapshot();
    const target = state.items.find((i) => i.id === itemId);
    if (!target) {
      return false;
    }

    target.is_purchased = !target.is_purchased;
    target.updated_at = Date.now();

    state.pendingSyncQueue.push({
      action: "UPDATE",
      item: { ...target },
      clientTimestamp: Date.now(),
    });

    return this.saveSnapshot(state);
  },

  toggleItem(itemId: string): CartItem[] {
    this.toggleCheck(itemId);
    return this.getItems();
  },

  deleteItem(itemId: string): void {
    const state = this.getSnapshot();
    const target = state.items.find((i) => i.id === itemId);

    state.items = state.items.filter((i) => i.id !== itemId);

    if (target) {
      state.pendingSyncQueue.push({
        action: "DELETE",
        item: target,
        clientTimestamp: Date.now(),
      });
    }

    this.saveSnapshot(state);
  },

  removeItem(itemId: string): CartItem[] {
    this.deleteItem(itemId);
    return this.getItems();
  },

  getQueue(): SyncMutation[] {
    return this.getSnapshot().pendingSyncQueue;
  },

  clearQueue(): void {
    const state = this.getSnapshot();
    state.pendingSyncQueue = [];
    this.saveSnapshot(state);
  },

  flushSyncQueue(): SyncMutation[] {
    const state = this.getSnapshot();
    const queue = [...state.pendingSyncQueue];
    state.pendingSyncQueue = [];
    state.lastSyncedAt = Date.now();
    this.saveSnapshot(state);
    return queue;
  },

  clearAll(): void {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (error) {
      console.error("[OfflineStorage] Failed to clear storage:", error);
    }
  },
};

export const offlineStorage = OfflineStorage;
export default OfflineStorage;
