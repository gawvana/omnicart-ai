import React, {
  useState,
  useEffect,
  useCallback,
  useMemo,
  useRef,
} from "react";
import {
  motion,
  AnimatePresence,
  useMotionValue,
  useTransform,
  type PanInfo,
} from "framer-motion";
import DynamicIsland from "../components/DynamicIsland";
import LiquidCard from "../components/LiquidCard";

// ── Types ───────────────────────────────────────────────────────────────────

interface ChecklistItem {
  id: string;
  item_name: string;
  quantity: string;
  unit: string;
  price_paid: string;
  currency_code: string;
  store_name: string | null;
  is_purchased: boolean;
  created_at: string;
}

interface CartSummary {
  totalItems: number;
  purchasedItems: number;
  totalCost: string;
  currency: string;
}

// ── Telegram SDK Helpers ────────────────────────────────────────────────────

function getTelegramWebApp(): any {
  return (window as any).Telegram?.WebApp ?? null;
}

function getInitData(): string {
  const tg = getTelegramWebApp();
  return tg?.initData ?? "";
}

function haptic(type: "light" | "medium" | "heavy" | "rigid" | "soft" = "light") {
  try {
    getTelegramWebApp()?.HapticFeedback?.impactOccurred(type);
  } catch {
    // graceful degradation
  }
}

function hapticNotification(type: "success" | "warning" | "error" = "success") {
  try {
    getTelegramWebApp()?.HapticFeedback?.notificationOccurred(type);
  } catch {
    // graceful degradation
  }
}

// ── API Client ──────────────────────────────────────────────────────────────

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const initData = getInitData();
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `tma ${initData}`,
      ...(options.headers ?? {}),
    },
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }

  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

// ── Swipeable Item ──────────────────────────────────────────────────────────

interface SwipeableItemProps {
  item: ChecklistItem;
  onToggle: (id: string, purchased: boolean) => void;
  onDelete: (id: string) => void;
}

const SWIPE_THRESHOLD = 80;

const SwipeableItem: React.FC<SwipeableItemProps> = ({
  item,
  onToggle,
  onDelete,
}) => {
  const x = useMotionValue(0);
  const deleteOpacity = useTransform(x, [-SWIPE_THRESHOLD, -20], [1, 0]);
  const checkOpacity = useTransform(x, [20, SWIPE_THRESHOLD], [0, 1]);
  const cardScale = useTransform(
    x,
    [-SWIPE_THRESHOLD * 1.5, 0, SWIPE_THRESHOLD * 1.5],
    [0.96, 1, 0.96]
  );

  const handleDragEnd = useCallback(
    (_: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
      const offset = info.offset.x;
      if (offset < -SWIPE_THRESHOLD) {
        haptic("heavy");
        onDelete(item.id);
      } else if (offset > SWIPE_THRESHOLD) {
        haptic("medium");
        onToggle(item.id, !item.is_purchased);
      }
    },
    [item.id, item.is_purchased, onDelete, onToggle]
  );

  const priceNum = parseFloat(item.price_paid);
  const qtyNum = parseFloat(item.quantity);

  return (
    <motion.div
      className="relative mb-2"
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: -200, scale: 0.8 }}
      transition={{ type: "spring", stiffness: 350, damping: 30 }}
    >
      {/* Swipe background layers */}
      <div className="absolute inset-0 rounded-2xl overflow-hidden">
        {/* Left (swipe-right): check */}
        <motion.div
          className="absolute inset-y-0 left-0 w-1/2 flex items-center pl-5"
          style={{
            opacity: checkOpacity,
            background: "linear-gradient(90deg, rgba(16, 185, 129, 0.25) 0%, transparent 100%)",
          }}
        >
          <span className="text-2xl">
            {item.is_purchased ? "↩️" : "✅"}
          </span>
        </motion.div>

        {/* Right (swipe-left): delete */}
        <motion.div
          className="absolute inset-y-0 right-0 w-1/2 flex items-center justify-end pr-5"
          style={{
            opacity: deleteOpacity,
            background: "linear-gradient(270deg, rgba(239, 68, 68, 0.25) 0%, transparent 100%)",
          }}
        >
          <span className="text-2xl">🗑️</span>
        </motion.div>
      </div>

      {/* Main card */}
      <motion.div
        drag="x"
        dragConstraints={{ left: 0, right: 0 }}
        dragElastic={0.4}
        onDragEnd={handleDragEnd}
        style={{ x, scale: cardScale }}
        className="relative cursor-grab active:cursor-grabbing"
      >
        <LiquidCard
          variant={item.is_purchased ? "inset" : "default"}
          padding="none"
          animate={false}
        >
          <div className="flex items-center gap-3 p-3">
            {/* Checkbox circle */}
            <button
              className={`
                flex-shrink-0 w-7 h-7 rounded-full border-2 flex items-center justify-center
                transition-all duration-300
                ${
                  item.is_purchased
                    ? "bg-emerald-500/80 border-emerald-400 shadow-[0_0_12px_rgba(16,185,129,0.3)]"
                    : "border-white/20 dark:border-white/15 bg-transparent hover:border-indigo-400/50"
                }
              `}
              onClick={(e) => {
                e.stopPropagation();
                haptic("medium");
                onToggle(item.id, !item.is_purchased);
              }}
            >
              <AnimatePresence mode="wait">
                {item.is_purchased && (
                  <motion.svg
                    key="check"
                    width="14"
                    height="14"
                    viewBox="0 0 14 14"
                    initial={{ scale: 0, rotate: -45 }}
                    animate={{ scale: 1, rotate: 0 }}
                    exit={{ scale: 0, rotate: 45 }}
                    transition={{ type: "spring", stiffness: 500, damping: 25 }}
                  >
                    <path
                      d="M2 7L5.5 10.5L12 3.5"
                      stroke="white"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      fill="none"
                    />
                  </motion.svg>
                )}
              </AnimatePresence>
            </button>

            {/* Item details */}
            <div className="flex-1 min-w-0">
              <p
                className={`text-sm font-medium truncate transition-all duration-300 ${
                  item.is_purchased
                    ? "text-white/30 dark:text-white/25 line-through"
                    : "text-gray-900 dark:text-white/90"
                }`}
              >
                {item.item_name}
              </p>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-xs text-white/40 dark:text-white/30 tabular-nums">
                  {qtyNum % 1 === 0 ? qtyNum.toFixed(0) : qtyNum.toFixed(2)}{" "}
                  {item.unit}
                </span>
                {item.store_name && (
                  <>
                    <span className="text-white/15">·</span>
                    <span className="text-xs text-white/30 truncate max-w-[100px]">
                      {item.store_name}
                    </span>
                  </>
                )}
              </div>
            </div>

            {/* Price badge */}
            {priceNum > 0 && (
              <div
                className={`
                  flex-shrink-0 px-2.5 py-1 rounded-lg text-xs font-semibold tabular-nums
                  transition-all duration-300
                  ${
                    item.is_purchased
                      ? "bg-emerald-500/10 text-emerald-400/50"
                      : "bg-indigo-500/10 dark:bg-indigo-500/15 text-indigo-500 dark:text-indigo-300"
                  }
                `}
              >
                {priceNum.toLocaleString(undefined, {
                  minimumFractionDigits: 0,
                  maximumFractionDigits: 2,
                })}{" "}
                {item.currency_code}
              </div>
            )}
          </div>
        </LiquidCard>
      </motion.div>
    </motion.div>
  );
};

// ── Add Item Bottom Sheet ───────────────────────────────────────────────────

interface AddItemSheetProps {
  isOpen: boolean;
  onClose: () => void;
  onAdd: (name: string, qty: number, unit: string) => void;
  onAIParse: (text: string) => void;
  isLoading: boolean;
}

const UNITS = ["kg", "g", "lb", "oz", "pcs", "l", "ml"];

const AddItemSheet: React.FC<AddItemSheetProps> = ({
  isOpen,
  onClose,
  onAdd,
  onAIParse,
  isLoading,
}) => {
  const [mode, setMode] = useState<"manual" | "ai">("ai");
  const [name, setName] = useState("");
  const [qty, setQty] = useState("1");
  const [unit, setUnit] = useState("kg");
  const [aiText, setAiText] = useState("");

  const handleSubmit = useCallback(() => {
    if (mode === "ai" && aiText.trim()) {
      haptic("medium");
      onAIParse(aiText.trim());
      setAiText("");
    } else if (mode === "manual" && name.trim()) {
      haptic("medium");
      onAdd(name.trim(), parseFloat(qty) || 1, unit);
      setName("");
      setQty("1");
    }
  }, [mode, aiText, name, qty, unit, onAIParse, onAdd]);

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />

          {/* Sheet */}
          <motion.div
            className="fixed inset-x-0 bottom-0 z-50 px-4 pb-8"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", stiffness: 400, damping: 35 }}
          >
            <div
              className="rounded-3xl overflow-hidden"
              style={{
                background:
                  "linear-gradient(180deg, rgba(30,30,40,0.95) 0%, rgba(20,20,28,0.98) 100%)",
                backdropFilter: "blur(40px) saturate(1.8)",
                WebkitBackdropFilter: "blur(40px) saturate(1.8)",
                boxShadow:
                  "0 -8px 40px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.08)",
                border: "1px solid rgba(255,255,255,0.08)",
              }}
            >
              {/* Handle */}
              <div className="flex justify-center pt-3 pb-2">
                <div className="w-10 h-1 rounded-full bg-white/20" />
              </div>

              <div className="px-5 pb-5">
                {/* Mode toggle */}
                <div className="flex gap-1 p-1 rounded-xl bg-white/5 mb-4">
                  {(["ai", "manual"] as const).map((m) => (
                    <button
                      key={m}
                      className={`
                        flex-1 py-2 rounded-lg text-xs font-semibold transition-all duration-200
                        ${
                          mode === m
                            ? "bg-indigo-500/20 text-indigo-300 shadow-[0_0_12px_rgba(99,102,241,0.15)]"
                            : "text-white/40 hover:text-white/60"
                        }
                      `}
                      onClick={() => {
                        haptic("light");
                        setMode(m);
                      }}
                    >
                      {m === "ai" ? "✨ AI Parse" : "✏️ Manual"}
                    </button>
                  ))}
                </div>

                {/* AI mode */}
                {mode === "ai" && (
                  <div>
                    <textarea
                      className="w-full h-24 bg-white/5 border border-white/10 rounded-xl px-4 py-3
                                 text-sm text-white placeholder-white/25 resize-none
                                 focus:outline-none focus:border-indigo-500/40 focus:ring-1 focus:ring-indigo-500/20
                                 transition-all duration-200"
                      placeholder='Type naturally, e.g.: "bought 2kg potatoes for 500 at the bazaar, 1L milk 200"'
                      value={aiText}
                      onChange={(e) => setAiText(e.target.value)}
                      maxLength={2000}
                    />
                  </div>
                )}

                {/* Manual mode */}
                {mode === "manual" && (
                  <div className="space-y-3">
                    <input
                      className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3
                                 text-sm text-white placeholder-white/25
                                 focus:outline-none focus:border-indigo-500/40 focus:ring-1 focus:ring-indigo-500/20
                                 transition-all duration-200"
                      placeholder="Product name"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      maxLength={255}
                    />
                    <div className="flex gap-2">
                      <input
                        className="w-20 bg-white/5 border border-white/10 rounded-xl px-3 py-3
                                   text-sm text-white text-center tabular-nums
                                   focus:outline-none focus:border-indigo-500/40 focus:ring-1 focus:ring-indigo-500/20
                                   transition-all duration-200"
                        type="number"
                        step="0.1"
                        min="0.01"
                        placeholder="Qty"
                        value={qty}
                        onChange={(e) => setQty(e.target.value)}
                      />
                      <div className="flex flex-1 gap-1 overflow-x-auto">
                        {UNITS.map((u) => (
                          <button
                            key={u}
                            className={`
                              px-3 py-2.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all duration-200
                              ${
                                unit === u
                                  ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/30"
                                  : "bg-white/5 text-white/40 border border-white/5 hover:text-white/60"
                              }
                            `}
                            onClick={() => {
                              haptic("light");
                              setUnit(u);
                            }}
                          >
                            {u}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* Submit button */}
                <motion.button
                  className={`
                    w-full mt-4 py-3.5 rounded-2xl text-sm font-semibold
                    transition-all duration-200
                    ${
                      isLoading
                        ? "bg-indigo-500/20 text-indigo-300/50 cursor-not-allowed"
                        : "bg-indigo-500/80 text-white hover:bg-indigo-500 active:bg-indigo-600 shadow-[0_4px_16px_rgba(99,102,241,0.3)]"
                    }
                  `}
                  onClick={handleSubmit}
                  disabled={isLoading}
                  whileTap={isLoading ? {} : { scale: 0.97 }}
                  transition={{ type: "spring", stiffness: 400, damping: 25 }}
                >
                  {isLoading ? (
                    <span className="flex items-center justify-center gap-2">
                      <motion.span
                        animate={{ rotate: 360 }}
                        transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
                        className="inline-block w-4 h-4 border-2 border-indigo-300/30 border-t-indigo-300 rounded-full"
                      />
                      Parsing with AI…
                    </span>
                  ) : mode === "ai" ? (
                    "✨ Parse & Add"
                  ) : (
                    "Add Item"
                  )}
                </motion.button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

// ── Main Screen ─────────────────────────────────────────────────────────────

const ChecklistScreen: React.FC = () => {
  const [items, setItems] = useState<ChecklistItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSheetOpen, setIsSheetOpen] = useState(false);
  const [islandExpanded, setIslandExpanded] = useState(false);
  const [filter, setFilter] = useState<"all" | "pending" | "done">("all");
  const [error, setError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // ── Fetch items ───────────────────────────────────────────

  const fetchItems = useCallback(async () => {
    try {
      const data = await apiFetch<ChecklistItem[]>(
        "/api/v1/checklist?include_purchased=true"
      );
      setItems(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load items");
    }
  }, []);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  // ── Expand Telegram viewport ──────────────────────────────

  useEffect(() => {
    const tg = getTelegramWebApp();
    if (tg) {
      tg.ready();
      tg.expand();
      if (tg.setHeaderColor) tg.setHeaderColor("#0f0f14");
      if (tg.setBackgroundColor) tg.setBackgroundColor("#0a0a0f");
    }
  }, []);

  // ── Cart summary ──────────────────────────────────────────

  const cart: CartSummary = useMemo(() => {
    const total = items.length;
    const purchased = items.filter((i) => i.is_purchased).length;
    const cost = items.reduce(
      (sum, i) => sum + parseFloat(i.price_paid || "0"),
      0
    );
    const currency = items[0]?.currency_code ?? "USD";
    return {
      totalItems: total,
      purchasedItems: purchased,
      totalCost: cost.toFixed(2),
      currency,
    };
  }, [items]);

  // ── Filtered items ────────────────────────────────────────

  const filteredItems = useMemo(() => {
    switch (filter) {
      case "pending":
        return items.filter((i) => !i.is_purchased);
      case "done":
        return items.filter((i) => i.is_purchased);
      default:
        return items;
    }
  }, [items, filter]);

  // ── Actions ───────────────────────────────────────────────

  const handleToggle = useCallback(
    async (id: string, purchased: boolean) => {
      // Optimistic update
      setItems((prev) =>
        prev.map((i) =>
          i.id === id ? { ...i, is_purchased: purchased } : i
        )
      );

      try {
        await apiFetch(`/api/v1/checklist/${id}/toggle`, {
          method: "PATCH",
          body: JSON.stringify({ is_purchased: purchased }),
        });
        if (purchased) hapticNotification("success");
      } catch {
        // Rollback
        setItems((prev) =>
          prev.map((i) =>
            i.id === id ? { ...i, is_purchased: !purchased } : i
          )
        );
        hapticNotification("error");
      }
    },
    []
  );

  const handleDelete = useCallback(async (id: string) => {
    let removedItem: ChecklistItem | undefined;
    let removedIndex = -1;

    setItems((prev) => {
      removedIndex = prev.findIndex((i) => i.id === id);
      if (removedIndex !== -1) {
        removedItem = prev[removedIndex];
      }
      return prev.filter((i) => i.id !== id);
    });

    try {
      await apiFetch(`/api/v1/checklist/${id}`, { method: "DELETE" });
    } catch {
      // Rollback: re-insert removed item at original position
      if (removedItem) {
        const itemToRestore = removedItem;
        const idx = removedIndex;
        setItems((prev) => {
          const copy = [...prev];
          copy.splice(idx, 0, itemToRestore);
          return copy;
        });
      }
      hapticNotification("error");
    }
  }, []);

  const handleManualAdd = useCallback(
    async (name: string, qty: number, unit: string) => {
      setIsLoading(true);
      try {
        const newItem = await apiFetch<ChecklistItem>("/api/v1/checklist", {
          method: "POST",
          body: JSON.stringify({
            item_name: name,
            quantity: qty,
            unit,
            price_paid: 0,
          }),
        });
        setItems((prev) => [newItem, ...prev]);
        setIsSheetOpen(false);
        hapticNotification("success");
      } catch {
        hapticNotification("error");
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const handleAIParse = useCallback(async (text: string) => {
    setIsLoading(true);
    try {
      await apiFetch("/api/v1/ai/parse-purchase", {
        method: "POST",
        body: JSON.stringify({ text }),
      });
      await fetchItems();
      setIsSheetOpen(false);
      hapticNotification("success");
    } catch {
      hapticNotification("error");
    } finally {
      setIsLoading(false);
    }
  }, [fetchItems]);

  // ── Render ────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white overflow-x-hidden">
      {/* Ambient background gradient */}
      <div
        className="fixed inset-0 pointer-events-none"
        style={{
          background: [
            "radial-gradient(ellipse 80% 50% at 50% -20%, rgba(99,102,241,0.12) 0%, transparent 70%)",
            "radial-gradient(ellipse 60% 40% at 80% 100%, rgba(16,185,129,0.08) 0%, transparent 60%)",
          ].join(", "),
        }}
      />

      {/* Dynamic Island */}
      <DynamicIsland
        cart={cart}
        isExpanded={islandExpanded}
        onToggle={() => setIslandExpanded((p) => !p)}
      />

      {/* Content */}
      <div className="relative z-10 pt-16 px-4 pb-28" ref={listRef}>
        {/* Header */}
        <div className="mb-5">
          <h1 className="text-2xl font-bold tracking-tight">
            Shopping List
          </h1>
          <p className="text-sm text-white/35 mt-1">
            Swipe right to check, left to delete
          </p>
        </div>

        {/* Filter pills */}
        <div className="flex gap-2 mb-4">
          {(
            [
              { key: "all", label: "All", count: items.length },
              {
                key: "pending",
                label: "Pending",
                count: items.filter((i) => !i.is_purchased).length,
              },
              {
                key: "done",
                label: "Done",
                count: items.filter((i) => i.is_purchased).length,
              },
            ] as const
          ).map(({ key, label, count }) => (
            <motion.button
              key={key}
              className={`
                px-3.5 py-1.5 rounded-full text-xs font-medium transition-all duration-200
                ${
                  filter === key
                    ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 shadow-[0_0_12px_rgba(99,102,241,0.1)]"
                    : "bg-white/5 text-white/35 border border-white/5 hover:text-white/50"
                }
              `}
              onClick={() => {
                haptic("light");
                setFilter(key);
              }}
              whileTap={{ scale: 0.95 }}
            >
              {label}
              <span className="ml-1.5 tabular-nums opacity-60">{count}</span>
            </motion.button>
          ))}
        </div>

        {/* Error state */}
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="mb-4"
            >
              <LiquidCard variant="default" padding="sm">
                <div className="flex items-center gap-2">
                  <span className="text-red-400 text-sm">⚠️ {error}</span>
                  <button
                    className="ml-auto text-xs text-indigo-400 font-medium"
                    onClick={fetchItems}
                  >
                    Retry
                  </button>
                </div>
              </LiquidCard>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Empty state */}
        {filteredItems.length === 0 && !error && (
          <motion.div
            className="flex flex-col items-center justify-center py-20"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ type: "spring", stiffness: 300, damping: 25 }}
          >
            <motion.div
              className="text-6xl mb-4"
              animate={{ y: [0, -8, 0] }}
              transition={{ repeat: Infinity, duration: 2.5, ease: "easeInOut" }}
            >
              {filter === "done" ? "🎉" : "🛒"}
            </motion.div>
            <p className="text-white/30 text-sm text-center">
              {filter === "done"
                ? "No completed items yet"
                : filter === "pending"
                ? "All done! Nothing pending."
                : "Your shopping list is empty"}
            </p>
            <p className="text-white/20 text-xs mt-1">
              Tap + to add items
            </p>
          </motion.div>
        )}

        {/* Item list */}
        <AnimatePresence mode="popLayout">
          {filteredItems.map((item) => (
            <SwipeableItem
              key={item.id}
              item={item}
              onToggle={handleToggle}
              onDelete={handleDelete}
            />
          ))}
        </AnimatePresence>
      </div>

      {/* FAB: Add item */}
      <motion.button
        className="fixed bottom-6 right-6 z-40 w-14 h-14 rounded-full
                   flex items-center justify-center text-xl
                   shadow-[0_8px_24px_rgba(99,102,241,0.4)]"
        style={{
          background: "linear-gradient(135deg, #6366F1 0%, #818CF8 100%)",
        }}
        whileTap={{ scale: 0.9, rotate: 90 }}
        whileHover={{ scale: 1.05 }}
        transition={{ type: "spring", stiffness: 400, damping: 20 }}
        onClick={() => {
          haptic("medium");
          setIsSheetOpen(true);
        }}
      >
        <motion.span
          animate={isSheetOpen ? { rotate: 45 } : { rotate: 0 }}
          transition={{ type: "spring", stiffness: 300, damping: 20 }}
        >
          +
        </motion.span>
      </motion.button>

      {/* Bottom sheet */}
      <AddItemSheet
        isOpen={isSheetOpen}
        onClose={() => setIsSheetOpen(false)}
        onAdd={handleManualAdd}
        onAIParse={handleAIParse}
        isLoading={isLoading}
      />
    </div>
  );
};

export default ChecklistScreen;
