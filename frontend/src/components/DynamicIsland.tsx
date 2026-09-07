import React, { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { TrendingDown, WifiOff, Users, Check } from "lucide-react";

export interface IslandNotification {
  id: string;
  type: "offline" | "family" | "success" | "error";
  title: string;
  subtitle?: string;
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
    <div className="fixed top-[max(0.625rem,env(safe-area-inset-top))] left-0 right-0 z-50 flex justify-center pointer-events-none px-4">
      <AnimatePresence>
        {notification ? (
          <motion.div
            key={notification.id}
            initial={{ scale: 0.9, opacity: 0, y: -20, filter: "blur(10px)" }}
            animate={{ scale: 1, opacity: 1, y: 0, filter: "blur(0px)" }}
            exit={{ scale: 0.9, opacity: 0, y: -20, filter: "blur(10px)" }}
            transition={{ type: "spring", stiffness: 400, damping: 25 }}
            className="pointer-events-auto max-w-sm w-full bg-white/10 backdrop-blur-3xl border border-white/20 text-white px-3.5 py-2.5 rounded-[28px] shadow-[0_8px_32px_rgba(0,0,0,0.2)] flex items-center justify-between gap-3 overflow-hidden relative"
          >
            {/* Liquid shine effect */}
            <motion.div
              animate={{ x: ["-100%", "200%"] }}
              transition={{ repeat: Infinity, duration: 2, ease: "easeInOut", repeatDelay: 3 }}
              className="absolute inset-0 w-1/2 bg-gradient-to-r from-transparent via-white/10 to-transparent -skew-x-12"
            />
            
            <div className="flex items-center gap-2.5 z-10">
              <motion.div 
                initial={{ rotate: -90, scale: 0 }}
                animate={{ rotate: 0, scale: 1 }}
                transition={{ type: "spring", stiffness: 300, damping: 20, delay: 0.1 }}
                className="w-8 h-8 rounded-full bg-white/20 backdrop-blur-md flex items-center justify-center text-white shrink-0 shadow-inner"
              >
                {notification.type === "offline" && (
                  <WifiOff className="w-4 h-4 text-amber-400" />
                )}
                {notification.type === "family" && (
                  <Users className="w-4 h-4 text-blue-400" />
                )}
                {notification.type === "success" && (
                  <Check className="w-4 h-4 text-white" />
                )}
                {notification.type === "error" && (
                  <TrendingDown className="w-4 h-4 text-red-400" />
                )}
              </motion.div>
              <div className="flex flex-col text-left">
                <motion.span 
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.15 }}
                  className="text-[13px] font-semibold tracking-tight text-white leading-tight drop-shadow-md"
                >
                  {notification.title}
                </motion.span>
                {notification.subtitle && (
                  <motion.span 
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.2 }}
                    className="text-[11px] text-zinc-300 leading-tight"
                  >
                    {notification.subtitle}
                  </motion.span>
                )}
              </div>
            </div>


          </motion.div>
        ) : (
          /* Subtle collapsed indicator */
          <motion.div
            initial={{ opacity: 0, scaleX: 0 }}
            animate={{ opacity: 0.3, scaleX: 1 }}
            transition={{ duration: 1, ease: "easeInOut", repeat: Infinity, repeatType: "mirror" }}
            className="w-16 h-1 bg-white/30 rounded-full shadow-[0_0_10px_rgba(255,255,255,0.5)]"
          />
        )}
      </AnimatePresence>
    </div>
  );
};

export default DynamicIsland;
