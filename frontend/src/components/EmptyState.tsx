/**
 * OmniCart AI — EmptyState
 * Clean, minimal empty state with CTA.
 */

import React from "react";

interface EmptyStateProps {
  onAdd?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ onAdd }) => {
  return (
    <div className="empty-state" role="status">
      <div className="empty-state-emoji">🛒</div>
      <h2 className="empty-state-title">Пока ничего нет</h2>
      <p className="empty-state-subtitle">
        Добавьте первый товар,<br />и список готов.
      </p>
      {onAdd && (
        <button type="button" onClick={onAdd} className="empty-state-cta">
          ✨ Добавить первый товар
        </button>
      )}
    </div>
  );
};

export default EmptyState;
