import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, TrendingUp, Check } from "lucide-react";

interface PriceEditModalProps {
  isOpen: boolean;
  onClose: () => void;
  itemName: string;
  currentPrice: number;
  onPriceUpdated: (name: string, newPrice: number) => void;
}

export const PriceEditModal: React.FC<PriceEditModalProps> = ({
  isOpen,
  onClose,
  itemName,
  currentPrice,
  onPriceUpdated,
}) => {
  const [price, setPrice] = useState<string>(currentPrice > 0 ? String(currentPrice) : "");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const num = parseFloat(price);
    if (isNaN(num) || num <= 0) return;

    setLoading(true);
    try {
      await fetch("/api/v1/market/report-price", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ item_name: itemName, price: num }),
      });
      onPriceUpdated(itemName, num);
      try {
        (window as any).Telegram?.WebApp?.HapticFeedback?.notificationOccurred("success");
      } catch {}
      onClose();
    } catch (err) {
      console.error("Report price error:", err);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/80 backdrop-blur-md">
        <motion.div
          initial={{ y: "100%" }}
          animate={{ y: 0 }}
          exit={{ y: "100%" }}
          transition={{ type: "spring", damping: 30, stiffness: 350 }}
          className="w-full max-w-md bg-zinc-950 border border-white/10 rounded-t-3xl sm:rounded-3xl p-6 text-white shadow-2xl"
        >
          {/* Header */}
          <div className="flex items-center justify-between pb-4 border-b border-white/10">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center">
                <TrendingUp className="w-4 h-4 text-emerald-400" />
              </div>
              <div>
                <h2 className="text-base font-semibold">Уточнить цену</h2>
                <p className="text-[11px] text-zinc-400">Рыночный краудсорсинг Гулистана</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1 rounded-full text-zinc-400 hover:text-white transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="py-4 space-y-4">
            <div>
              <label className="text-xs text-zinc-400 block mb-1">Товар</label>
              <div className="p-3 bg-white/[0.04] border border-white/10 rounded-xl text-sm font-medium text-white">
                {itemName}
              </div>
            </div>

            <div>
              <label className="text-xs text-zinc-400 block mb-1">Фактическая цена на базаре (сум)</label>
              <input
                type="number"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                placeholder="Например, 15000"
                className="w-full p-3 bg-white/[0.06] border border-white/15 rounded-xl text-white font-mono placeholder:text-zinc-600 focus:outline-none focus:border-white/30"
                autoFocus
              />
            </div>

            <div className="pt-2 flex flex-col gap-2">
              <button
                type="submit"
                disabled={loading || !price}
                className="w-full py-3 rounded-xl bg-white text-black font-semibold text-xs flex items-center justify-center gap-2 hover:bg-zinc-200 transition disabled:opacity-40"
              >
                <Check className="w-4 h-4" />
                <span>{loading ? "Сохраняю..." : "Обновить цену для города"}</span>
              </button>
            </div>
          </form>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};

export default PriceEditModal;
