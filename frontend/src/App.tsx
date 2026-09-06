import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ShoppingBag,
  Store,
  WifiOff,
} from "lucide-react";

import ChecklistScreen from "./screens/ChecklistScreen";
import GulistonMarketScreen from "./screens/GulistonMarketScreen";
import DynamicIsland, { IslandNotification } from "./components/DynamicIsland";
import { OfflineStorage } from "./utils/offlineStorage";

type TabType = "checklist" | "market";

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>("checklist");
  const [notification, setNotification] = useState<IslandNotification | null>(null);
  const [isOnline, setIsOnline] = useState(navigator.onLine);

  useEffect(() => {
    const tg = (window as any).Telegram?.WebApp;
    if (tg) {
      tg.ready();
      try {
        tg.expand();
        tg.setHeaderColor?.("#000000");
        tg.setBackgroundColor?.("#000000");
      } catch (err) {
        console.warn("Telegram setup error:", err);
      }
    }

    // Network status listener
    const handleOnline = () => {
      setIsOnline(true);
      setNotification({
        id: String(Date.now()),
        type: "success",
        title: "Сеть восстановлена",
        subtitle: "Синхронизация данных с сервером",
      });
      // Flush pending offline mutations
      const queue = OfflineStorage.getQueue();
      if (queue.length > 0) {
        OfflineStorage.clearQueue();
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

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  const handleTabChange = (tab: TabType) => {
    try {
      (window as any).Telegram?.WebApp?.HapticFeedback?.impactOccurred("light");
    } catch {}
    setActiveTab(tab);
  };

  return (
    <main className="min-h-screen w-full bg-black text-white flex flex-col font-sans selection:bg-white selection:text-black">
      {/* iOS 26 Dynamic Island (Interactive top notification pill) */}
      <DynamicIsland
        notification={notification}
        onDismiss={() => setNotification(null)}
      />

      {/* Top Header */}
      <header className="sticky top-0 z-40 w-full px-4 pt-3 pb-2.5 bg-white/10 backdrop-blur-3xl border-b border-white/20 flex items-center justify-between shadow-[0_4px_30px_rgba(0,0,0,0.1)]">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-white flex items-center justify-center text-black font-black text-xs">
            O
          </div>
          <span className="text-sm font-semibold tracking-tight text-white">
            OmniCart AI
          </span>
        </div>

        {/* Status / Location pill */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/[0.06] border border-white/10 text-[11px] text-zinc-300 font-medium">
          {isOnline ? (
            <>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>Гулистан</span>
            </>
          ) : (
            <>
              <WifiOff className="w-3 h-3 text-amber-400" />
              <span className="text-amber-400">Офлайн</span>
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

      {/* iOS 26 Floating Frosted Glass Tab Bar - Liquid Glass */}
      <nav className="fixed bottom-0 left-0 right-0 z-50 px-4 pb-safe pt-2 bg-white/5 backdrop-blur-3xl border-t border-white/20 shadow-[0_-4px_30px_rgba(0,0,0,0.1)]">
        <div className="max-w-md mx-auto grid grid-cols-2 gap-1">
          {/* Tab 1: Checklist */}
          <button
            type="button"
            onClick={() => handleTabChange("checklist")}
            className={`flex flex-col items-center justify-center py-1.5 rounded-xl transition ${
              activeTab === "checklist"
                ? "text-white bg-white/[0.08]"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            <ShoppingBag className="w-5 h-5" />
            <span className="text-[10px] font-medium mt-1">Чек-лист</span>
          </button>



          {/* Tab 3: Guliston Market */}
          <button
            type="button"
            onClick={() => handleTabChange("market")}
            className={`flex flex-col items-center justify-center py-1.5 rounded-xl transition ${
              activeTab === "market"
                ? "text-white bg-white/[0.08]"
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
