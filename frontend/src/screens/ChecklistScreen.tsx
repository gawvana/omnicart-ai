import React, { useState, useEffect, useCallback, useMemo } from "react";
import { motion } from "framer-motion";
import {
  Check,
  Plus,
  Trash2,
  RefreshCw,
  ShoppingBag,
  MapPin,
  CheckCheck,
  ChevronRight,
} from "lucide-react";

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

function getTelegramWebApp(): any {
  return (window as any).Telegram?.WebApp ?? null;
}

function getInitData(): string {
  return getTelegramWebApp()?.initData ?? "";
}

function haptic(type: "light" | "medium" | "heavy" = "light") {
  try {
    getTelegramWebApp()?.HapticFeedback?.impactOccurred(type);
  } catch {
    // Graceful fallback
  }
}

export const ChecklistScreen: React.FC<{
  onOpenNotes?: () => void;
  onOpenMarket?: () => void;
}> = ({ onOpenNotes, onOpenMarket }) => {
  const [items, setItems] = useState<ChecklistItem[]>([]);
  const [filter, setFilter] = useState<"all" | "pending" | "purchased">("all");
  const [quickText, setQuickText] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchItems = useCallback(async () => {
    setIsLoading(true);
    try {
      const initData = getInitData();
      const res = await fetch("/api/v1/checklist?include_purchased=true", {
        headers: {
          "Content-Type": "application/json",
          Authorization: `tma ${initData}`,
        },
      });
      if (res.ok) {
        const data = await res.json();
        setItems(data);
      }
    } catch (err) {
      console.warn("Fetch checklist failed", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  const handleToggle = async (id: string, currentStatus: boolean) => {
    haptic("light");
    // Optimistic UI update
    setItems((prev) =>
      prev.map((it) => (it.id === id ? { ...it, is_purchased: !currentStatus } : it))
    );

    try {
      const initData = getInitData();
      await fetch(`/api/v1/checklist/${id}/toggle`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `tma ${initData}`,
        },
        body: JSON.stringify({ is_purchased: !currentStatus }),
      });
    } catch (err) {
      // Revert on error
      setItems((prev) =>
        prev.map((it) => (it.id === id ? { ...it, is_purchased: currentStatus } : it))
      );
    }
  };

  const handleDelete = async (id: string) => {
    haptic("medium");
    setItems((prev) => prev.filter((it) => it.id !== id));

    try {
      const initData = getInitData();
      await fetch(`/api/v1/checklist/${id}`, {
        method: "DELETE",
        headers: {
          Authorization: `tma ${initData}`,
        },
      });
    } catch (err) {
      console.warn("Delete item failed", err);
    }
  };

  const handleClearPurchased = async () => {
    haptic("medium");
    const purchasedIds = items.filter((i) => i.is_purchased).map((i) => i.id);
    setItems((prev) => prev.filter((i) => !i.is_purchased));

    for (const pid of purchasedIds) {
      try {
        const initData = getInitData();
        await fetch(`/api/v1/checklist/${pid}`, {
          method: "DELETE",
          headers: { Authorization: `tma ${initData}` },
        });
      } catch {
        // ignore
      }
    }
  };

  const handleQuickAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!quickText.trim() || isSubmitting) return;

    haptic("light");
    setIsSubmitting(true);

    try {
      const initData = getInitData();
      const res = await fetch("/api/v1/checklist", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `tma ${initData}`,
        },
        body: JSON.stringify({
          item_name: quickText.trim(),
          quantity: 1,
          unit: "шт",
          price_paid: 0,
        }),
      });

      if (res.ok) {
        setQuickText("");
        fetchItems();
      }
    } catch (err) {
      console.warn("Add item failed", err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const filteredItems = useMemo(() => {
    if (filter === "pending") return items.filter((i) => !i.is_purchased);
    if (filter === "purchased") return items.filter((i) => i.is_purchased);
    return items;
  }, [items, filter]);

  const pendingCount = items.filter((i) => !i.is_purchased).length;
  const purchasedCount = items.filter((i) => i.is_purchased).length;

  const totalEstimatedCost = useMemo(() => {
    return items.reduce((sum, item) => {
      const price = parseFloat(item.price_paid || "0");
      return sum + (isNaN(price) ? 0 : price);
    }, 0);
  }, [items]);

  return (
    <div className="flex flex-col gap-5 px-4 pt-4 pb-28">
      {/* Dynamic Summary Card (iOS 26 Frosted Glass) */}
      <div className="ios-glass-card rounded-ios-lg p-5">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center text-white">
              <ShoppingBag className="w-4 h-4" />
            </div>
            <div>
              <h1 className="text-sm font-semibold text-white tracking-tight">
                Чек-лист покупок
              </h1>
              <div className="flex items-center gap-1 text-[11px] text-zinc-400">
                <MapPin className="w-3 h-3 text-zinc-500" />
                <span>Гулистан, Сырдарья</span>
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={fetchItems}
            disabled={isLoading}
            className="w-8 h-8 rounded-lg bg-white/5 hover:bg-white/10 flex items-center justify-center text-zinc-400 hover:text-white transition active:scale-95"
            title="Обновить"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
          </button>
        </div>

        {/* Counters */}
        <div className="grid grid-cols-3 gap-2 pt-1 border-t border-white/5">
          <div className="p-2 rounded-xl bg-black/40 border border-white/5 text-center">
            <div className="text-[10px] text-zinc-500">Осталось</div>
            <div className="text-sm font-semibold text-white mt-0.5">{pendingCount}</div>
          </div>

          <div className="p-2 rounded-xl bg-black/40 border border-white/5 text-center">
            <div className="text-[10px] text-zinc-500">Куплено</div>
            <div className="text-sm font-semibold text-zinc-400 mt-0.5">{purchasedCount}</div>
          </div>

          <div className="p-2 rounded-xl bg-black/40 border border-white/5 text-center">
            <div className="text-[10px] text-zinc-500">Оценка суммы</div>
            <div className="text-xs font-mono font-semibold text-white mt-0.5 truncate">
              {totalEstimatedCost > 0 ? `${totalEstimatedCost.toLocaleString()} сум` : "—"}
            </div>
          </div>
        </div>

        {/* Quick actions for Notes & Market */}
        <div className="grid grid-cols-2 gap-2 pt-3">
          {onOpenNotes && (
            <button
              type="button"
              onClick={onOpenNotes}
              className="py-2 px-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/5 text-[11px] font-medium text-zinc-300 flex items-center justify-center gap-1.5 transition active:scale-98"
            >
              <span>Из Xiaomi Заметок</span>
              <ChevronRight className="w-3 h-3 text-zinc-500" />
            </button>
          )}

          {onOpenMarket && (
            <button
              type="button"
              onClick={onOpenMarket}
              className="py-2 px-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/5 text-[11px] font-medium text-zinc-300 flex items-center justify-center gap-1.5 transition active:scale-98"
            >
              <span>Цены в Гулистане</span>
              <ChevronRight className="w-3 h-3 text-zinc-500" />
            </button>
          )}
        </div>
      </div>

      {/* Quick Add Bar */}
      <form onSubmit={handleQuickAdd} className="flex gap-2">
        <input
          type="text"
          value={quickText}
          onChange={(e) => setQuickText(e.target.value)}
          placeholder="Добавить товар (напр. картошка 2кг, молоко)..."
          className="flex-1 px-4 py-3 rounded-xl bg-zinc-900 border border-white/10 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-white/30"
        />
        <button
          type="submit"
          disabled={!quickText.trim() || isSubmitting}
          className="px-4 py-3 rounded-xl bg-white text-black hover:bg-zinc-200 active:scale-95 transition text-xs font-semibold flex items-center justify-center disabled:opacity-40"
        >
          <Plus className="w-4 h-4" />
        </button>
      </form>

      {/* Filter Tabs */}
      <div className="flex items-center justify-between">
        <div className="flex gap-1.5 bg-white/[0.04] p-1 rounded-xl border border-white/5 text-xs">
          <button
            type="button"
            onClick={() => setFilter("all")}
            className={`px-3 py-1 rounded-lg font-medium transition ${
              filter === "all" ? "bg-white text-black font-semibold" : "text-zinc-400 hover:text-white"
            }`}
          >
            Все ({items.length})
          </button>
          <button
            type="button"
            onClick={() => setFilter("pending")}
            className={`px-3 py-1 rounded-lg font-medium transition ${
              filter === "pending" ? "bg-white text-black font-semibold" : "text-zinc-400 hover:text-white"
            }`}
          >
            Купить ({pendingCount})
          </button>
          <button
            type="button"
            onClick={() => setFilter("purchased")}
            className={`px-3 py-1 rounded-lg font-medium transition ${
              filter === "purchased" ? "bg-white text-black font-semibold" : "text-zinc-400 hover:text-white"
            }`}
          >
            Куплено ({purchasedCount})
          </button>
        </div>

        {purchasedCount > 0 && (
          <button
            type="button"
            onClick={handleClearPurchased}
            className="text-[11px] text-zinc-500 hover:text-zinc-300 flex items-center gap-1 transition"
          >
            <Trash2 className="w-3 h-3" />
            <span>Очистить купленное</span>
          </button>
        )}
      </div>

      {/* Items List */}
      <div className="space-y-2">
        {filteredItems.length === 0 ? (
          <div className="ios-glass-card rounded-ios-lg p-8 text-center flex flex-col items-center justify-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-white/5 flex items-center justify-center text-zinc-500">
              <CheckCheck className="w-6 h-6" />
            </div>
            <div>
              <div className="text-sm font-medium text-white">Список пуст</div>
              <p className="text-xs text-zinc-500 mt-1 max-w-xs">
                Добавьте товары через строку ввода выше или импортируйте список из заметок Xiaomi.
              </p>
            </div>
          </div>
        ) : (
          filteredItems.map((item) => {
            const price = parseFloat(item.price_paid || "0");

            return (
              <motion.div
                key={item.id}
                layout
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.96 }}
                className={`ios-glass-card rounded-ios p-3.5 flex items-center justify-between gap-3 transition ${
                  item.is_purchased ? "opacity-45 bg-black/40" : ""
                }`}
              >
                {/* Left: Checkmark button + Details */}
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <button
                    type="button"
                    onClick={() => handleToggle(item.id, item.is_purchased)}
                    className={`w-5 h-5 rounded-md flex items-center justify-center transition shrink-0 border ${
                      item.is_purchased
                        ? "bg-white text-black border-white"
                        : "border-zinc-600 bg-transparent hover:border-zinc-400"
                    }`}
                  >
                    {item.is_purchased && <Check className="w-3.5 h-3.5 stroke-[3]" />}
                  </button>

                  <div className="min-w-0">
                    <div
                      className={`text-xs font-medium truncate ${
                        item.is_purchased ? "line-through text-zinc-400" : "text-white"
                      }`}
                    >
                      {item.item_name}
                    </div>

                    <div className="flex items-center gap-1.5 text-[11px] text-zinc-500 mt-0.5">
                      {parseFloat(item.quantity) > 0 && (
                        <span>
                          {parseFloat(item.quantity)} {item.unit}
                        </span>
                      )}
                      {item.store_name && (
                        <>
                          <span>•</span>
                          <span>{item.store_name}</span>
                        </>
                      )}
                      {price > 0 && (
                        <>
                          <span>•</span>
                          <span className="font-mono text-zinc-400">{price.toLocaleString()} сум</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                {/* Right: Delete */}
                <button
                  type="button"
                  onClick={() => handleDelete(item.id)}
                  className="w-7 h-7 rounded-lg hover:bg-white/10 text-zinc-600 hover:text-zinc-300 flex items-center justify-center transition active:scale-95 shrink-0"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </motion.div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default ChecklistScreen;
