/**
 * OmniCart AI — Toast Component
 * Minimal transient notification. No idle animation.
 * Replaces DynamicIsland.
 */

import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Check, WifiOff, Info, AlertCircle } from "lucide-react";
import type { ToastData } from "../types";

interface ToastProps {
  toast: ToastData | null;
  onDismiss: () => void;
  onAction?: () => void;
}

const iconMap = {
  success: <Check className="w-4 h-4" />,
  info: <Info className="w-4 h-4" />,
  error: <AlertCircle className="w-4 h-4" />,
  offline: <WifiOff className="w-4 h-4" />,
};

const colorMap = {
  success: "text-accent",
  info: "text-secondary",
  error: "text-destructive",
  offline: "text-warning",
};

export const Toast: React.FC<ToastProps> = ({ toast, onDismiss, onAction }) => {
  return (
    <div className="toast-container" aria-live="polite" aria-atomic="true">
      <AnimatePresence>
        {toast && (
          <motion.div
            key={toast.id}
            role="status"
            initial={{ opacity: 0, y: -16, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -16, scale: 0.95 }}
            transition={{ duration: 0.2, ease: [0.25, 0.46, 0.45, 0.94] }}
            onClick={onDismiss}
            className="toast-pill"
          >
            <span className={`toast-icon ${colorMap[toast.type]}`}>
              {iconMap[toast.type]}
            </span>
            <span className="toast-text">{toast.message}</span>
            {toast.action && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onAction?.();
                }}
                className="toast-action"
              >
                {toast.action.label}
              </button>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default Toast;
