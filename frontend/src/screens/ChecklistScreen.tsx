import React, { useState, useEffect, useCallback, useMemo } from "react";
import { motion } from "framer-motion";
import {
  Check,
  Plus,
  Trash2,
  RefreshCw,
  ShoppingBag,
  Users,
  Search,
  Tag,
} from "lucide-react";
import { CartItem, OfflineStorage } from "../utils/offlineStorage";
import { IslandNotification } from "../components/DynamicIsland";
import FamilyShareModal from "../components/FamilyShareModal";
import PriceEditModal from "../components/PriceEditModal";

interface ChecklistScreenProps {
  onNotify?: (notif: IslandNotification) => void;
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
  } catch {}
}

export const ChecklistScreen: React.FC<ChecklistScreenProps> = ({
  onNotify,
}) => {
  const [items, setItems] = useState<CartItem[]>(() => OfflineStorage.getItems());
  const [filter, setFilter] = useState<"all" | "pending" | "purchased">("all");
  const [groupByAisle, setGroupByAisle] = useState(true);
  const [quickText, setQuickText] = useState("");
  const [autocompleteResults, setAutocompleteResults] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isShareModalOpen, setIsShareModalOpen] = useState(false);
  const [priceModalData, setPriceModalData] = useState<{ name: string; price: number } | null>(null);

  // Sync with backend
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
        const data: CartItem[] = await res.json();
        setItems(data);
        OfflineStorage.saveItems(data);
      }
    } catch (err) {
      console.warn("Fetch checklist failed, using offline cache", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  // Autocomplete debounce
  useEffect(() => {
    if (!quickText.trim() || quickText.length < 2) {
      setAutocompleteResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(`/api/v1/market/autocomplete?q=${encodeURIComponent(quickText.trim())}`);
        if (res.ok) {
          const data = await res.json();
          setAutocompleteResults(data.results || []);
        }
      } catch {
        setAutocompleteResults([]);
      }
    }, 150);
    return () => clearTimeout(timer);
  }, [quickText]);

  // Optimistic Toggle with Dynamic Island notification
  const handleToggle = async (id: string, currentStatus: boolean) => {
    haptic("medium");
    const updated = OfflineStorage.toggleItem(id);
    setItems(updated);

    const target = updated.find((i) => i.id === id);
    if (target && target.is_purchased) {
      const price = parseFloat(target.price_paid) || 0;
      const savings = price > 0 ? Math.round(price * 0.15) : 1500;
      onNotify?.({
        id: String(Date.now()),
        type: "savings",
        title: `Куплено: ${target.item_name}`,
        subtitle: "Сэкономлено на базаре Гулистана",
        amount: `${savings.toLocaleString("ru-RU")} сум`,
      });
    }

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
    } catch {
      // Handled offline via queue
    }
  };

  // Optimistic Add
  const handleAddItem = async (name: string, price: number = 0, unit: string = "кг", category?: string) => {
    if (!name.trim()) return;
    haptic("light");

    const newItem: CartItem = {
      id: "opt_" + Math.random().toString(36).substring(2, 9),
      item_name: name.trim(),
      category: category || "🥫 Бакалея и специи",
      quantity: "1.0",
      unit: unit,
      price_paid: String(price),
      currency_code: "UZS",
      is_purchased: false,
      created_at: new Date().toISOString(),
    };

    const updated = OfflineStorage.addItem(newItem);
    setItems(updated);
    setQuickText("");
    setAutocompleteResults([]);

    onNotify?.({
      id: String(Date.now()),
      type: "success",
      title: `Добавлено: ${name}`,
      subtitle: category,
    });

    try {
      const initData = getInitData();
      await fetch("/api/v1/checklist", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `tma ${initData}`,
        },
        body: JSON.stringify({
          item_name: name.trim(),
          category: newItem.category,
          quantity: 1.0,
          unit: unit,
          price_paid: price,
        }),
      });
    } catch {}
  };

  // Optimistic Delete
  const handleDelete = async (id: string) => {
    haptic("medium");
    const updated = OfflineStorage.removeItem(id);
    setItems(updated);

    try {
      const initData = getInitData();
      await fetch(`/api/v1/checklist/${id}`, {
        method: "DELETE",
        headers: {
          Authorization: `tma ${initData}`,
        },
      });
    } catch {}
  };

  // Clear completed
  const handleClearCompleted = async () => {
    haptic("heavy");
    const active = items.filter((i) => !i.is_purchased);
    setItems(active);
    OfflineStorage.saveItems(active);

    try {
      const initData = getInitData();
      await fetch("/api/v1/checklist/clear-purchased", {
        method: "POST",
        headers: { Authorization: `tma ${initData}` },
      });
    } catch {}
  };

  const filteredItems = useMemo(() => {
    return items.filter((it) => {
      if (filter === "pending") return !it.is_purchased;
      if (filter === "purchased") return it.is_purchased;
      return true;
    });
  }, [items, filter]);

  const pendingCount = useMemo(() => items.filter((i) => !i.is_purchased).length, [items]);
  const totalEstimated = useMemo(() => {
    return items
      .filter((i) => !i.is_purchased)
      .reduce((acc, i) => acc + (parseFloat(i.price_paid) || 0), 0);
  }, [items]);

  // Grouped items by aisle
  const groupedByAisle = useMemo(() => {
    const groups: Record<string, CartItem[]> = {};
    filteredItems.forEach((it) => {
      const cat = it.category || "🥫 Бакалея и специи";
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(it);
    });
    return groups;
  }, [filteredItems]);

  const tgUser = getTelegramWebApp()?.initDataUnsafe?.user;
  const currentUserId = tgUser?.id ? String(tgUser.id) : "demo";

  return (
    <div className="p-4 pb-28 space-y-4 text-white">
      {/* Top Header Card */}
      <div className="p-4 rounded-3xl bg-zinc-950 border border-white/10 flex items-center justify-between">
        <div>
          <span className="text-[10px] text-zinc-400 uppercase tracking-wider block">
            Базар Гулистана • Чек-лист
          </span>
          <div className="flex items-baseline gap-2 mt-0.5">
            <span className="text-xl font-bold font-mono">
              {totalEstimated.toLocaleString("ru-RU")}
            </span>
            <span className="text-xs text-zinc-400">сум</span>
          </div>
          <span className="text-[11px] text-zinc-400 block mt-0.5">
            Осталось купить: <b className="text-white">{pendingCount}</b> поз.
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          {/* Share Family Cart */}
          <button
            onClick={() => setIsShareModalOpen(true)}
            className="p-2.5 rounded-2xl bg-white/[0.06] border border-white/10 hover:bg-white/10 text-white transition flex items-center gap-1.5 text-xs"
            title="Поделиться с семьей"
          >
            <Users className="w-4 h-4 text-blue-400" />
          </button>

          {/* Refresh */}
          <button
            onClick={fetchItems}
            disabled={isLoading}
            className="p-2.5 rounded-2xl bg-white/[0.06] border border-white/10 hover:bg-white/10 text-white transition disabled:opacity-40"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin text-zinc-400" : ""}`} />
          </button>
        </div>
      </div>

      {/* Smart Search & Autocomplete Input */}
      <div className="relative">
        <div className="flex items-center gap-2 p-1.5 bg-zinc-950 border border-white/10 rounded-2xl focus-within:border-white/30 transition">
          <div className="pl-2.5 text-zinc-500">
            <Search className="w-4 h-4" />
          </div>
          <input
            type="text"
            value={quickText}
            onChange={(e) => setQuickText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleAddItem(quickText);
            }}
            placeholder="Что купить? (например: морковь, мясо, сыр)..."
            className="flex-1 bg-transparent text-xs text-white placeholder:text-zinc-600 focus:outline-none py-1.5"
          />
          <button
            onClick={() => handleAddItem(quickText)}
            disabled={!quickText.trim()}
            className="p-2 rounded-xl bg-white text-black font-semibold text-xs disabled:opacity-30 hover:bg-zinc-200 transition"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>

        {/* Autocomplete Dropdown (Google style) */}
        {autocompleteResults.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="absolute top-full left-0 right-0 mt-1 z-30 bg-zinc-950/95 backdrop-blur-2xl border border-white/15 rounded-2xl p-1.5 shadow-2xl space-y-1"
          >
            <div className="px-2.5 py-1 text-[10px] text-zinc-400 flex items-center justify-between border-b border-white/5">
              <span>Подсказки цен в Гулистане</span>
              <span className="text-zinc-500 font-mono">Redis Fast</span>
            </div>
            {autocompleteResults.map((r: any, idx: number) => (
              <button
                key={idx}
                onClick={() => handleAddItem(r.name, r.bazaar_price || r.price, r.unit, r.category)}
                className="w-full px-3 py-2 rounded-xl hover:bg-white/[0.08] text-left flex items-center justify-between transition group"
              >
                <div>
                  <div className="text-xs font-medium text-white group-hover:text-white">
                    {r.name}
                  </div>
                  <div className="text-[10px] text-zinc-400">{r.category}</div>
                </div>
                <div className="text-right">
                  <div className="text-xs font-mono font-semibold text-emerald-400">
                    ~{(r.bazaar_price || r.price).toLocaleString("ru-RU")} сум
                  </div>
                  <div className="text-[9px] text-zinc-500">за {r.unit}</div>
                </div>
              </button>
            ))}
          </motion.div>
        )}
      </div>

      {/* Filter Chips & Aisle Toggle */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex gap-1 bg-white/[0.04] p-1 rounded-xl border border-white/10">
          <button
            onClick={() => setFilter("all")}
            className={`px-3 py-1 rounded-lg text-[11px] font-medium transition ${
              filter === "all" ? "bg-white text-black" : "text-zinc-400 hover:text-white"
            }`}
          >
            Все ({items.length})
          </button>
          <button
            onClick={() => setFilter("pending")}
            className={`px-3 py-1 rounded-lg text-[11px] font-medium transition ${
              filter === "pending" ? "bg-white text-black" : "text-zinc-400 hover:text-white"
            }`}
          >
            Нужно ({pendingCount})
          </button>
          <button
            onClick={() => setFilter("purchased")}
            className={`px-3 py-1 rounded-lg text-[11px] font-medium transition ${
              filter === "purchased" ? "bg-white text-black" : "text-zinc-400 hover:text-white"
            }`}
          >
            Куплено
          </button>
        </div>

        <button
          onClick={() => setGroupByAisle(!groupByAisle)}
          className={`px-2.5 py-1.5 rounded-xl border text-[11px] font-medium flex items-center gap-1 transition ${
            groupByAisle
              ? "bg-white/10 border-white/20 text-white"
              : "border-white/10 text-zinc-400 hover:text-white"
          }`}
        >
          <Tag className="w-3 h-3" />
          <span>{groupByAisle ? "По рядам" : "Списком"}</span>
        </button>
      </div>

      {/* Items List */}
      {filteredItems.length === 0 ? (
        <div className="p-8 text-center text-zinc-500 rounded-3xl border border-dashed border-white/10 space-y-2">
          <ShoppingBag className="w-8 h-8 mx-auto opacity-40 text-zinc-400" />
          <p className="text-xs">В этом списке пока ничего нет</p>
        </div>
      ) : groupByAisle ? (
        /* Grouped by Bazaar Aisles */
        <div className="space-y-4">
          {Object.entries(groupedByAisle).map(([aisleName, aisleItems]) => (
            <div key={aisleName} className="space-y-1.5">
              <div className="text-xs font-semibold text-zinc-400 px-1 flex items-center justify-between">
                <span>{aisleName}</span>
                <span className="text-[10px] text-zinc-500">{aisleItems.length} поз.</span>
              </div>
              <div className="space-y-1.5">
                {aisleItems.map((item) => (
                  <ItemCard
                    key={item.id}
                    item={item}
                    onToggle={handleToggle}
                    onDelete={handleDelete}
                    onEditPrice={(name, price) => setPriceModalData({ name, price })}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* Flat List */
        <div className="space-y-1.5">
          {filteredItems.map((item) => (
            <ItemCard
              key={item.id}
              item={item}
              onToggle={handleToggle}
              onDelete={handleDelete}
              onEditPrice={(name, price) => setPriceModalData({ name, price })}
            />
          ))}
        </div>
      )}

      {/* Clear Completed button */}
      {items.some((i) => i.is_purchased) && (
        <div className="pt-2 text-center">
          <button
            onClick={handleClearCompleted}
            className="text-xs text-zinc-500 hover:text-zinc-300 transition underline underline-offset-4"
          >
            Очистить купленные товары
          </button>
        </div>
      )}

      {/* Modals */}
      <FamilyShareModal
        isOpen={isShareModalOpen}
        onClose={() => setIsShareModalOpen(false)}
        userId={currentUserId}
      />

      {priceModalData && (
        <PriceEditModal
          isOpen={true}
          onClose={() => setPriceModalData(null)}
          itemName={priceModalData.name}
          currentPrice={priceModalData.price}
          onPriceUpdated={(name, newPrice) => {
            setItems((prev) =>
              prev.map((i) => (i.item_name === name ? { ...i, price_paid: String(newPrice) } : i))
            );
            onNotify?.({
              id: String(Date.now()),
              type: "success",
              title: `Цена обновлена: ${name}`,
              subtitle: "Данные сохранены для всех жителей",
            });
          }}
        />
      )}
    </div>
  );
};

interface ItemCardProps {
  item: CartItem;
  onToggle: (id: string, is_purchased: boolean) => void;
  onDelete: (id: string) => void;
  onEditPrice: (name: string, price: number) => void;
}

const ItemCard: React.FC<ItemCardProps> = ({ item, onToggle, onDelete, onEditPrice }) => {
  const priceNum = parseFloat(item.price_paid) || 0;

  return (
    <div
      className={`p-3 rounded-2xl border transition-all flex items-center justify-between gap-3 ${
        item.is_purchased
          ? "bg-white/[0.01] border-white/5 opacity-50"
          : "bg-zinc-950 border-white/10 hover:border-white/20"
      }`}
    >
      <div className="flex items-center gap-3 min-w-0 flex-1">
        {/* Checkbox button */}
        <button
          onClick={() => onToggle(item.id, item.is_purchased)}
          className={`w-6 h-6 rounded-lg border flex items-center justify-center transition shrink-0 ${
            item.is_purchased
              ? "bg-emerald-500 border-emerald-500 text-black"
              : "border-white/30 hover:border-white/60 bg-transparent text-transparent"
          }`}
        >
          <Check className="w-3.5 h-3.5 stroke-[3]" />
        </button>

        <div className="min-w-0 flex-1">
          <span
            className={`text-xs font-medium block truncate ${
              item.is_purchased ? "line-through text-zinc-500" : "text-white"
            }`}
          >
            {item.item_name}
          </span>
          <div className="flex items-center gap-1.5 text-[10px] text-zinc-400">
            <span>
              {item.quantity} {item.unit}
            </span>
            {item.store_name && <span>• {item.store_name}</span>}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        {/* Price button (opens crowdsource edit) */}
        <button
          onClick={() => onEditPrice(item.item_name, priceNum)}
          className="text-right px-2 py-1 rounded-lg bg-white/[0.04] hover:bg-white/10 border border-white/5 transition"
          title="Нажмите, чтобы изменить цену"
        >
          <div className="text-xs font-mono font-bold text-white">
            {priceNum > 0 ? `${priceNum.toLocaleString("ru-RU")} с.` : "цена"}
          </div>
        </button>

        {/* Delete */}
        <button
          onClick={() => onDelete(item.id)}
          className="p-1.5 rounded-lg text-zinc-600 hover:text-red-400 hover:bg-white/5 transition"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
};

export default ChecklistScreen;
