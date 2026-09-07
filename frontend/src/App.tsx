import React, { useState, useEffect, useCallback } from "react";
import {
  WifiOff,
} from "lucide-react";

import ChecklistScreen from "./screens/ChecklistScreen";
import DynamicIsland, { IslandNotification } from "./components/DynamicIsland";
import { OfflineStorage, SyncMutation } from "./utils/offlineStorage";

function getTelegramWebApp(): any {
  return (window as any).Telegram?.WebApp ?? null;
}

function getInitData(): string {
  return getTelegramWebApp()?.initData ?? "";
}

export const App: React.FC = () => {
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

  return (
    <main className="min-h-[100dvh] w-full bg-black text-white flex flex-col font-sans selection:bg-white selection:text-black">
      {/* iOS Dynamic Island (Interactive top notification pill) */}
      <DynamicIsland
        notification={notification}
        onDismiss={() => setNotification(null)}
      />

      {/* Top Header with Safe Area Inset */}
      <header className="sticky top-0 z-40 w-full px-4 pt-safe pb-2.5 bg-black/80 backdrop-blur-2xl border-b border-white/[0.06] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-white flex items-center justify-center text-black font-black text-xs shadow-md">
            O
          </div>
          <span className="text-sm font-semibold tracking-tight text-white">
            OmniCart AI
          </span>
        </div>

        {/* Status pill */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/[0.04] border border-white/[0.06] text-[11px] text-zinc-400 font-medium">
          {isOnline ? (
            <>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>Онлайн</span>
            </>
          ) : (
            <>
              <WifiOff className="w-3 h-3 text-amber-400" />
              <span className="text-amber-400 font-semibold">Офлайн</span>
            </>
          )}
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 w-full max-w-md mx-auto">
        <ChecklistScreen
          onNotify={(notif) => setNotification(notif)}
        />
      </div>
    </main>
  );
};

export default App;
