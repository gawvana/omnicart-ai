import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Copy, Check, Users, Share2 } from "lucide-react";
import { hapticSuccess, openTelegramLink } from "../services/telegram";

interface FamilyShareModalProps {
  isOpen: boolean;
  onClose: () => void;
  userId: string;
}

export const FamilyShareModal: React.FC<FamilyShareModalProps> = ({
  isOpen,
  onClose,
  userId,
}) => {
  const [copied, setCopied] = useState(false);
  const shareLink = `https://t.me/gusop_bot?start=cart_${userId || "demo"}`;

  const handleCopy = () => {
    navigator.clipboard.writeText(shareLink);
    setCopied(true);
    hapticSuccess();
    setTimeout(() => setCopied(false), 2000);
  };

  const handleTelegramShare = () => {
    const text = encodeURIComponent(
      "Давай вести список покупок вместе! Открой ссылку в боте OmniCart AI:\n" + shareLink
    );
    const tgUrl = `https://t.me/share/url?url=${encodeURIComponent(shareLink)}&text=${text}`;
    openTelegramLink(tgUrl);
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/80 backdrop-blur-md">
        <motion.div
          initial={{ y: "100%" }}
          animate={{ y: 0 }}
          exit={{ y: "100%" }}
          transition={{ type: "spring", damping: 30, stiffness: 350 }}
          className="w-full max-w-md bg-zinc-950 border border-white/10 rounded-t-3xl sm:rounded-3xl p-6 text-white shadow-2xl"
        >
          {/* Header */}
          <div className="flex items-center justify-between pb-4 border-b border-white/10">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center">
                <Users className="w-4 h-4 text-white" />
              </div>
              <h2 className="text-base font-semibold">Семейная корзина</h2>
            </div>
            <button
              onClick={onClose}
              className="p-1 rounded-full text-zinc-400 hover:text-white transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Description */}
          <div className="py-4 space-y-3">
            <p className="text-xs text-zinc-400 leading-relaxed">
              Отправьте эту ссылку супругу(е) или близким. Как только они перейдут по ней в Telegram, ваш список покупок станет общим: добавления и вычеркивания товаров будут видны обоим сразу.
            </p>

            {/* Link box */}
            <div className="p-3 bg-white/[0.04] border border-white/10 rounded-xl flex items-center justify-between gap-2">
              <span className="text-xs font-mono text-zinc-300 truncate">
                {shareLink}
              </span>
              <button
                onClick={handleCopy}
                className="shrink-0 p-2 rounded-lg bg-white/10 hover:bg-white/20 text-white transition flex items-center gap-1 text-xs"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? "Скопировано" : "Копия"}</span>
              </button>
            </div>
          </div>

          {/* Action buttons */}
          <div className="pt-2 flex flex-col gap-2">
            <button
              onClick={handleTelegramShare}
              className="w-full py-3 rounded-xl bg-white text-black font-semibold text-xs flex items-center justify-center gap-2 hover:bg-zinc-200 transition"
            >
              <Share2 className="w-4 h-4" />
              <span>Поделиться в Telegram</span>
            </button>
            <button
              onClick={onClose}
              className="w-full py-2.5 rounded-xl bg-white/5 text-zinc-400 text-xs hover:text-white transition"
            >
              Закрыть
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};

export default FamilyShareModal;
