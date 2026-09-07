/**
 * OmniCart AI — Shared Types
 */

// ── Cart Item (matches backend ChecklistItemResponse) ───────────────────────

export interface CartItem {
  id: string;
  item_name: string;
  category: string;
  quantity: string;
  unit: string;
  price_paid: string;       // Price per unit (string for backend compat)
  currency_code: string;
  store_name?: string;
  is_purchased: boolean;
  created_at: string;
  updated_at?: number;       // Client-side timestamp for local mutations
}

// ── Sync Queue ──────────────────────────────────────────────────────────────

export type MutationAction = "CREATE" | "UPDATE" | "DELETE";

export interface SyncMutation {
  id: string;                // Unique mutation ID
  action: MutationAction;
  item: CartItem;
  clientTimestamp: number;
  retryCount: number;
  status: "queued" | "processing" | "failed";
}

export type SyncState = "synced" | "pending" | "syncing" | "failed" | "offline";

// ── Units & Categories ──────────────────────────────────────────────────────

export type UnitType = "кг" | "шт" | "л" | "упак" | "г";

export const UNITS: { value: UnitType; label: string }[] = [
  { value: "кг", label: "кг" },
  { value: "шт", label: "шт" },
  { value: "л", label: "л" },
  { value: "упак", label: "упак" },
  { value: "г", label: "г" },
];

export interface CategoryDef {
  id: string;
  emoji: string;
  label: string;
}

export const CATEGORIES: CategoryDef[] = [
  { id: "produce",   emoji: "🍎", label: "Фрукты и овощи" },
  { id: "dairy",     emoji: "🥛", label: "Молочное" },
  { id: "bread",     emoji: "🥖", label: "Хлеб" },
  { id: "meat",      emoji: "🥩", label: "Мясо" },
  { id: "fish",      emoji: "🐟", label: "Рыба" },
  { id: "grocery",   emoji: "🥫", label: "Бакалея" },
  { id: "drinks",    emoji: "🥤", label: "Напитки" },
  { id: "sweets",    emoji: "🍫", label: "Сладости" },
  { id: "household", emoji: "🧼", label: "Бытовое" },
  { id: "hygiene",   emoji: "🧴", label: "Гигиена" },
  { id: "pets",      emoji: "🐶", label: "Животные" },
  { id: "other",     emoji: "📦", label: "Другое" },
];

export const DEFAULT_CATEGORY = "📦 Другое";

/**
 * Find the full category string (emoji + label) from a partial match.
 */
export function matchCategory(raw: string): string {
  if (!raw) return DEFAULT_CATEGORY;
  const lower = raw.toLowerCase();
  for (const cat of CATEGORIES) {
    if (
      lower.includes(cat.label.toLowerCase()) ||
      lower.includes(cat.emoji) ||
      lower.includes(cat.id)
    ) {
      return `${cat.emoji} ${cat.label}`;
    }
  }
  return raw || DEFAULT_CATEGORY;
}

// ── Toast ────────────────────────────────────────────────────────────────────

export interface ToastData {
  id: string;
  type: "success" | "info" | "error" | "offline";
  message: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

// ── API Response Types ──────────────────────────────────────────────────────

export interface ApiError {
  error: string;
  request_id?: string;
}

export interface AIParsedItem {
  item_name: string;
  quantity: string;
  unit: string;
  price: string;
  currency: string;
  store_name?: string;
  confidence: string;
}

export interface AIParseResponse {
  parsed_items: AIParsedItem[];
  interpretation: string;
  count: number;
}
