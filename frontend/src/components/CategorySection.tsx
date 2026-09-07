/**
 * OmniCart AI — CategorySection
 * Groups items under category emoji headers.
 */

import React from "react";
import ShoppingItem from "./ShoppingItem";
import type { CartItem } from "../types";

interface CategorySectionProps {
  category: string;
  items: CartItem[];
  onToggle: (id: string) => void;
  onDelete: (id: string) => void;
}

export const CategorySection: React.FC<CategorySectionProps> = ({
  category,
  items,
  onToggle,
  onDelete,
}) => {
  return (
    <div className="category-section" role="group" aria-label={category}>
      <div className="category-header">
        <span>{category || "📦 Другое"}</span>
        <span className="category-count">{items.length}</span>
      </div>
      <div className="category-items" role="list">
        {items.map((item) => (
          <ShoppingItem
            key={item.id}
            item={item}
            onToggle={onToggle}
            onDelete={onDelete}
          />
        ))}
      </div>
    </div>
  );
};

export default CategorySection;
