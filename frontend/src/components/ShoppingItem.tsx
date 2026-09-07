/**
 * OmniCart AI — ShoppingItem
 * Single item row with swipe-to-delete and checkbox.
 * 44px minimum touch target.
 */

import React, { useRef, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { Check, Trash2 } from "lucide-react";
import type { CartItem } from "../types";

interface ShoppingItemProps {
  item: CartItem;
  onToggle: (id: string) => void;
  onDelete: (id: string) => void;
}

const SWIPE_THRESHOLD = -80;

export const ShoppingItem: React.FC<ShoppingItemProps> = ({
  item,
  onToggle,
  onDelete,
}) => {
  const [offsetX, setOffsetX] = useState(0);
  const [swiping, setSwiping] = useState(false);
  const startX = useRef(0);
  const currentX = useRef(0);

  const qty = parseFloat(item.quantity) || 1;
  const price = parseFloat(item.price_paid) || 0;
  const unitLabel = item.unit || "шт";
  const hasCustomQty = qty !== 1 || (item.unit && item.unit !== "шт");
  const qtyText = unitLabel === "шт" && qty > 1 ? `×${qty}` : `${qty} ${unitLabel}`;
  const lineTotal = price * qty;

  // ── Touch Handlers ──────────────────────────────────────────────────────

  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    startX.current = e.touches[0].clientX;
    currentX.current = startX.current;
    setSwiping(true);
  }, []);

  const handleTouchMove = useCallback((e: React.TouchEvent) => {
    if (!swiping) return;
    currentX.current = e.touches[0].clientX;
    const diff = currentX.current - startX.current;
    // Only allow left swipe, cap at -120
    setOffsetX(Math.max(Math.min(diff, 0), -120));
  }, [swiping]);

  const handleTouchEnd = useCallback(() => {
    setSwiping(false);
    if (offsetX < SWIPE_THRESHOLD) {
      onDelete(item.id);
    }
    setOffsetX(0);
  }, [offsetX, onDelete, item.id]);

  const deleteRevealed = offsetX < SWIPE_THRESHOLD / 2;

  return (
    <div className="item-wrapper" role="listitem">
      {/* Delete background */}
      <div
        className={`item-delete-bg ${deleteRevealed ? "revealed" : ""}`}
        aria-hidden="true"
      >
        <Trash2 className="w-4 h-4" />
      </div>

      {/* Main item row */}
      <motion.div
        className={`item-row ${item.is_purchased ? "purchased" : ""}`}
        style={{ x: offsetX }}
        animate={swiping ? undefined : { x: 0 }}
        transition={{ type: "spring", stiffness: 300, damping: 30 }}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
      >
        {/* Checkbox */}
        <button
          type="button"
          onClick={() => onToggle(item.id)}
          className={`item-checkbox ${item.is_purchased ? "checked" : ""}`}
          role="checkbox"
          aria-checked={item.is_purchased}
          aria-label={`${item.is_purchased ? "Снять отметку" : "Отметить"}: ${item.item_name}`}
        >
          {item.is_purchased && (
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: "spring", stiffness: 500, damping: 20 }}
            >
              <Check className="w-3 h-3 stroke-[3]" />
            </motion.div>
          )}
        </button>

        {/* Item content */}
        <div className="item-content">
          <span className={`item-name ${item.is_purchased ? "done" : ""}`}>
            {item.item_name}
          </span>
          {(hasCustomQty || lineTotal > 0) && (
            <span className="item-meta">
              {hasCustomQty && `${qty} ${unitLabel}`}
              {hasCustomQty && lineTotal > 0 && " · "}
              {lineTotal > 0 && `${lineTotal.toLocaleString("ru-RU")} сум`}
            </span>
          )}
        </div>

        {/* Quantity badge */}
        {hasCustomQty && !item.is_purchased && (
          <span className="item-qty-badge">{qtyText}</span>
        )}

        {/* Delete action button for direct click / hover */}
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onDelete(item.id);
          }}
          className="item-delete-btn"
          aria-label={`Удалить ${item.item_name}`}
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </motion.div>
    </div>
  );
};

export default ShoppingItem;
