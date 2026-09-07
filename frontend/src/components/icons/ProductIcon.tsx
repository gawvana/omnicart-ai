/**
 * OmniCart AI — Custom Vector Icon System
 * Dedicated high-fidelity custom SVG iconography for grocery items,
 * market categories, and measurement units.
 */

import React from "react";
import {
  Beef,
  Apple,
  Milk,
  Wheat,
  Fish,
  CupSoda,
  Cake,
  Sparkles,
  ShoppingBag,
  Package,
  Box,
  Droplet,
  Scale,
  Tag,
  Coins,
} from "lucide-react";
import type { UnitType } from "../../types";

export type IconCategoryKey =
  | "meat"
  | "produce"
  | "dairy"
  | "bakery"
  | "fish"
  | "drinks"
  | "sweets"
  | "household"
  | "other";

interface CategoryStyle {
  Icon: React.ComponentType<{ className?: string }>;
  bgGradient: string;
  borderColor: string;
  iconColor: string;
  glowColor: string;
}

export const CATEGORY_STYLES: Record<IconCategoryKey, CategoryStyle> = {
  meat: {
    Icon: Beef,
    bgGradient: "from-rose-500/15 via-red-500/10 to-rose-950/20",
    borderColor: "border-rose-500/30",
    iconColor: "text-rose-400",
    glowColor: "rgba(244, 63, 94, 0.15)",
  },
  produce: {
    Icon: Apple,
    bgGradient: "from-emerald-500/15 via-teal-500/10 to-emerald-950/20",
    borderColor: "border-emerald-500/30",
    iconColor: "text-emerald-400",
    glowColor: "rgba(16, 185, 129, 0.15)",
  },
  dairy: {
    Icon: Milk,
    bgGradient: "from-sky-500/15 via-blue-500/10 to-cyan-950/20",
    borderColor: "border-sky-500/30",
    iconColor: "text-sky-300",
    glowColor: "rgba(56, 189, 248, 0.15)",
  },
  bakery: {
    Icon: Wheat,
    bgGradient: "from-amber-500/15 via-yellow-500/10 to-amber-950/20",
    borderColor: "border-amber-500/30",
    iconColor: "text-amber-400",
    glowColor: "rgba(245, 158, 11, 0.15)",
  },
  fish: {
    Icon: Fish,
    bgGradient: "from-cyan-500/15 via-teal-500/10 to-blue-950/20",
    borderColor: "border-cyan-500/30",
    iconColor: "text-cyan-400",
    glowColor: "rgba(6, 182, 212, 0.15)",
  },
  drinks: {
    Icon: CupSoda,
    bgGradient: "from-indigo-500/15 via-blue-500/10 to-indigo-950/20",
    borderColor: "border-indigo-500/30",
    iconColor: "text-indigo-300",
    glowColor: "rgba(99, 102, 241, 0.15)",
  },
  sweets: {
    Icon: Cake,
    bgGradient: "from-pink-500/15 via-fuchsia-500/10 to-purple-950/20",
    borderColor: "border-pink-500/30",
    iconColor: "text-pink-400",
    glowColor: "rgba(236, 72, 153, 0.15)",
  },
  household: {
    Icon: Sparkles,
    bgGradient: "from-purple-500/15 via-violet-500/10 to-purple-950/20",
    borderColor: "border-purple-500/30",
    iconColor: "text-purple-300",
    glowColor: "rgba(168, 85, 247, 0.15)",
  },
  other: {
    Icon: ShoppingBag,
    bgGradient: "from-slate-500/15 via-zinc-500/10 to-slate-950/20",
    borderColor: "border-slate-500/30",
    iconColor: "text-slate-300",
    glowColor: "rgba(148, 163, 184, 0.15)",
  },
};

/**
 * Detects the category key from product name and optional category string.
 */
export function resolveCategoryKey(name: string, category?: string): IconCategoryKey {
  const combined = `${name || ""} ${category || ""}`.toLowerCase();

  // Meat
  if (
    /мясо|говядин|баранин|куриц|индейк|фарш|стейк|филе|шашлык|сосиск|колбас|казы|гушт|go'sht/i.test(
      combined
    )
  ) {
    return "meat";
  }

  // Fish
  if (/рыб|лосос|семг|форел|судак|сазан|креветк|тунец/i.test(combined)) {
    return "fish";
  }

  // Dairy
  if (
    /молок|сливк|кефир|йогурт|ряженк|айран|сыр|творог|брынз|сулугуни|масло сливочн|сут|qatiq/i.test(
      combined
    )
  ) {
    return "dairy";
  }

  // Bakery
  if (
    /хлеб|батон|лаваш|булочк|выпечк|лепешк|багет|круассан|нон|буханк|самса/i.test(
      combined
    )
  ) {
    return "bakery";
  }

  // Produce (Fruits & Vegetables)
  if (
    /яблок|груш|банан|апельсин|мандарин|лимон|виноград|клубник|ягод|фрукт|абрикос|персик|черешн|вишн|арбуз|дыня|ананас|манго|помидор|томат|огур|картоф|картошк|морков|лук|чеснок|капуст|перец|зелень|укроп|петрушк|баклажан|кабачок|свекл|гриб|sabzi|kartoshka|piyoz/i.test(
      combined
    )
  ) {
    return "produce";
  }

  // Drinks
  if (
    /напиток|сок|вода|cola|pepsi|чай|кофе|минералк|лимонад|компот|пиво/i.test(
      combined
    )
  ) {
    return "drinks";
  }

  // Sweets & snacks
  if (
    /шоколад|конфет|печень|печенье|торт|пирожн|чипс|морожен|сахар|халва|мед|джем/i.test(
      combined
    )
  ) {
    return "sweets";
  }

  // Household & hygiene
  if (
    /мыло|порошок|паста|шампунь|салфет|бумага|fairy|моющее|губк|чистящ|бытов/i.test(
      combined
    )
  ) {
    return "household";
  }

  return "other";
}

interface CustomProductIconProps {
  name: string;
  category?: string;
  isPurchased?: boolean;
  size?: "sm" | "md" | "lg";
  className?: string;
}

/**
 * Custom Vector Product Icon Component
 * Renders an optimized SVG vector icon in an elegant illuminated pill badge.
 */
export const CustomProductIcon: React.FC<CustomProductIconProps> = ({
  name,
  category,
  isPurchased = false,
  size = "md",
  className = "",
}) => {
  const catKey = resolveCategoryKey(name, category);
  const style = CATEGORY_STYLES[catKey];
  const IconComponent = style.Icon;

  const sizeClasses = {
    sm: "w-7 h-7 rounded-lg text-xs",
    md: "w-8 h-8 rounded-xl text-sm",
    lg: "w-10 h-10 rounded-2xl text-base",
  }[size];

  const iconSizes = {
    sm: "w-3.5 h-3.5",
    md: "w-4 h-4",
    lg: "w-5 h-5",
  }[size];

  if (isPurchased) {
    return (
      <div
        className={`relative inline-flex items-center justify-center shrink-0 border border-slate-700/40 bg-slate-800/40 text-slate-500 opacity-60 grayscale transition-all duration-200 ${sizeClasses} ${className}`}
        aria-hidden="true"
      >
        <IconComponent className={`${iconSizes} stroke-[1.75]`} />
      </div>
    );
  }

  return (
    <div
      className={`relative inline-flex items-center justify-center shrink-0 border bg-gradient-to-br transition-all duration-200 shadow-sm ${sizeClasses} ${style.bgGradient} ${style.borderColor} ${style.iconColor} ${className}`}
      style={{
        boxShadow: `0 2px 8px -2px ${style.glowColor}`,
      }}
      aria-hidden="true"
    >
      <IconComponent className={`${iconSizes} stroke-[2] drop-shadow-sm`} />
    </div>
  );
};

interface UnitIconProps {
  unit: UnitType | string;
  className?: string;
}

/**
 * Vector icon for units of measurement
 */
export const CustomUnitIcon: React.FC<UnitIconProps> = ({ unit, className = "w-3.5 h-3.5" }) => {
  const u = (unit || "").toLowerCase();
  if (u.startsWith("кг") || u === "kg") {
    return <Scale className={className} />;
  }
  if (u.startsWith("л") || u === "l") {
    return <Droplet className={className} />;
  }
  if (u.startsWith("упак") || u.startsWith("пачк")) {
    return <Package className={className} />;
  }
  if (u.startsWith("г") || u === "g") {
    return <Tag className={className} />;
  }
  return <Box className={className} />;
};

export { Scale, Droplet, Package, Tag, Box, Coins };
