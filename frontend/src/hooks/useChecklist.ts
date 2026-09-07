/**
 * OmniCart AI — useChecklist Hook
 * Central state management for checklist items with optimistic updates,
 * offline support, undo, and category grouping.
 */

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { offlineStore, generateId } from "../storage/offlineStore";
import { processQueue } from "../storage/syncEngine";
import checklistApi from "../services/checklistApi";
import { haptic, hapticSuccess } from "../services/telegram";
import type { CartItem, SyncState, ToastData } from "../types";
import { matchCategory } from "../types";

interface UseChecklistReturn {
  items: CartItem[];
  pendingItems: CartItem[];
  purchasedItems: CartItem[];
  groupedItems: Record<string, CartItem[]>;
  pendingCount: number;
  purchasedCount: number;
  totalCost: number;
  syncState: SyncState;
  toast: ToastData | null;
  dismissToast: () => void;
  addItem: (name: string, opts?: { price?: number; quantity?: number; unit?: string; category?: string }) => void;
  toggleItem: (id: string) => void;
  deleteItem: (id: string) => void;
  undoDelete: () => void;
  clearPurchased: () => void;
  refresh: () => Promise<void>;
}

export function useChecklist(): UseChecklistReturn {
  const [items, setItems] = useState<CartItem[]>(() => offlineStore.getItems());
  const [syncState, setSyncState] = useState<SyncState>("synced");
  const [toast, setToast] = useState<ToastData | null>(null);

  // Undo state
  const undoRef = useRef<{ item: CartItem; timer: ReturnType<typeof setTimeout> } | null>(null);

  // Auto-dismiss toast
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), toast.action ? 5000 : 3000);
    return () => clearTimeout(t);
  }, [toast]);

  const showToast = useCallback((data: Omit<ToastData, "id">) => {
    setToast({ ...data, id: String(Date.now()) });
  }, []);

  const dismissToast = useCallback(() => setToast(null), []);

  // ── Background Sync ─────────────────────────────────────────────────────

  const syncQueue = useCallback(async () => {
    const queue = offlineStore.getQueue();
    if (queue.length === 0) return;

    setSyncState("syncing");
    try {
      const synced = await processQueue();
      if (synced > 0) {
        setSyncState("synced");
      } else {
        setSyncState(queue.length > 0 ? "pending" : "synced");
      }
    } catch {
      setSyncState("failed");
    }
  }, []);

  // ── Fetch & Reconcile ───────────────────────────────────────────────────

  const refresh = useCallback(async () => {
    try {
      const serverItems = await checklistApi.fetchAll();
      const reconciled = offlineStore.reconcile(serverItems);
      setItems(reconciled);
      setSyncState("synced");

      // Process any pending queue after reconciliation
      await syncQueue();
    } catch {
      // Use cache on failure
      setSyncState(navigator.onLine ? "failed" : "offline");
    }
  }, [syncQueue]);

  // Initial load: cache first, then background fetch
  useEffect(() => {
    refresh();
  }, [refresh]);

  // Network status listeners
  useEffect(() => {
    const handleOnline = () => {
      showToast({ type: "info", message: "Сеть восстановлена" });
      refresh();
    };

    const handleOffline = () => {
      setSyncState("offline");
      showToast({ type: "offline", message: "Офлайн-режим" });
    };

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, [refresh, showToast]);

  // ── Add ─────────────────────────────────────────────────────────────────

  const addItem = useCallback((
    name: string,
    opts?: { price?: number; quantity?: number; unit?: string; category?: string; hasCustomQuantity?: boolean }
  ) => {
    const trimmed = name.trim();
    if (!trimmed) return;

    haptic("light");

    const hasCustomQty = !!opts?.hasCustomQuantity && opts?.quantity !== undefined && opts.quantity > 0;

    const newItem: CartItem = {
      id: generateId(),
      item_name: trimmed,
      category: opts?.category ? matchCategory(opts.category) : "",
      quantity: hasCustomQty ? String(opts!.quantity) : "1",
      unit: hasCustomQty ? (opts?.unit || "шт") : "шт",
      price_paid: String(opts?.price ?? 0),
      currency_code: "UZS",
      is_purchased: false,
      has_custom_quantity: hasCustomQty,
      created_at: new Date().toISOString(),
    };

    const updated = offlineStore.addItem(newItem);
    setItems(updated);
    setSyncState("pending");

    showToast({ type: "success", message: `✅ ${trimmed} добавлен` });

    // Background sync
    checklistApi.create({
      item_name: trimmed,
      category: newItem.category || undefined,
      quantity: hasCustomQty ? (opts?.quantity ?? 1) : 1,
      unit: hasCustomQty ? (opts?.unit || "шт") : "шт",
      price_paid: opts?.price ?? 0,
    }).then(() => {
      offlineStore.removeMutation(
        offlineStore.getQueue().find(m => m.action === "CREATE" && m.item.id === newItem.id)?.id || ""
      );
      setSyncState("synced");
    }).catch(() => {
      setSyncState(navigator.onLine ? "failed" : "offline");
    });
  }, [showToast]);

  // ── Toggle ──────────────────────────────────────────────────────────────

  const toggleItem = useCallback((id: string) => {
    haptic("light");

    const current = items.find(i => i.id === id);
    if (!current) return;

    const updated = offlineStore.toggleItem(id);
    setItems(updated);

    const toggled = updated.find(i => i.id === id);
    if (toggled?.is_purchased) {
      hapticSuccess();
      showToast({ type: "success", message: `✓ ${toggled.item_name}` });
    }

    // Background sync
    if (toggled) {
      checklistApi.toggle(id, toggled.is_purchased).then(() => {
        offlineStore.removeMutation(
          offlineStore.getQueue().find(m => m.action === "UPDATE" && m.item.id === id)?.id || ""
        );
      }).catch(() => {});
    }
  }, [items, showToast]);

  // ── Delete (with undo) ──────────────────────────────────────────────────

  const deleteItem = useCallback((id: string) => {
    haptic("medium");

    const target = items.find(i => i.id === id);
    if (!target) return;

    // Cancel any previous undo timer
    if (undoRef.current) {
      clearTimeout(undoRef.current.timer);
    }

    const updated = offlineStore.removeItem(id);
    setItems(updated);

    // Set up undo with timer
    const timer = setTimeout(() => {
      undoRef.current = null;
      // Actually sync the delete
      checklistApi.remove(id).then(() => {
        offlineStore.removeMutation(
          offlineStore.getQueue().find(m => m.action === "DELETE" && m.item.id === id)?.id || ""
        );
      }).catch(() => {});
    }, 5000);

    undoRef.current = { item: target, timer };

    showToast({
      type: "info",
      message: `${target.item_name} удалён`,
      action: {
        label: "Отменить",
        onClick: () => {
          // Will be called by undoDelete
        },
      },
    });
  }, [items, showToast]);

  const undoDelete = useCallback(() => {
    if (!undoRef.current) return;

    clearTimeout(undoRef.current.timer);
    const restored = undoRef.current.item;
    undoRef.current = null;

    // Remove the DELETE mutation from queue
    const queue = offlineStore.getQueue();
    const deleteMut = queue.find(m => m.action === "DELETE" && m.item.id === restored.id);
    if (deleteMut) {
      offlineStore.removeMutation(deleteMut.id);
    }

    // Re-add the item
    const state = offlineStore.getItems();
    state.unshift(restored);
    offlineStore.saveItems(state);
    setItems([...state]);

    haptic("light");
    showToast({ type: "success", message: `${restored.item_name} восстановлен` });
  }, [showToast]);

  // ── Clear Purchased ─────────────────────────────────────────────────────

  const clearPurchased = useCallback(() => {
    haptic("medium");
    const active = items.filter(i => !i.is_purchased);
    setItems(active);
    offlineStore.saveItems(active);

    showToast({ type: "info", message: "Купленные товары очищены" });

    checklistApi.clearPurchased().catch(() => {});
  }, [items, showToast]);

  // ── Computed ────────────────────────────────────────────────────────────

  const pendingItems = useMemo(() => items.filter(i => !i.is_purchased), [items]);
  const purchasedItems = useMemo(() => items.filter(i => i.is_purchased), [items]);

  const pendingCount = pendingItems.length;
  const purchasedCount = purchasedItems.length;

  const totalCost = useMemo(() =>
    items.reduce((sum, i) => {
      const price = parseFloat(i.price_paid) || 0;
      const qty = parseFloat(i.quantity) || 1;
      const hasQty = i.has_custom_quantity ?? (qty !== 1);
      const itemCost = hasQty ? price * qty : price;
      return sum + itemCost;
    }, 0),
  [items]);

  const groupedItems = useMemo(() => {
    const groups: Record<string, CartItem[]> = {};
    for (const item of pendingItems) {
      const cat = item.category || "📦 Другое";
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(item);
    }
    return groups;
  }, [pendingItems]);

  return {
    items,
    pendingItems,
    purchasedItems,
    groupedItems,
    pendingCount,
    purchasedCount,
    totalCost,
    syncState,
    toast,
    dismissToast,
    addItem,
    toggleItem,
    deleteItem,
    undoDelete,
    clearPurchased,
    refresh,
  };
}

export default useChecklist;
