import React, { useState } from "react";
import { motion } from "framer-motion";
import { Sparkles, Utensils, Plus, Check, Users, ChefHat } from "lucide-react";
import { CartItem, OfflineStorage } from "../utils/offlineStorage";

interface RecipeScreenProps {
  onIngredientsAdded: (count: number) => void;
}

interface IngredientItem {
  name: string;
  qty: number;
  unit: string;
  category: string;
  estimated_price: number;
}

const PRESET_RECIPES = [
  {
    name: "Чайханский плов",
    servings: 6,
    text: "Плов на 6 человек: говядина 1.2кг, рис лазер 1.2кг, морковь желтая 1.2кг, масло хлопковое 350мл, лук репчатый 350г, нут 150г, чеснок 2 головки, зира 20г.",
  },
  {
    name: "Шурпа по-сырдарьински",
    servings: 4,
    text: "Шурпа на 4 человека: баранина на кости 1кг, картофель крупный 600г, лук 300г, морковь 300г, помидоры 2 шт, болгарский перец 2 шт, зелень ассорти 1 пучок.",
  },
  {
    name: "Манты с мясом и тыквой",
    servings: 4,
    text: "Манты на 4 человека: говядина 600г, тыква сладкая 400г, курдюк 150г, лук 500г, мука 1 сорт 500г, яйцо 1 шт, зира и черный перец.",
  },
];

export const RecipeScreen: React.FC<RecipeScreenProps> = ({ onIngredientsAdded }) => {
  const [recipeText, setRecipeText] = useState("");
  const [servings, setServings] = useState(6);
  const [loading, setLoading] = useState(false);
  const [parsedItems, setParsedItems] = useState<IngredientItem[]>([]);
  const [added, setAdded] = useState(false);

  const handleParse = async (textToParse: string, count: number) => {
    if (!textToParse.trim()) return;
    setLoading(true);
    setAdded(false);

    try {
      const resp = await fetch("/api/v1/ai/parse-recipe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ recipe: textToParse, servings: count }),
      });
      const data = await resp.json();
      if (data.items) {
        setParsedItems(data.items);
      }
      try {
        (window as any).Telegram?.WebApp?.HapticFeedback?.notificationOccurred("success");
      } catch {}
    } catch (err) {
      console.error("Parse recipe error:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleAddAllToCart = () => {
    if (!parsedItems.length) return;

    let count = 0;
    parsedItems.forEach((it) => {
      const newItem: CartItem = {
        id: "rcp_" + Math.random().toString(36).substring(2, 9),
        item_name: it.name,
        category: it.category || "🥫 Бакалея и специи",
        quantity: String(it.qty),
        unit: it.unit || "кг",
        price_paid: String(it.estimated_price || 0),
        currency_code: "UZS",
        is_purchased: false,
        created_at: new Date().toISOString(),
      };
      OfflineStorage.addItem(newItem);
      count++;
    });

    setAdded(true);
    onIngredientsAdded(count);
    try {
      (window as any).Telegram?.WebApp?.HapticFeedback?.notificationOccurred("success");
    } catch {}
  };

  return (
    <div className="p-4 pb-28 space-y-5 text-white">
      {/* Title */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold tracking-tight">Реверс рецептов</h1>
          <p className="text-xs text-zinc-400">Превращение блюда в точный список для базара</p>
        </div>
        <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center">
          <ChefHat className="w-4 h-4 text-white" />
        </div>
      </div>

      {/* Preset popular dishes */}
      <div className="space-y-2">
        <label className="text-[11px] font-medium text-zinc-400 uppercase tracking-wider">
          Популярные блюда (в 1 клик)
        </label>
        <div className="grid grid-cols-3 gap-1.5">
          {PRESET_RECIPES.map((r) => (
            <button
              key={r.name}
              onClick={() => {
                setRecipeText(r.text);
                setServings(r.servings);
                handleParse(r.text, r.servings);
              }}
              className="p-2.5 rounded-xl bg-white/[0.04] border border-white/10 hover:bg-white/[0.08] text-left transition flex flex-col justify-between"
            >
              <span className="text-[11px] font-semibold text-white line-clamp-1">{r.name}</span>
              <span className="text-[10px] text-zinc-400 mt-1">{r.servings} персон</span>
            </button>
          ))}
        </div>
      </div>

      {/* Custom recipe input card */}
      <div className="p-4 rounded-2xl bg-zinc-950 border border-white/10 space-y-3">
        <div className="flex items-center justify-between">
          <label className="text-xs font-semibold text-white flex items-center gap-1.5">
            <Utensils className="w-3.5 h-3.5 text-zinc-400" />
            <span>Текст или ссылка на рецепт</span>
          </label>

          {/* Servings counter */}
          <div className="flex items-center gap-2 bg-white/[0.06] border border-white/10 px-2 py-1 rounded-lg">
            <Users className="w-3 h-3 text-zinc-400" />
            <button
              onClick={() => setServings(Math.max(1, servings - 1))}
              className="text-xs font-bold text-zinc-300 hover:text-white px-1"
            >
              -
            </button>
            <span className="text-xs font-mono font-semibold text-white">{servings}</span>
            <button
              onClick={() => setServings(servings + 1)}
              className="text-xs font-bold text-zinc-300 hover:text-white px-1"
            >
              +
            </button>
            <span className="text-[10px] text-zinc-400">чел</span>
          </div>
        </div>

        <textarea
          value={recipeText}
          onChange={(e) => setRecipeText(e.target.value)}
          placeholder="Вставьте ссылку на YouTube или список продуктов: 'Мясо 1кг, рис 1кг, лук...'"
          rows={3}
          className="w-full p-3 bg-white/[0.03] border border-white/10 rounded-xl text-xs text-white placeholder:text-zinc-600 focus:outline-none focus:border-white/20 resize-none font-sans"
        />

        <button
          onClick={() => handleParse(recipeText, servings)}
          disabled={loading || !recipeText.trim()}
          className="w-full py-2.5 rounded-xl bg-white text-black font-semibold text-xs flex items-center justify-center gap-2 hover:bg-zinc-200 transition disabled:opacity-40"
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>{loading ? "Нейросеть считает граммовки..." : "Рассчитать ингредиенты"}</span>
        </button>
      </div>

      {/* Parsed Ingredients Output */}
      {parsedItems.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-3"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-white">
              Ингредиенты ({parsedItems.length} поз.)
            </span>
            <span className="text-xs font-mono font-semibold text-emerald-400">
              ~
              {parsedItems
                .reduce((acc, it) => acc + (it.estimated_price || 0), 0)
                .toLocaleString("ru-RU")}{" "}
              сум
            </span>
          </div>

          <div className="space-y-1.5">
            {parsedItems.map((it, idx) => (
              <div
                key={idx}
                className="p-3 bg-white/[0.03] border border-white/10 rounded-xl flex items-center justify-between"
              >
                <div>
                  <div className="text-xs font-medium text-white">{it.name}</div>
                  <div className="text-[10px] text-zinc-400">{it.category}</div>
                </div>
                <div className="text-right">
                  <div className="text-xs font-mono font-bold text-white">
                    {it.qty} {it.unit}
                  </div>
                  {it.estimated_price > 0 && (
                    <div className="text-[10px] font-mono text-zinc-400">
                      ~{it.estimated_price.toLocaleString("ru-RU")} сум
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          <button
            onClick={handleAddAllToCart}
            disabled={added}
            className={`w-full py-3 rounded-xl font-semibold text-xs flex items-center justify-center gap-2 transition ${
              added
                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                : "bg-white text-black hover:bg-zinc-200"
            }`}
          >
            {added ? (
              <>
                <Check className="w-4 h-4 text-emerald-400" />
                <span>Добавлено в чек-лист!</span>
              </>
            ) : (
              <>
                <Plus className="w-4 h-4" />
                <span>Добавить все ингредиенты в корзину</span>
              </>
            )}
          </button>
        </motion.div>
      )}
    </div>
  );
};

export default RecipeScreen;
