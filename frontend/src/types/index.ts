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
  has_custom_quantity?: boolean; // True ONLY if user explicitly specified a weight or quantity
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

export const UNITS: { value: UnitType; label: string; icon: string }[] = [
  { value: "кг", label: "кг", icon: "⚖️" },
  { value: "шт", label: "шт", icon: "🔢" },
  { value: "л", label: "л", icon: "🥛" },
  { value: "упак", label: "упак", icon: "📦" },
  { value: "г", label: "г", icon: "🏷️" },
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

/**
 * Smart custom product emoji matching for rich visual recognition.
 */
export function getProductEmoji(name: string, category?: string): string {
  const lower = (name || "").toLowerCase().trim();
  if (/яблок|груш|банан|апельсин|мандарин|лимон|виноград|клубник|ягод|фрукт|абрикос|персик|черешн|вишн|арбуз|дыня|ананас|манго/i.test(lower)) return "🍎";
  if (/помидор|томат|огур|картоф|картошк|морков|лук|чеснок|капуст|перец|зелень|укроп|петрушк|баклажан|кабачок|свекл|гриб/i.test(lower)) return "🥦";
  if (/молок|сливк|кефир|йогурт|ряженк|айран/i.test(lower)) return "🥛";
  if (/сыр|творог|брынз|сулугуни/i.test(lower)) return "🧀";
  if (/хлеб|батон|лаваш|булочк|выпечк|лепешк|багет|круассан/i.test(lower)) return "🥖";
  if (/мясо|говядин|баранин|куриц|индейк|фарш|стейк|филе|шашлык/i.test(lower)) return "🥩";
  if (/колбас|сосиск|сардельк|ветчин/i.test(lower)) return "🥓";
  if (/рыб|лосось|семг|форель|тунец|креветк|мидии|икра/i.test(lower)) return "🐟";
  if (/яйц/i.test(lower)) return "🥚";
  if (/макарон|спагетти|паста|лапш/i.test(lower)) return "🍝";
  if (/рис|гречк|овсянк|пшено|булгур|круп|каша/i.test(lower)) return "🍚";
  if (/масло|оливков/i.test(lower)) return "🫒";
  if (/мука|сахар|соль|специи|приправ/i.test(lower)) return "🧂";
  if (/чай|кофе|какао/i.test(lower)) return "☕";
  if (/вод[аы]|сок|компот|напиток|газировк|кола|pepsi|fanta|sprite/i.test(lower)) return "🥤";
  if (/пив|вино|алкогол/i.test(lower)) return "🍷";
  if (/шоколад|конфет|печень|торт|пирожн|сладост|вафл|зефир|морожен/i.test(lower)) return "🍫";
  if (/мыл|порошок|гель|салфетк|бумаг|моющее|пакет|губк|белизн/i.test(lower)) return "🧼";
  if (/шампун|паст|щетк|крем|дезодорант|ватн|бритв/i.test(lower)) return "🧴";
  if (/корм|кош|собак|кот/i.test(lower)) return "🐶";

  if (category) {
    for (const cat of CATEGORIES) {
      if (category.includes(cat.emoji) || category.toLowerCase().includes(cat.label.toLowerCase())) {
        return cat.emoji;
      }
    }
  }
  return "🛍️";
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
