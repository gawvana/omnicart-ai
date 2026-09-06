import React from "react";
import { motion, type Variants } from "framer-motion";

interface LiquidCardProps {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
  variant?: "default" | "elevated" | "inset";
  padding?: "none" | "sm" | "md" | "lg";
  animate?: boolean;
}

const paddingMap: Record<string, string> = {
  none: "",
  sm: "p-3",
  md: "p-4",
  lg: "p-6",
};

const variantStyles: Record<string, string> = {
  default: [
    "bg-white/60 dark:bg-white/[0.08]",
    "backdrop-blur-2xl",
    "border border-white/[0.18] dark:border-white/[0.12]",
    "border-t-white/25 dark:border-t-white/20",
    "shadow-[0_8px_32px_0_rgba(0,0,0,0.12)] dark:shadow-[0_8px_32px_0_rgba(0,0,0,0.37)]",
    "rounded-2xl",
  ].join(" "),
  elevated: [
    "bg-white/[0.72] dark:bg-white/[0.12]",
    "backdrop-blur-3xl",
    "border border-white/[0.22] dark:border-white/[0.15]",
    "border-t-white/30 dark:border-t-white/25",
    "shadow-[0_12px_48px_0_rgba(0,0,0,0.18)] dark:shadow-[0_12px_48px_0_rgba(0,0,0,0.45)]",
    "rounded-3xl",
  ].join(" "),
  inset: [
    "bg-black/[0.04] dark:bg-white/[0.04]",
    "backdrop-blur-xl",
    "border border-black/[0.06] dark:border-white/[0.08]",
    "rounded-xl",
    "shadow-inner",
  ].join(" "),
};

const tapVariants: Variants = {
  idle: { scale: 1 },
  tap: { scale: 0.97 },
};

const LiquidCard: React.FC<LiquidCardProps> = ({
  children,
  className = "",
  onClick,
  variant = "default",
  padding = "md",
  animate = true,
}) => {
  const baseClasses = [
    variantStyles[variant],
    paddingMap[padding],
    "relative overflow-hidden transition-colors duration-300",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  if (!animate) {
    return (
      <div className={baseClasses} onClick={onClick}>
        {/* Top specular highlight */}
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/30 to-transparent dark:via-white/20" />
        {children}
      </div>
    );
  }

  return (
    <motion.div
      className={baseClasses}
      onClick={onClick}
      variants={tapVariants}
      initial="idle"
      whileTap={onClick ? "tap" : undefined}
      whileHover={onClick ? { scale: 1.01 } : undefined}
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
    >
      {/* Top specular highlight — mimics glass refraction */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/30 to-transparent dark:via-white/20" />
      {children}
    </motion.div>
  );
};

export default LiquidCard;
