import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Check,
  Plus,
  Trash2,
  RefreshCw,
  ShoppingBag,
  Users,
  PackagePlus,
  X,
  Coins,
} from "lucide-react";
import { CartItem, OfflineStorage } from "../utils/offlineStorage";
import { IslandNotification } from "../components/DynamicIsland";
import FamilyShareModal from "../components/FamilyShareModal";

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

type UnitType = "кг" | "шт" | "л" | "упак";

const UNITS: { value: UnitType; label: string }[] = [
  { value: "кг", label: "кг" },
  { value: "шт", label: "шт" },
  { value: "л", label: "л" },
  { value: "упак", label: "упак" },
];

export const ChecklistScreen: React.FC<ChecklistScreenProps> = ({
  onNotify,
}) => {
  const [items, setItems] = useState<CartItem[]>(() => OfflineStorage.getItems());
  const [isLoading, setIsLoading] = useState(false);
  const [isShareModalOpen, setIsShareModalOpen] = useState(false);

  // Add form state
  const [showAddForm, setShowAddForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [newPrice, setNewPrice] = useState("");
  const [newQuantity, setNewQuantity] = useState("1");
  const [newUnit, setNewUnit] = useState<UnitType>("кг");

  const nameInputRef = useRef<HTMLInputElement>(null);

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

  // Focus name input when form opens
  useEffect(() => {
    if (showAddForm && nameInputRef.current) {
      setTimeout(() => nameInputRef.current?.focus(), 100);
    }
  }, [showAddForm]);

  // Optimistic Toggle
  const handleToggle = async (id: string, currentStatus: boolean) => {
    haptic("medium");
    const updated = OfflineStorage.toggleItem(id);
    setItems(updated);

    const target = updated.find((i) => i.id === id);
    if (target && target.is_purchased) {
      onNotify?.({
        id: String(Date.now()),
        type: "success",
        title: `✓ ${target.item_name}`,
        subtitle: `${target.quantity} ${target.unit}`,
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

  // Add item with full details
  const handleAddItem = async () => {
    const name = newName.trim();
    if (!name) return;

    haptic("light");

    const price = parseFloat(newPrice) || 0;
    const quantity = parseFloat(newQuantity) || 1;

    const newItem: CartItem = {
      id: "opt_" + Math.random().toString(36).substring(2, 9),
      item_name: name,
      category: "",
      quantity: String(quantity),
      unit: newUnit,
      price_paid: String(price),
      currency_code: "UZS",
      is_purchased: false,
      created_at: new Date().toISOString(),
    };

    const updated = OfflineStorage.addItem(newItem);
    setItems(updated);

    // Reset form
    setNewName("");
    setNewPrice("");
    setNewQuantity("1");
    setNewUnit("кг");

    onNotify?.({
      id: String(Date.now()),
      type: "success",
      title: `Добавлено: ${name}`,
      subtitle: price > 0 ? `${price.toLocaleString("ru-RU")} сум` : undefined,
    });

    // Sync to backend
    try {
      const initData = getInitData();
      await fetch("/api/v1/checklist", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `tma ${initData}`,
        },
        body: JSON.stringify({
          item_name: name,
          category: "",
          quantity: quantity,
          unit: newUnit,
          price_paid: price,
        }),
      });
    } catch {}

    // Keep form open for quick sequential adds, focus name input
    nameInputRef.current?.focus();
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

  // Computed values
  const pendingCount = useMemo(() => items.filter((i) => !i.is_purchased).length, [items]);
  const purchasedCount = useMemo(() => items.filter((i) => i.is_purchased).length, [items]);

  const totalCost = useMemo(() => {
    return items.reduce((acc, i) => {
      const price = parseFloat(i.price_paid) || 0;
      const qty = parseFloat(i.quantity) || 1;
      return acc + price * qty;
    }, 0);
  }, [items]);

  const pendingCost = useMemo(() => {
    return items
      .filter((i) => !i.is_purchased)
      .reduce((acc, i) => {
        const price = parseFloat(i.price_paid) || 0;
        const qty = parseFloat(i.quantity) || 1;
        return acc + price * qty;
      }, 0);
  }, [items]);

  const purchasedCost = useMemo(() => {
    return items
      .filter((i) => i.is_purchased)
      .reduce((acc, i) => {
        const price = parseFloat(i.price_paid) || 0;
        const qty = parseFloat(i.quantity) || 1;
        return acc + price * qty;
      }, 0);
  }, [items]);

  const pendingItems = useMemo(() => items.filter((i) => !i.is_purchased), [items]);
  const purchasedItems = useMemo(() => items.filter((i) => i.is_purchased), [items]);

  const tgUser = getTelegramWebApp()?.initDataUnsafe?.user;
  const currentUserId = tgUser?.id ? String(tgUser.id) : "demo";

  return (
    <div className="p-4 pb-44 space-y-4 text-white">
      {/* Header Stats */}
      <div className="p-4 rounded-3xl bg-white/[0.06] backdrop-blur-2xl border border-white/[0.08] shadow-[0_8px_32px_rgba(0,0,0,0.2)]">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-2xl bg-gradient-to-br from-white/15 to-white/5 flex items-center justify-center border border-white/10">
              <ShoppingBag className="w-4.5 h-4.5 text-white" />
            </div>
            <div>
              <span className="text-[10px] text-zinc-500 uppercase tracking-widest block font-medium">
                Список покупок
              </span>
              <span className="text-xs text-zinc-300">
                {items.length === 0
                  ? "Пусто"
                  : `${pendingCount} из ${items.length} осталось`}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setIsShareModalOpen(true)}
              className="p-2 rounded-xl bg-white/[0.06] border border-white/[0.08] hover:bg-white/[0.12] text-white transition"
              title="Поделиться"
            >
              <Users className="w-4 h-4 text-blue-400" />
            </button>
            <button
              onClick={fetchItems}
              disabled={isLoading}
              className="p-2 rounded-xl bg-white/[0.06] border border-white/[0.08] hover:bg-white/[0.12] text-white transition disabled:opacity-40"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin text-zinc-400" : ""}`} />
            </button>
          </div>
        </div>

        {/* Progress bar */}
        {items.length > 0 && (
          <div className="space-y-1.5">
            <div className="w-full h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
              <motion.div
                className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-emerald-400"
                initial={{ width: 0 }}
                animate={{
                  width: `${items.length > 0 ? (purchasedCount / items.length) * 100 : 0}%`,
                }}
                transition={{ duration: 0.4, ease: "easeOut" }}
              />
            </div>
            <div className="flex justify-between text-[10px] text-zinc-500">
              <span>Куплено: {purchasedCount}</span>
              <span>{items.length > 0 ? Math.round((purchasedCount / items.length) * 100) : 0}%</span>
            </div>
          </div>
        )}
      </div>

      {/* Add Item Button / Form */}
      <AnimatePresence mode="wait">
        {!showAddForm ? (
          <motion.button
            key="add-btn"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            onClick={() => setShowAddForm(true)}
            className="w-full p-3.5 rounded-2xl border border-dashed border-white/[0.15] bg-white/[0.03] hover:bg-white/[0.06] hover:border-white/[0.25] transition-all flex items-center justify-center gap-2 text-zinc-400 hover:text-white group"
          >
            <PackagePlus className="w-4.5 h-4.5 group-hover:scale-110 transition-transform" />
            <span className="text-xs font-medium">Добавить товар</span>
          </motion.button>
        ) : (
          <motion.div
            key="add-form"
            initial={{ opacity: 0, y: 12, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -12, scale: 0.97 }}
            transition={{ type: "spring", damping: 25, stiffness: 300 }}
            className="p-4 rounded-2xl bg-white/[0.06] backdrop-blur-xl border border-white/[0.12] space-y-3"
          >
            {/* Form header */}
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-white flex items-center gap-1.5">
                <PackagePlus className="w-3.5 h-3.5 text-zinc-400" />
                Новый товар
              </span>
              <button
                onClick={() => setShowAddForm(false)}
                className="p-1 rounded-lg text-zinc-500 hover:text-white hover:bg-white/[0.08] transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Name */}
            <div>
              <label className="text-[10px] text-zinc-500 uppercase tracking-wider block mb-1 font-medium">
                Название товара
              </label>
              <input
                ref={nameInputRef}
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleAddItem();
                }}
                placeholder="Говядина, Рис, Масло..."
                className="w-full p-2.5 rounded-xl bg-black/30 border border-white/[0.08] text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-white/25 transition"
              />
            </div>

            {/* Price & Quantity row */}
            <div className="grid grid-cols-2 gap-2.5">
              <div>
                <label className="text-[10px] text-zinc-500 uppercase tracking-wider block mb-1 font-medium">
                  Цена (сум)
                </label>
                <input
                  type="number"
                  value={newPrice}
                  onChange={(e) => setNewPrice(e.target.value)}
                  placeholder="0"
                  className="w-full p-2.5 rounded-xl bg-black/30 border border-white/[0.08] text-sm text-white font-mono placeholder:text-zinc-600 focus:outline-none focus:border-white/25 transition"
                />
              </div>
              <div>
                <label className="text-[10px] text-zinc-500 uppercase tracking-wider block mb-1 font-medium">
                  Количество
                </label>
                <input
                  type="number"
                  value={newQuantity}
                  onChange={(e) => setNewQuantity(e.target.value)}
                  placeholder="1"
                  min="0.1"
                  step="0.1"
                  className="w-full p-2.5 rounded-xl bg-black/30 border border-white/[0.08] text-sm text-white font-mono placeholder:text-zinc-600 focus:outline-none focus:border-white/25 transition"
                />
              </div>
            </div>

            {/* Unit selector */}
            <div>
              <label className="text-[10px] text-zinc-500 uppercase tracking-wider block mb-1.5 font-medium">
                Единица измерения
              </label>
              <div className="flex gap-1.5">
                {UNITS.map((u) => (
                  <button
                    key={u.value}
                    type="button"
                    onClick={() => setNewUnit(u.value)}
                    className={`flex-1 py-2 rounded-xl text-xs font-medium transition border ${
                      newUnit === u.value
                        ? "bg-white text-black border-white font-semibold shadow-md"
                        : "bg-white/[0.04] text-zinc-400 border-white/[0.08] hover:bg-white/[0.08] hover:text-white"
                    }`}
                  >
                    {u.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Submit */}
            <button
              onClick={handleAddItem}
              disabled={!newName.trim()}
              className="w-full py-2.5 rounded-xl bg-white text-black font-semibold text-xs flex items-center justify-center gap-2 hover:bg-zinc-200 active:scale-[0.98] transition disabled:opacity-30 shadow-lg"
            >
              <Plus className="w-4 h-4" />
              Добавить
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Items List */}
      {items.length === 0 ? (
        <div className="p-10 text-center text-zinc-600 rounded-3xl border border-dashed border-white/[0.06] space-y-3">
          <ShoppingBag className="w-10 h-10 mx-auto opacity-30" />
          <p className="text-xs">Список покупок пуст</p>
          <p className="text-[10px] text-zinc-700">
            Нажмите «Добавить товар» чтобы начать
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Pending items */}
          {pendingItems.length > 0 && (
            <div className="space-y-1.5">
              <div className="text-[10px] text-zinc-500 uppercase tracking-widest px-1 font-medium flex items-center justify-between">
                <span>Нужно купить ({pendingItems.length})</span>
                <span className="font-mono text-zinc-600 normal-case tracking-normal">
                  {pendingCost > 0 && `${pendingCost.toLocaleString("ru-RU")} сум`}
                </span>
              </div>
              <div className="space-y-1.5">
                {pendingItems.map((item) => (
                  <ItemCard
                    key={item.id}
                    item={item}
                    onToggle={handleToggle}
                    onDelete={handleDelete}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Purchased items */}
          {purchasedItems.length > 0 && (
            <div className="space-y-1.5">
              <div className="text-[10px] text-zinc-500 uppercase tracking-widest px-1 font-medium flex items-center justify-between">
                <span>Куплено ({purchasedItems.length})</span>
                <button
                  onClick={handleClearCompleted}
                  className="text-[10px] text-zinc-600 hover:text-red-400 normal-case tracking-normal transition underline underline-offset-2"
                >
                  Очистить
                </button>
              </div>
              <div className="space-y-1.5">
                {purchasedItems.map((item) => (
                  <ItemCard
                    key={item.id}
                    item={item}
                    onToggle={handleToggle}
                    onDelete={handleDelete}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Family Share Modal */}
      <FamilyShareModal
        isOpen={isShareModalOpen}
        onClose={() => setIsShareModalOpen(false)}
        userId={currentUserId}
      />

      {/* Sticky Total Bar */}
      {items.length > 0 && (
        <div className="fixed bottom-[60px] left-0 right-0 z-40 px-4 pb-2">
          <div className="max-w-md mx-auto">
            <motion.div
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              className="p-3.5 rounded-2xl bg-zinc-950/90 backdrop-blur-2xl border border-white/[0.1] shadow-[0_-8px_40px_rgba(0,0,0,0.5)] flex items-center justify-between"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-emerald-500/20 to-emerald-500/5 flex items-center justify-center border border-emerald-500/20">
                  <Coins className="w-4 h-4 text-emerald-400" />
                </div>
                <div>
                  <span className="text-[10px] text-zinc-500 block uppercase tracking-wider font-medium">
                    Итого
                  </span>
                  <span className="text-lg font-bold font-mono text-white leading-tight">
                    {totalCost.toLocaleString("ru-RU")}
                    <span className="text-xs text-zinc-400 font-normal ml-1">сум</span>
                  </span>
                </div>
              </div>

              <div className="text-right">
                {purchasedCost > 0 && (
                  <div className="text-[10px] text-emerald-400/80">
                    Куплено: {purchasedCost.toLocaleString("ru-RU")} с.
                  </div>
                )}
                {pendingCost > 0 && (
                  <div className="text-[10px] text-zinc-500">
                    Осталось: {pendingCost.toLocaleString("ru-RU")} с.
                  </div>
                )}
              </div>
            </motion.div>
          </div>
        </div>
      )}
    </div>
  );
};

/* ─── Item Card ─── */

interface ItemCardProps {
  item: CartItem;
  onToggle: (id: string, is_purchased: boolean) => void;
  onDelete: (id: string) => void;
}

const ItemCard: React.FC<ItemCardProps> = ({ item, onToggle, onDelete }) => {
  const priceNum = parseFloat(item.price_paid) || 0;
  const qtyNum = parseFloat(item.quantity) || 1;
  const lineTotal = priceNum * qtyNum;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className={`p-3 rounded-2xl border transition-all flex items-center justify-between gap-3 ${
        item.is_purchased
          ? "bg-white/[0.02] border-white/[0.05] opacity-45"
          : "bg-white/[0.06] border-white/[0.1] hover:bg-white/[0.1] hover:border-white/[0.15]"
      }`}
    >
      <div className="flex items-center gap-3 min-w-0 flex-1">
        {/* Checkbox */}
        <button
          onClick={() => onToggle(item.id, item.is_purchased)}
          className={`w-6 h-6 rounded-lg border-[1.5px] flex items-center justify-center transition shrink-0 ${
            item.is_purchased
              ? "bg-emerald-500 border-emerald-500 text-black"
              : "border-white/20 hover:border-white/40 bg-transparent text-transparent"
          }`}
        >
          <Check className="w-3.5 h-3.5 stroke-[3]" />
        </button>

        <div className="min-w-0 flex-1">
          <span
            className={`text-[13px] font-medium block truncate leading-tight ${
              item.is_purchased ? "line-through text-zinc-600" : "text-white"
            }`}
          >
            {item.item_name}
          </span>
          <div className="flex items-center gap-1.5 text-[10px] text-zinc-500 mt-0.5">
            <span>
              {qtyNum} {item.unit}
            </span>
            {priceNum > 0 && (
              <>
                <span>•</span>
                <span className="font-mono">{priceNum.toLocaleString("ru-RU")} сум/{item.unit}</span>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        {/* Line total */}
        {lineTotal > 0 && (
          <div className="text-right px-2 py-1 rounded-lg bg-white/[0.04]">
            <div
              className={`text-[12px] font-mono font-semibold ${
                item.is_purchased ? "text-zinc-600" : "text-white"
              }`}
            >
              {lineTotal.toLocaleString("ru-RU")}
            </div>
            <div className="text-[8px] text-zinc-600">сум</div>
          </div>
        )}

        {/* Delete */}
        <button
          onClick={() => onDelete(item.id)}
          className="p-1.5 rounded-lg text-zinc-700 hover:text-red-400 hover:bg-white/[0.04] transition"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </motion.div>
  );
};

export default ChecklistScreen;
