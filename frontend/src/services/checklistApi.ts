/**
 * OmniCart AI — Checklist API Service
 * All checklist CRUD operations, typed and centralized.
 */

import api from "./api";
import type { CartItem } from "../types";

export interface CreateItemPayload {
  item_name: string;
  category?: string;
  quantity?: number;
  unit?: string;
  price_paid?: number;
  store_name?: string;
}

export const checklistApi = {
  /** Fetch all checklist items (including purchased) */
  async fetchAll(): Promise<CartItem[]> {
    return api.get<CartItem[]>("/api/v1/checklist?include_purchased=true");
  },

  /** Create a new checklist item */
  async create(payload: CreateItemPayload): Promise<CartItem> {
    return api.post<CartItem>("/api/v1/checklist", {
      item_name: payload.item_name,
      category: payload.category || "",
      quantity: payload.quantity ?? 1,
      unit: payload.unit || "шт",
      price_paid: payload.price_paid ?? 0,
      store_name: payload.store_name,
    });
  },

  /** Toggle purchased status */
  async toggle(itemId: string, isPurchased: boolean): Promise<{ id: string; is_purchased: boolean }> {
    return api.patch(`/api/v1/checklist/${itemId}/toggle`, {
      is_purchased: isPurchased,
    });
  },

  /** Delete an item */
  async remove(itemId: string): Promise<void> {
    return api.delete(`/api/v1/checklist/${itemId}`);
  },

  /** Clear all purchased items */
  async clearPurchased(): Promise<{ status: string; deleted_count: number }> {
    return api.post("/api/v1/checklist/clear-purchased");
  },
};

export default checklistApi;
