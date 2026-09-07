/**
 * OmniCart AI — EmptyState
 * Clean, modern vector empty state with custom glowing iconography.
 */

import React from "react";
import { ShoppingBag, Sparkles, Plus } from "lucide-react";

interface EmptyStateProps {
  onAdd?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ onAdd }) => {
  return (
    <div className="empty-state" role="status">
      <div className="relative mb-4 flex items-center justify-center">
        {/* Ambient Glow */}
        <div className="absolute w-20 h-20 rounded-full bg-emerald-500/15 blur-xl pointer-events-none" />
        
        {/* Outer Icon Badge */}
        <div className="relative w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-500/20 via-teal-500/10 to-slate-800/40 border border-emerald-500/30 flex items-center justify-center shadow-lg shadow-emerald-950/40">
          <ShoppingBag className="w-8 h-8 text-emerald-400 stroke-[1.75]" />
          <div className="absolute -top-1.5 -right-1.5 w-6 h-6 rounded-full bg-emerald-500/30 border border-emerald-400/50 flex items-center justify-center">
            <Sparkles className="w-3.5 h-3.5 text-emerald-300" />
          </div>
        </div>
      </div>

      <h2 className="empty-state-title">Пока ничего нет</h2>
      <p className="empty-state-subtitle">
        Добавьте товары в список покупок,<br />указав вес, цену или количество.
      </p>

      {onAdd && (
        <button type="button" onClick={onAdd} className="empty-state-cta inline-flex items-center gap-2">
          <Plus className="w-4 h-4" />
          <span>Добавить первый товар</span>
        </button>
      )}
    </div>
  );
};

export default EmptyState;
