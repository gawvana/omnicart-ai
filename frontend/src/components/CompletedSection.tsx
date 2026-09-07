/**
 * OmniCart AI — CompletedSection
 * Collapsible section for purchased items.
 * Collapsed by default to keep focus on pending items.
 */

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronRight, Check } from "lucide-react";
import ShoppingItem from "./ShoppingItem";
import type { CartItem } from "../types";

interface CompletedSectionProps {
  items: CartItem[];
  onToggle: (id: string) => void;
  onDelete: (id: string) => void;
  onClear: () => void;
}

export const CompletedSection: React.FC<CompletedSectionProps> = ({
  items,
  onToggle,
  onDelete,
  onClear,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  if (items.length === 0) return null;

  return (
    <div className="completed-section">
      {/* Toggle header */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="completed-header"
        aria-expanded={isExpanded}
      >
        <div className="completed-header-left">
          <ChevronRight
            className={`w-3.5 h-3.5 transition-transform ${isExpanded ? "rotate-90" : ""}`}
          />
          <Check className="w-3.5 h-3.5 text-emerald-500" />
          <span>✨ Куплено</span>
          <span className="completed-count">{items.length}</span>
        </div>
      </button>

      {/* Expanded content */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="completed-body"
          >
            <div role="list">
              {items.map((item) => (
                <ShoppingItem
                  key={item.id}
                  item={item}
                  onToggle={onToggle}
                  onDelete={onDelete}
                />
              ))}
            </div>
            <button
              type="button"
              onClick={onClear}
              className="completed-clear-btn"
            >
              🗑️ Очистить купленное
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default CompletedSection;
