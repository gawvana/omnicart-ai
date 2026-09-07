import React, { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ShoppingBag,
  Store,
  WifiOff,
} from "lucide-react";

import ChecklistScreen from "./screens/ChecklistScreen";
import GulistonMarketScreen from "./screens/GulistonMarketScreen";
import DynamicIsland, { IslandNotification } from "./components/DynamicIsland";
import { OfflineStorage, SyncMutation } from "./utils/offlineStorage";

type TabType = "checklist" | "market";

function getTelegramWebApp(): any {
  return (window as any).Telegram?.WebApp ?? null;
}

function getInitData(): string {
  return getTelegramWebApp()?.initData ?? "";
}

function triggerHaptic(type: "light" | "medium" | "heavy" = "light"): void {
  try {
    getTelegramWebApp()?.HapticFeedback?.impactOccurred(type);
  } catch {}
}

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>("checklist");
  const [notification, setNotification] = useState<IslandNotification | null>(null);
  const [isOnline, setIsOnline] = useState<boolean>(navigator.onLine);

  // Sync offline mutations with backend
  const syncPendingMutations = useCallback(async (queue: SyncMutation[]) => {
    if (!queue.length) return;
    const initData = getInitData();
    let syncedCount = 0;

    for (const mutation of queue) {
      try {
        if (mutation.action === "CREATE") {
          await fetch("/api/v1/checklist", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `tma ${initData}`,
            },
            body: JSON.stringify({
              item_name: mutation.item.item_name,
              category: mutation.item.category,
              quantity: parseFloat(mutation.item.quantity) || 1.0,
              unit: mutation.item.unit,
              price_paid: parseFloat(mutation.item.price_paid) || 0,
            }),
          });
          syncedCount++;
        } else if (mutation.action === "UPDATE") {
          // If ID is optimistic (opt_), skipping toggle patch to non-existent UUID on server
          if (!mutation.item.id.startsWith("opt_")) {
            await fetch(`/api/v1/checklist/${mutation.item.id}/toggle`, {
              method: "PATCH",
              headers: {
                "Content-Type": "application/json",
                Authorization: `tma ${initData}`,
              },
              body: JSON.stringify({ is_purchased: mutation.item.is_purchased }),
            });
            syncedCount++;
          }
        } else if (mutation.action === "DELETE") {
          if (!mutation.item.id.startsWith("opt_")) {
            await fetch(`/api/v1/checklist/${mutation.item.id}`, {
              method: "DELETE",
              headers: { Authorization: `tma ${initData}` },
            });
            syncedCount++;
          }
        }
      } catch (err) {
        console.warn("[App] Sync mutation failed:", err);
      }
    }

    if (syncedCount > 0) {
      setNotification({
        id: String(Date.now()),
        type: "success",
        title: "Синхронизация завершена",
        subtitle: `Обновлено ${syncedCount} изменений на сервере`,
      });
    }
  }, []);

  useEffect(() => {
    const tg = getTelegramWebApp();
    if (tg) {
      tg.ready();
      try {
        tg.expand();
        tg.setHeaderColor?.("#000000");
        tg.setBackgroundColor?.("#000000");
        tg.enableClosingConfirmation?.();
      } catch (err) {
        console.warn("[App] Telegram WebApp setup error:", err);
      }

      // Theme change handler
      const handleThemeChanged = () => {
        try {
          const isDark = tg.colorScheme === "dark";
          document.documentElement.classList.toggle("dark", isDark);
        } catch {}
      };
      tg.onEvent?.("themeChanged", handleThemeChanged);

      return () => {
        tg.offEvent?.("themeChanged", handleThemeChanged);
      };
    }
  }, []);

  useEffect(() => {
    // Network status listener & queue synchronization
    const handleOnline = async () => {
      setIsOnline(true);
      setNotification({
        id: String(Date.now()),
        type: "success",
        title: "Сеть восстановлена",
        subtitle: "Синхронизация данных с сервером...",
      });

      const queue = OfflineStorage.flushSyncQueue();
      if (queue.length > 0) {
        await syncPendingMutations(queue);
      }
    };

    const handleOffline = () => {
      setIsOnline(false);
      setNotification({
        id: String(Date.now()),
        type: "offline",
        title: "Офлайн-режим активирован",
        subtitle: "Вычеркивайте товары без интернета",
      });
    };

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    // Initial check for pending queue on startup
    if (navigator.onLine) {
      const pending = OfflineStorage.getQueue();
      if (pending.length > 0) {
        const flushed = OfflineStorage.flushSyncQueue();
        syncPendingMutations(flushed);
      }
    }

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, [syncPendingMutations]);

  const handleTabChange = (tab: TabType) => {
    triggerHaptic("light");
    setActiveTab(tab);
  };

  return (
    <main className="min-h-[100dvh] w-full bg-black text-white flex flex-col font-sans selection:bg-white selection:text-black">
      {/* iOS Dynamic Island (Interactive top notification pill) */}
      <DynamicIsland
        notification={notification}
        onDismiss={() => setNotification(null)}
      />

      {/* Top Header with Safe Area Inset */}
      <header className="sticky top-0 z-40 w-full px-4 pt-safe pb-2.5 bg-white/10 backdrop-blur-3xl border-b border-white/20 flex items-center justify-between shadow-[0_4px_30px_rgba(0,0,0,0.1)]">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-white flex items-center justify-center text-black font-black text-xs shadow-md">
            O
          </div>
          <span className="text-sm font-semibold tracking-tight text-white drop-shadow-sm">
            OmniCart AI
          </span>
        </div>

        {/* Status / Location pill */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/[0.06] border border-white/10 text-[11px] text-zinc-300 font-medium shadow-inner">
          {isOnline ? (
            <>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>Гулистан</span>
            </>
          ) : (
            <>
              <WifiOff className="w-3 h-3 text-amber-400" />
              <span className="text-amber-400 font-semibold">Офлайн</span>
            </>
          )}
        </div>
      </header>

      {/* Main Tab Content */}
      <div className="flex-1 w-full max-w-md mx-auto">
        <AnimatePresence mode="wait">
          {activeTab === "checklist" && (
            <motion.div
              key="checklist"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.15 }}
            >
              <ChecklistScreen
                onNotify={(notif) => setNotification(notif)}
              />
            </motion.div>
          )}

          {activeTab === "market" && (
            <motion.div
              key="market"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.15 }}
            >
              <GulistonMarketScreen
                onAddItem={() => {
                  setNotification({
                    id: String(Date.now()),
                    type: "success",
                    title: "Товар добавлен из цен Гулистана",
                  });
                }}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Floating Frosted Glass Tab Bar with Safe Area Bottom */}
      <nav className="fixed bottom-0 left-0 right-0 z-50 px-4 pb-safe pt-2 bg-white/5 backdrop-blur-3xl border-t border-white/20 shadow-[0_-4px_30px_rgba(0,0,0,0.1)]">
        <div className="max-w-md mx-auto grid grid-cols-2 gap-1">
          {/* Tab 1: Checklist */}
          <button
            type="button"
            onClick={() => handleTabChange("checklist")}
            className={`flex flex-col items-center justify-center py-1.5 rounded-xl transition ios-tap ${
              activeTab === "checklist"
                ? "text-white bg-white/[0.08] shadow-sm"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            <ShoppingBag className="w-5 h-5" />
            <span className="text-[10px] font-medium mt-1">Чек-лист</span>
          </button>

          {/* Tab 2: Guliston Market */}
          <button
            type="button"
            onClick={() => handleTabChange("market")}
            className={`flex flex-col items-center justify-center py-1.5 rounded-xl transition ios-tap ${
              activeTab === "market"
                ? "text-white bg-white/[0.08] shadow-sm"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            <Store className="w-5 h-5" />
            <span className="text-[10px] font-medium mt-1">Рынок Гулистан</span>
          </button>
        </div>
      </nav>
    </main>
  );
};

export default App;
