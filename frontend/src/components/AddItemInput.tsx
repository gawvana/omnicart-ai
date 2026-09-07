/**
 * OmniCart AI — AddItemInput
 * Always-visible inline input with progressive disclosure for advanced fields.
 */

import React, { useState, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Plus, ChevronDown } from "lucide-react";
import { UNITS, type UnitType } from "../types";

interface AddItemInputProps {
  onAdd: (name: string, opts?: { price?: number; quantity?: number; unit?: string }) => void;
  inputRef?: React.RefObject<HTMLInputElement>;
}

export const AddItemInput: React.FC<AddItemInputProps> = ({ onAdd, inputRef: externalRef }) => {
  const [value, setValue] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [price, setPrice] = useState("");
  const [quantity, setQuantity] = useState("");
  const [unit, setUnit] = useState<UnitType>("шт");
  const localRef = useRef<HTMLInputElement>(null);
  const activeRef = externalRef || localRef;

  const handleSubmit = useCallback(() => {
    const raw = value.trim();
    if (!raw) return;

    let finalName = raw;
    let finalPrice = price ? (parseFloat(price) || 0) : undefined;
    let finalQty = quantity ? (parseFloat(quantity) || 1) : undefined;
    let finalUnit: UnitType = unit;

    // Smart natural language parsing if advanced fields are empty
    if (!price && !quantity) {
      // 1. Check for trailing price: "30000", "25 000 сум", "15000uzs"
      const priceMatch = finalName.match(/(?:^|\s)(\d[\d\s]{2,})\s*(?:сум|sum|uzs)?$/i);
      if (priceMatch && priceMatch.index !== undefined) {
        const rawP = priceMatch[1].replace(/\s+/g, "");
        const numP = parseInt(rawP, 10);
        if (!isNaN(numP) && numP >= 50) {
          finalPrice = numP;
          finalName = finalName.slice(0, priceMatch.index).trim();
        }
      }

      // 2. Check for qty and unit: "2 кг", "1.5кг", "3 шт", "1 л", "500 г", "2 упак"
      const qtyMatch = finalName.match(/(?:^|\s)(\d+(?:[.,]\d+)?)\s*(кг|шт|л|упак|г|kg|l|g)\b/i);
      if (qtyMatch && qtyMatch.index !== undefined) {
        finalQty = parseFloat(qtyMatch[1].replace(",", "."));
        const u = qtyMatch[2].toLowerCase();
        if (u === "кг" || u === "kg") finalUnit = "кг";
        else if (u === "шт") finalUnit = "шт";
        else if (u === "л" || u === "l") finalUnit = "л";
        else if (u === "упак") finalUnit = "упак";
        else if (u === "г" || u === "g") finalUnit = "г";

        finalName = (finalName.slice(0, qtyMatch.index) + " " + finalName.slice(qtyMatch.index + qtyMatch[0].length)).trim();
      }
    }

    if (!finalName) finalName = raw;

    const opts: { price?: number; quantity?: number; unit?: string } = {};
    if (finalPrice !== undefined) opts.price = finalPrice;
    if (finalQty !== undefined) opts.quantity = finalQty;
    if (finalUnit !== "шт" || finalQty !== undefined) opts.unit = finalUnit;

    onAdd(finalName, Object.keys(opts).length > 0 ? opts : undefined);

    setValue("");
    setPrice("");
    setQuantity("");
    // Keep unit for sequential adds of same type
    activeRef.current?.focus();
  }, [value, price, quantity, unit, onAdd, activeRef]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="add-input-container">
      {/* Main input row */}
      <div className="add-input-row">
        <button
          type="button"
          onClick={() => activeRef.current?.focus()}
          className="add-input-icon"
          aria-label="Добавить товар"
        >
          <Plus className="w-4 h-4" />
        </button>
        <input
          ref={activeRef}
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Добавить товар..."
          className="add-input-field"
          autoComplete="off"
          enterKeyHint="done"
        />
        {value.trim() && (
          <div className="add-input-actions">
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="add-input-expand"
              aria-label="Дополнительные параметры"
              aria-expanded={showAdvanced}
            >
              <ChevronDown
                className={`w-3.5 h-3.5 transition-transform ${showAdvanced ? "rotate-180" : ""}`}
              />
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              className="add-input-submit"
            >
              <Plus className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>

      {/* Advanced fields (progressive disclosure) */}
      <AnimatePresence>
        {showAdvanced && value.trim() && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="add-input-advanced"
          >
            <div className="add-input-advanced-grid">
              <div className="add-input-field-group">
                <label className="add-input-label">Цена</label>
                <input
                  type="number"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="0"
                  className="add-input-number"
                  inputMode="numeric"
                />
              </div>
              <div className="add-input-field-group">
                <label className="add-input-label">Кол-во</label>
                <input
                  type="number"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="1"
                  min="0.1"
                  step="0.1"
                  className="add-input-number"
                  inputMode="decimal"
                />
              </div>
            </div>
            <div className="add-input-units">
              {UNITS.map((u) => (
                <button
                  key={u.value}
                  type="button"
                  onClick={() => setUnit(u.value)}
                  className={`add-input-unit-btn ${unit === u.value ? "active" : ""}`}
                >
                  {u.label}
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default AddItemInput;
