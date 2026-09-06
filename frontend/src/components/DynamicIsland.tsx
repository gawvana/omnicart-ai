import React, { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { TrendingDown, WifiOff, Users, Check } from "lucide-react";

export interface IslandNotification {
  id: string;
  type: "savings" | "offline" | "family" | "success";
  title: string;
  subtitle?: string;
  amount?: string;
}

interface DynamicIslandProps {
  notification: IslandNotification | null;
  onDismiss: () => void;
}

export const DynamicIsland: React.FC<DynamicIslandProps> = ({
  notification,
  onDismiss,
}) => {
  useEffect(() => {
    if (notification) {
      const timer = setTimeout(() => {
        onDismiss();
      }, 3500);
      return () => clearTimeout(timer);
    }
  }, [notification, onDismiss]);

  return (
    <div className="fixed top-2.5 left-0 right-0 z-50 flex justify-center pointer-events-none px-4">
      <AnimatePresence>
        {notification ? (
          <motion.div
            key={notification.id}
            initial={{ scale: 0.85, opacity: 0, y: -10 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.85, opacity: 0, y: -10 }}
            transition={{ type: "spring", stiffness: 450, damping: 28 }}
            className="pointer-events-auto max-w-sm w-full bg-black/95 backdrop-blur-3xl border border-white/20 text-white px-3.5 py-2 rounded-2xl shadow-[0_10px_35px_rgba(0,0,0,0.8)] flex items-center justify-between gap-3"
          >
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-full bg-white/10 flex items-center justify-center text-white shrink-0">
                {notification.type === "savings" && (
                  <TrendingDown className="w-4 h-4 text-emerald-400" />
                )}
                {notification.type === "offline" && (
                  <WifiOff className="w-4 h-4 text-amber-400" />
                )}
                {notification.type === "family" && (
                  <Users className="w-4 h-4 text-blue-400" />
                )}
                {notification.type === "success" && (
                  <Check className="w-4 h-4 text-white" />
                )}
              </div>
              <div className="flex flex-col text-left">
                <span className="text-xs font-semibold tracking-tight text-white leading-tight">
                  {notification.title}
                </span>
                {notification.subtitle && (
                  <span className="text-[10px] text-zinc-400 leading-tight">
                    {notification.subtitle}
                  </span>
                )}
              </div>
            </div>

            {notification.amount && (
              <span className="text-xs font-mono font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full shrink-0">
                +{notification.amount}
              </span>
            )}
          </motion.div>
        ) : (
          /* Subtle collapsed indicator */
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.6 }}
            className="w-20 h-1 bg-white/20 rounded-full"
          />
        )}
      </AnimatePresence>
    </div>
  );
};

export default DynamicIsland;
