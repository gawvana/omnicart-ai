import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ShoppingBag,
  Store,
  FileText,
} from "lucide-react";

import ChecklistScreen from "./screens/ChecklistScreen";
import GulistonMarketScreen from "./screens/GulistonMarketScreen";
import XiaomiNotesScreen from "./screens/XiaomiNotesScreen";

type TabType = "checklist" | "market" | "notes";

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>("checklist");

  useEffect(() => {
    const tg = (window as any).Telegram?.WebApp;
    if (tg) {
      tg.ready();
      try {
        tg.expand();
      } catch (err) {
        console.warn("Telegram expand not available:", err);
      }
      try {
        tg.setHeaderColor?.("#000000");
        tg.setBackgroundColor?.("#000000");
      } catch (err) {
        console.warn("Telegram header/bg color not set:", err);
      }
    }
  }, []);

  const handleTabChange = (tab: TabType) => {
    try {
      (window as any).Telegram?.WebApp?.HapticFeedback?.impactOccurred("light");
    } catch {
      // Graceful fallback
    }
    setActiveTab(tab);
  };

  return (
    <main className="min-h-screen w-full bg-black text-white flex flex-col font-sans selection:bg-white selection:text-black">
      {/* Top iOS 26 Status Bar Header */}
      <header className="sticky top-0 z-40 w-full px-4 pt-safe pb-2.5 bg-black/85 backdrop-blur-2xl border-b border-white/[0.07] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-white flex items-center justify-center text-black font-black text-xs">
            O
          </div>
          <span className="text-sm font-semibold tracking-tight text-white">
            OmniCart AI
          </span>
        </div>

        {/* Location pill */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/[0.06] border border-white/10 text-[11px] text-zinc-300 font-medium">
          <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
          <span>Гулистан</span>
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
                onOpenNotes={() => handleTabChange("notes")}
                onOpenMarket={() => handleTabChange("market")}
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
                  // stay or notify
                }}
              />
            </motion.div>
          )}

          {activeTab === "notes" && (
            <motion.div
              key="notes"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.15 }}
            >
              <XiaomiNotesScreen
                onImportSuccess={() => {
                  handleTabChange("checklist");
                }}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* iOS 26 Floating Frosted Glass Tab Bar */}
      <nav className="fixed bottom-0 left-0 right-0 z-50 px-4 pb-safe pt-2 bg-black/80 backdrop-blur-2xl border-t border-white/[0.08]">
        <div className="max-w-md mx-auto grid grid-cols-3 gap-1">
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

          {/* Tab 2: Guliston Market */}
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

          {/* Tab 3: Xiaomi Notes */}
          <button
            type="button"
            onClick={() => handleTabChange("notes")}
            className={`flex flex-col items-center justify-center py-1.5 rounded-xl transition ${
              activeTab === "notes"
                ? "text-white bg-white/[0.08]"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            <FileText className="w-5 h-5" />
            <span className="text-[10px] font-medium mt-1">Заметки Xiaomi</span>
          </button>
        </div>
      </nav>
    </main>
  );
};

export default App;
