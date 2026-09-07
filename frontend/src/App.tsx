/**
 * OmniCart AI — App Shell
 * Minimal header + content + toast layer.
 */

import React, { useEffect, useRef, useCallback } from "react";
import { WifiOff, Users, ShoppingCart, Receipt } from "lucide-react";

import { useChecklist } from "./hooks/useChecklist";
import { initTelegram, applyThemeColors, onThemeChange, getUserId } from "./services/telegram";

import Toast from "./components/Toast";
import AddItemInput from "./components/AddItemInput";
import ShoppingItem from "./components/ShoppingItem";
import CompletedSection from "./components/CompletedSection";
import EmptyState from "./components/EmptyState";
import FamilyShareModal from "./components/FamilyShareModal";

export const App: React.FC = () => {
  const {
    pendingItems,
    purchasedItems,
    pendingCount,
    totalCost,
    syncState,
    toast,
    dismissToast,
    addItem,
    toggleItem,
    deleteItem,
    undoDelete,
    clearPurchased,
  } = useChecklist();

  const [showShareModal, setShowShareModal] = React.useState(false);
  const addInputRef = useRef<HTMLInputElement>(null);

  // ── Telegram Init ───────────────────────────────────────────────────────

  useEffect(() => {
    initTelegram();
    applyThemeColors();
    return onThemeChange(applyThemeColors);
  }, []);

  // ── Focus add input for empty state CTA ─────────────────────────────────

  const focusAddInput = useCallback(() => {
    addInputRef.current?.focus();
  }, []);

  const totalItems = pendingItems.length + purchasedItems.length;
  const isOffline = syncState === "offline";

  return (
    <main className="app-shell">
      {/* Toast */}
      <Toast
        toast={toast}
        onDismiss={dismissToast}
        onAction={undoDelete}
      />

      {/* Header */}
      <header className="app-header">
        <div className="app-header-left">
          <h1 className="app-title flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-emerald-500 to-teal-400 p-0.5 shadow-md shadow-emerald-500/20 flex items-center justify-center shrink-0">
              <ShoppingCart className="w-4 h-4 text-white stroke-[2.5]" />
            </div>
            <span>Покупки</span>
            {pendingCount > 0 && (
              <span className="app-title-count">{pendingCount}</span>
            )}
          </h1>
        </div>

        <div className="app-header-right">
          {/* Sync / offline indicator */}
          <div className={`status-pill ${isOffline ? "offline" : ""}`}>
            {isOffline ? (
              <>
                <WifiOff className="w-3 h-3" />
                <span>Офлайн</span>
              </>
            ) : (
              <>
                <span className="status-dot" />
                <span>Онлайн</span>
              </>
            )}
          </div>

          {/* Family share */}
          <button
            type="button"
            onClick={() => setShowShareModal(true)}
            className="header-icon-btn"
            aria-label="Семейный список"
            title="Семейный список"
          >
            <Users className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Content */}
      <div className="app-content">
        {/* Add input (always visible) */}
        <AddItemInput onAdd={addItem} inputRef={addInputRef} />

        {totalItems === 0 ? (
          <EmptyState onAdd={focusAddInput} />
        ) : (
          <div className="items-list">
            {/* Pending items */}
            {pendingItems.length > 0 && (
              <div className="pending-section" role="list">
                {pendingItems.map((item) => (
                  <ShoppingItem
                    key={item.id}
                    item={item}
                    onToggle={toggleItem}
                    onDelete={deleteItem}
                  />
                ))}
              </div>
            )}

            {/* Purchased items (collapsible) */}
            <CompletedSection
              items={purchasedItems}
              onToggle={toggleItem}
              onDelete={deleteItem}
              onClear={clearPurchased}
            />
          </div>
        )}
      </div>

      {/* Sticky total bar */}
      {totalItems > 0 && (
        <div className="total-bar">
          <div className="total-bar-inner">
            <span className="total-label flex items-center gap-1.5">
              <Receipt className="w-4 h-4 text-emerald-400" />
              <span>Итого {pendingCount > 0 ? `(${pendingCount} из ${totalItems})` : `(${totalItems})`}</span>
            </span>
            <span className="total-value">
              {totalCost.toLocaleString("ru-RU")}
              <span className="total-currency"> сум</span>
            </span>
          </div>
        </div>
      )}

      {/* Family Share Modal */}
      <FamilyShareModal
        isOpen={showShareModal}
        onClose={() => setShowShareModal(false)}
        userId={getUserId()}
      />
    </main>
  );
};

export default App;
