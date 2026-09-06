import React, { useState } from "react";
import { motion } from "framer-motion";
import {
  FileText,
  Sparkles,
  CheckCheck,
  Plus,
  RefreshCw,
  Layers,
  AlertCircle,
  Check,
} from "lucide-react";

interface ParsedNoteItem {
  item_name: string;
  quantity: number;
  unit: string;
  estimated_price: number;
  is_purchased: boolean;
  category: string;
}

const COMMON_STAPLES = [
  { name: "Лепёшка тандырная", qty: "3 шт", place: "Тандыр / Янги Бозор", price: "4 000 сум" },
  { name: "Молоко пастеризованное", qty: "1 л", place: "Корзинка Гулистан", price: "13 500 сум" },
  { name: "Говядина свежая", qty: "1.5 кг", place: "Деҳқон Бозори", price: "90 000 сум" },
  { name: "Масло подсолнечное", qty: "1 л", place: "Корзинка Гулистан", price: "18 500 сум" },
  { name: "Картофель отборный", qty: "3 кг", place: "Деҳқон Бозори", price: "4 500 сум" },
  { name: "Лук репчатый", qty: "2 кг", place: "Деҳқон Бозори", price: "2 500 сум" },
];

export const XiaomiNotesScreen: React.FC<{ onImportSuccess?: () => void }> = ({
  onImportSuccess,
}) => {
  const [noteText, setNoteText] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [importStatus, setImportStatus] = useState<string | null>(null);
  const [previewItems, setPreviewItems] = useState<ParsedNoteItem[]>([]);

  const handleParsePreview = () => {
    if (!noteText.trim()) return;

    const lines = noteText.trim().split("\n");
    const parsed: ParsedNoteItem[] = [];

    for (const rawLine of lines) {
      const line = rawLine.trim();
      if (!line) continue;

      const isChecked = Boolean(line.match(/^[-*+]\s*\[[xX]\]|^\[[xX]\]/));
      const cleaned = line
        .replace(/^[-*+]\s*\[[ xX]?\]\s*|^\[[ xX]?\]\s*|^[-*•–—\d.)]\s*/, "")
        .trim();

      if (cleaned.length >= 2) {
        parsed.push({
          item_name: cleaned,
          quantity: 1,
          unit: "шт",
          estimated_price: 0,
          is_purchased: isChecked,
          category: "general",
        });
      }
    }

    setPreviewItems(parsed);
  };

  const handleImportToCart = async () => {
    if (!noteText.trim()) return;

    setIsProcessing(true);
    setImportStatus(null);

    try {
      const tg = (window as any).Telegram?.WebApp;
      const initData = tg?.initData ?? "";

      const res = await fetch("/api/v1/notes/import-xiaomi", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `tma ${initData}`,
        },
        body: JSON.stringify({ text: noteText }),
      });

      if (!res.ok) throw new Error("Не удалось импортировать");

      const data = await res.json();
      tg?.HapticFeedback?.notificationOccurred("success");
      setImportStatus(`Успешно добавлено ${data.count} товаров в ваш чек-лист!`);
      setNoteText("");
      setPreviewItems([]);

      if (onImportSuccess) {
        onImportSuccess();
      }
    } catch (err) {
      setImportStatus("Ошибка импорта. Проверьте интернет или формат списка.");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleAddStaple = async (name: string) => {
    try {
      const tg = (window as any).Telegram?.WebApp;
      const initData = tg?.initData ?? "";

      await fetch("/api/v1/checklist", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `tma ${initData}`,
        },
        body: JSON.stringify({
          item_name: name,
          quantity: 1,
          unit: "шт",
          price_paid: 0,
        }),
      });

      tg?.HapticFeedback?.impactOccurred("light");
      if (onImportSuccess) onImportSuccess();
    } catch (err) {
      console.warn("Could not add staple", err);
    }
  };

  return (
    <div className="flex flex-col gap-6 px-4 pt-4 pb-28">
      {/* Header card */}
      <div className="ios-glass-card rounded-ios-lg p-5">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center text-white">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-white tracking-tight">
              Заметки Xiaomi (Mi Notes)
            </h2>
            <p className="text-xs text-zinc-400">
              Быстрый перенос списков покупок прямо в чек-лист
            </p>
          </div>
        </div>
      </div>

      {/* Input Form */}
      <div className="ios-glass-card rounded-ios-lg p-5 flex flex-col gap-3">
        <label className="text-xs font-medium text-zinc-300 flex items-center justify-between">
          <span>Вставьте текст из заметки</span>
          <span className="text-zinc-500 font-normal">Поддерживает чек-листы и списки</span>
        </label>

        <textarea
          rows={6}
          value={noteText}
          onChange={(e) => {
            setNoteText(e.target.value);
            setImportStatus(null);
          }}
          placeholder={"Пример из Заметок Xiaomi:\n- [ ] Говядина 1.5кг на базаре\n- [ ] Молоко 2л в Корзинке\n- [ ] Лук 2кг по 2500 сум\n- [x] Хлеб тандырный"}
          className="w-full rounded-xl bg-black/60 border border-white/10 p-3.5 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-white/30 resize-none font-mono leading-relaxed"
        />

        <div className="flex gap-2.5 pt-1">
          <button
            type="button"
            onClick={handleParsePreview}
            disabled={!noteText.trim() || isProcessing}
            className="flex-1 py-3 px-4 rounded-xl bg-zinc-800 hover:bg-zinc-700 active:scale-98 transition text-xs font-medium text-zinc-200 flex items-center justify-center gap-2 border border-white/5 disabled:opacity-40"
          >
            <Layers className="w-4 h-4" />
            Разобрать
          </button>

          <button
            type="button"
            onClick={handleImportToCart}
            disabled={!noteText.trim() || isProcessing}
            className="flex-1 py-3 px-4 rounded-xl bg-white text-black hover:bg-zinc-200 active:scale-98 transition text-xs font-semibold flex items-center justify-center gap-2 disabled:opacity-40 shadow-sm"
          >
            {isProcessing ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <CheckCheck className="w-4 h-4" />
            )}
            Импортировать
          </button>
        </div>

        {importStatus && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            className={`p-3 rounded-xl text-xs flex items-center gap-2.5 border ${
              importStatus.includes("Успешно")
                ? "bg-white/5 text-zinc-200 border-white/20"
                : "bg-red-500/10 text-red-300 border-red-500/20"
            }`}
          >
            {importStatus.includes("Успешно") ? (
              <Check className="w-4 h-4 text-white" />
            ) : (
              <AlertCircle className="w-4 h-4 text-red-400" />
            )}
            <span>{importStatus}</span>
          </motion.div>
        )}
      </div>

      {/* Preview Section */}
      {previewItems.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="ios-glass-card rounded-ios-lg p-5"
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
              Найдено позиций ({previewItems.length})
            </span>
            <span className="text-[11px] text-zinc-500">Готово к переносу</span>
          </div>

          <div className="space-y-2">
            {previewItems.map((item, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between p-2.5 rounded-lg bg-white/[0.03] border border-white/5 text-xs"
              >
                <div className="flex items-center gap-2">
                  <div
                    className={`w-4 h-4 rounded flex items-center justify-center border ${
                      item.is_purchased
                        ? "bg-white text-black border-white"
                        : "border-zinc-600 bg-transparent"
                    }`}
                  >
                    {item.is_purchased && <Check className="w-3 h-3 stroke-[3]" />}
                  </div>
                  <span
                    className={`font-medium ${
                      item.is_purchased ? "text-zinc-500 line-through" : "text-white"
                    }`}
                  >
                    {item.item_name}
                  </span>
                </div>
                <span className="text-zinc-500 font-mono">
                  {item.is_purchased ? "Куплено" : "В список"}
                </span>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Regular Staples (Часто покупаемые товары для дома) */}
      <div className="ios-glass-card rounded-ios-lg p-5">
        <div className="flex items-center justify-between mb-3.5">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-white" />
            <h3 className="text-sm font-semibold text-white tracking-tight">
              Регулярные товары (Гулистан)
            </h3>
          </div>
          <span className="text-[11px] text-zinc-500">В 1 клик</span>
        </div>

        <div className="grid grid-cols-1 gap-2.5">
          {COMMON_STAPLES.map((staple, idx) => (
            <div
              key={idx}
              className="flex items-center justify-between p-3 rounded-xl bg-white/[0.03] border border-white/5 hover:border-white/10 transition"
            >
              <div>
                <div className="text-xs font-medium text-white">{staple.name}</div>
                <div className="text-[11px] text-zinc-500 flex items-center gap-1.5 mt-0.5">
                  <span>{staple.qty}</span>
                  <span>•</span>
                  <span>{staple.place}</span>
                  <span>•</span>
                  <span className="text-zinc-400">{staple.price}</span>
                </div>
              </div>

              <button
                type="button"
                onClick={() => handleAddStaple(`${staple.name} (${staple.qty})`)}
                className="w-8 h-8 rounded-lg bg-white/10 hover:bg-white text-white hover:text-black flex items-center justify-center transition active:scale-95"
                title="Добавить в чек-лист"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default XiaomiNotesScreen;
