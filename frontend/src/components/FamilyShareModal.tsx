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

  const handleDragEnd = (_: unknown, info: { offset: { y: number }; velocity: { y: number } }) => {
    if (info.offset.y > 100 || info.velocity.y > 500) {
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
        style={{ backgroundColor: "var(--color-surface-overlay)" }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <motion.div
          initial={{ y: "100%" }}
          animate={{ y: 0 }}
          exit={{ y: "100%" }}
          drag="y"
          dragConstraints={{ top: 0 }}
          dragElastic={0.2}
          onDragEnd={handleDragEnd}
          transition={{ type: "spring", damping: 30, stiffness: 350 }}
          className="w-full max-w-md border rounded-t-3xl sm:rounded-3xl p-6 shadow-2xl"
          style={{
            backgroundColor: "var(--color-bg)",
            borderColor: "var(--color-border)",
            color: "var(--color-text)",
          }}
          onClick={(e: React.MouseEvent) => e.stopPropagation()}
        >
          {/* Drag handle */}
          <div className="flex justify-center mb-3 sm:hidden">
            <div
              className="w-9 h-1 rounded-full"
              style={{ backgroundColor: "var(--color-text-muted)" }}
            />
          </div>

          {/* Header */}
          <div
            className="flex items-center justify-between pb-4 border-b"
            style={{ borderColor: "var(--color-border)" }}
          >
            <div className="flex items-center gap-2">
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center"
                style={{ backgroundColor: "var(--color-surface)" }}
              >
                <Users className="w-4 h-4" style={{ color: "var(--color-text)" }} />
              </div>
              <h2 className="text-base font-semibold">Семейная корзина</h2>
            </div>
            <button
              onClick={onClose}
              className="p-1 rounded-full transition"
              style={{ color: "var(--color-text-tertiary)" }}
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Description */}
          <div className="py-4 space-y-3">
            <p
              className="text-xs leading-relaxed"
              style={{ color: "var(--color-text-tertiary)" }}
            >
              Отправьте эту ссылку супругу(е) или близким. Как только они перейдут по ней в Telegram, ваш список покупок станет общим: добавления и вычеркивания товаров будут видны обоим сразу.
            </p>

            {/* Link box */}
            <div
              className="p-3 rounded-xl flex items-center justify-between gap-2"
              style={{
                backgroundColor: "var(--color-surface)",
                border: "1px solid var(--color-border)",
              }}
            >
              <span
                className="text-xs font-mono truncate"
                style={{ color: "var(--color-text-secondary)" }}
              >
                {shareLink}
              </span>
              <button
                onClick={handleCopy}
                className="shrink-0 p-2 rounded-lg transition flex items-center gap-1 text-xs"
                style={{
                  backgroundColor: "var(--color-surface-elevated)",
                  color: "var(--color-text)",
                }}
              >
                {copied ? <Check className="w-3.5 h-3.5" style={{ color: "var(--color-accent)" }} /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? "Скопировано" : "Копия"}</span>
              </button>
            </div>
          </div>

          {/* Action buttons */}
          <div className="pt-2 flex flex-col gap-2">
            <button
              onClick={handleTelegramShare}
              className="w-full py-3 rounded-xl font-semibold text-xs flex items-center justify-center gap-2 transition"
              style={{
                backgroundColor: "var(--color-text)",
                color: "var(--color-bg)",
              }}
            >
              <Share2 className="w-4 h-4" />
              <span>Поделиться в Telegram</span>
            </button>
            <button
              onClick={onClose}
              className="w-full py-2.5 rounded-xl text-xs transition"
              style={{
                backgroundColor: "var(--color-surface)",
                color: "var(--color-text-tertiary)",
              }}
            >
              Закрыть
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

export default FamilyShareModal;
