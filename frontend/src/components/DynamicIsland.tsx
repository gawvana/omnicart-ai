import React, { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";

// ── Types ───────────────────────────────────────────────────────────────────

interface CartSummary {
  totalItems: number;
  purchasedItems: number;
  totalCost: string;
  currency: string;
}

interface DynamicIslandProps {
  cart: CartSummary;
  isExpanded?: boolean;
  onToggle?: () => void;
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function getCurrencySymbol(code: string): string {
  const map: Record<string, string> = {
    USD: "$", EUR: "€", GBP: "£", JPY: "¥", KZT: "₸",
    RUB: "₽", UAH: "₴", TRY: "₺", INR: "₹", BRL: "R$",
    KRW: "₩", CNY: "¥", PLN: "zł", CZK: "Kč", THB: "฿",
  };
  return map[code] || code;
}

function formatCompactCost(cost: string, currency: string): string {
  const num = parseFloat(cost);
  if (isNaN(num)) return `${getCurrencySymbol(currency)}0`;
  const sym = getCurrencySymbol(currency);

  if (num >= 1_000_000) return `${sym}${(num / 1_000_000).toFixed(1)}M`;
  if (num >= 1_000) return `${sym}${(num / 1_000).toFixed(1)}K`;
  return `${sym}${num.toFixed(2)}`;
}

// ── Component ───────────────────────────────────────────────────────────────

const DynamicIsland: React.FC<DynamicIslandProps> = ({
  cart,
  isExpanded: controlledExpanded,
  onToggle,
}) => {
  const [internalExpanded, setInternalExpanded] = useState(false);
  const isExpanded = controlledExpanded ?? internalExpanded;

  const handleToggle = useCallback(() => {
    if (onToggle) {
      onToggle();
    } else {
      setInternalExpanded((prev) => !prev);
    }

    // Haptic feedback via Telegram WebApp SDK
    try {
      const tg = (window as any).Telegram?.WebApp;
      if (tg?.HapticFeedback) {
        tg.HapticFeedback.impactOccurred("light");
      }
    } catch {
      // Graceful degradation outside Telegram
    }
  }, [onToggle]);

  // Progress calculation
  const progress =
    cart.totalItems > 0 ? cart.purchasedItems / cart.totalItems : 0;
  const progressPercent = Math.round(progress * 100);

  // Pulse animation when all items purchased
  const isComplete = cart.totalItems > 0 && cart.purchasedItems === cart.totalItems;

  return (
    <div className="fixed top-0 left-0 right-0 z-50 flex justify-center pt-2 px-4 pointer-events-none">
      <motion.div
        className="pointer-events-auto cursor-pointer select-none"
        onClick={handleToggle}
        layout
        transition={{
          layout: { type: "spring", stiffness: 500, damping: 35 },
        }}
      >
        <motion.div
          className="relative overflow-hidden"
          animate={{
            width: isExpanded ? 340 : 200,
            height: isExpanded ? 120 : 44,
            borderRadius: isExpanded ? 28 : 22,
          }}
          transition={{
            type: "spring",
            stiffness: 500,
            damping: 35,
          }}
          style={{
            background:
              "linear-gradient(135deg, rgba(15, 15, 20, 0.92) 0%, rgba(25, 25, 35, 0.88) 100%)",
            backdropFilter: "blur(40px) saturate(1.8)",
            WebkitBackdropFilter: "blur(40px) saturate(1.8)",
            boxShadow: [
              "0 8px 32px rgba(0, 0, 0, 0.4)",
              "0 2px 8px rgba(0, 0, 0, 0.2)",
              "inset 0 1px 0 rgba(255, 255, 255, 0.08)",
              "inset 0 -1px 0 rgba(0, 0, 0, 0.2)",
            ].join(", "),
            border: "1px solid rgba(255, 255, 255, 0.08)",
          }}
        >
          {/* Specular highlight on top edge */}
          <div
            className="absolute inset-x-0 top-0 h-[1px]"
            style={{
              background:
                "linear-gradient(90deg, transparent 10%, rgba(255,255,255,0.15) 50%, transparent 90%)",
            }}
          />

          {/* Compact (pill) state */}
          <AnimatePresence mode="wait">
            {!isExpanded && (
              <motion.div
                key="compact"
                className="flex items-center justify-between h-full px-4"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
              >
                {/* Left: cart icon + item count */}
                <div className="flex items-center gap-2">
                  <motion.div
                    animate={
                      isComplete
                        ? { scale: [1, 1.2, 1] }
                        : { scale: 1 }
                    }
                    transition={{
                      repeat: isComplete ? Infinity : 0,
                      repeatDelay: 2,
                      duration: 0.6,
                    }}
                  >
                    <span className="text-base">
                      {isComplete ? "✅" : "🛒"}
                    </span>
                  </motion.div>
                  <span className="text-white/90 text-xs font-semibold tracking-wide">
                    {cart.purchasedItems}/{cart.totalItems}
                  </span>
                </div>

                {/* Center: mini progress bar */}
                <div className="flex-1 mx-3 h-[3px] rounded-full bg-white/10 overflow-hidden">
                  <motion.div
                    className="h-full rounded-full"
                    style={{
                      background: isComplete
                        ? "linear-gradient(90deg, #34D399, #10B981)"
                        : "linear-gradient(90deg, #818CF8, #6366F1)",
                    }}
                    animate={{ width: `${progressPercent}%` }}
                    transition={{ type: "spring", stiffness: 300, damping: 30 }}
                  />
                </div>

                {/* Right: total cost */}
                <span className="text-white font-bold text-sm tabular-nums">
                  {formatCompactCost(cart.totalCost, cart.currency)}
                </span>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Expanded state */}
          <AnimatePresence mode="wait">
            {isExpanded && (
              <motion.div
                key="expanded"
                className="flex flex-col h-full p-4"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
              >
                {/* Header row */}
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">
                      {isComplete ? "✅" : "🛒"}
                    </span>
                    <span className="text-white font-semibold text-sm">
                      Shopping Cart
                    </span>
                  </div>
                  <span className="text-white font-bold text-lg tabular-nums">
                    {formatCompactCost(cart.totalCost, cart.currency)}
                  </span>
                </div>

                {/* Stats row */}
                <div className="flex items-center gap-4 mb-3">
                  <div className="flex flex-col">
                    <span className="text-white/40 text-[10px] uppercase tracking-wider font-medium">
                      Items
                    </span>
                    <span className="text-white font-bold text-base tabular-nums">
                      {cart.totalItems}
                    </span>
                  </div>
                  <div className="w-px h-6 bg-white/10" />
                  <div className="flex flex-col">
                    <span className="text-white/40 text-[10px] uppercase tracking-wider font-medium">
                      Done
                    </span>
                    <span className="text-emerald-400 font-bold text-base tabular-nums">
                      {cart.purchasedItems}
                    </span>
                  </div>
                  <div className="w-px h-6 bg-white/10" />
                  <div className="flex flex-col">
                    <span className="text-white/40 text-[10px] uppercase tracking-wider font-medium">
                      Left
                    </span>
                    <span className="text-indigo-400 font-bold text-base tabular-nums">
                      {cart.totalItems - cart.purchasedItems}
                    </span>
                  </div>
                </div>

                {/* Full-width progress bar */}
                <div className="w-full h-[5px] rounded-full bg-white/10 overflow-hidden">
                  <motion.div
                    className="h-full rounded-full"
                    style={{
                      background: isComplete
                        ? "linear-gradient(90deg, #34D399, #10B981, #059669)"
                        : "linear-gradient(90deg, #818CF8, #6366F1, #4F46E5)",
                    }}
                    animate={{ width: `${progressPercent}%` }}
                    transition={{ type: "spring", stiffness: 300, damping: 30 }}
                  />
                </div>
                <div className="flex justify-end mt-1">
                  <span className="text-white/30 text-[10px] tabular-nums">
                    {progressPercent}% complete
                  </span>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </motion.div>
    </div>
  );
};

export default DynamicIsland;
