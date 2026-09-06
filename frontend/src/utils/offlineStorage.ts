/**
 * OmniCart AI — Offline Storage & Sync Queue.
 * Enables zero-latency interactions in covered bazaar areas with poor 3G reception.
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
}

const STORAGE_KEY = "omnicart_items_v2";
const QUEUE_KEY = "omnicart_pending_queue_v2";

interface PendingMutation {
  type: "toggle" | "add" | "delete";
  itemId?: string;
  payload?: any;
  timestamp: number;
}

export const OfflineStorage = {
  getItems(): CartItem[] {
    try {
      const data = localStorage.getItem(STORAGE_KEY);
      return data ? JSON.parse(data) : [];
    } catch {
      return [];
    }
  },

  saveItems(items: CartItem[]): void {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    } catch (e) {
      console.warn("Local storage write error:", e);
    }
  },

  queueMutation(mutation: PendingMutation): void {
    try {
      const q = this.getQueue();
      q.push(mutation);
      localStorage.setItem(QUEUE_KEY, JSON.stringify(q));
    } catch (e) {
      console.warn("Queue write error:", e);
    }
  },

  getQueue(): PendingMutation[] {
    try {
      const data = localStorage.getItem(QUEUE_KEY);
      return data ? JSON.parse(data) : [];
    } catch {
      return [];
    }
  },

  clearQueue(): void {
    try {
      localStorage.removeItem(QUEUE_KEY);
    } catch {}
  },

  // Optimistic offline toggle
  toggleItem(id: string): CartItem[] {
    const items = this.getItems();
    const target = items.find((i) => i.id === id);
    if (target) {
      target.is_purchased = !target.is_purchased;
      this.saveItems(items);
      this.queueMutation({
        type: "toggle",
        itemId: id,
        payload: { is_purchased: target.is_purchased },
        timestamp: Date.now(),
      });
    }
    return items;
  },

  // Optimistic offline add
  addItem(item: CartItem): CartItem[] {
    const items = [item, ...this.getItems()];
    this.saveItems(items);
    this.queueMutation({
      type: "add",
      payload: item,
      timestamp: Date.now(),
    });
    return items;
  },

  // Optimistic offline remove
  removeItem(id: string): CartItem[] {
    const items = this.getItems().filter((i) => i.id !== id);
    this.saveItems(items);
    this.queueMutation({
      type: "delete",
      itemId: id,
      timestamp: Date.now(),
    });
    return items;
  },
};
