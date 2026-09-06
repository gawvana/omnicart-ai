import React, { useState } from "react";
import {
  Store,
  TrendingDown,
  Plus,
  Check,
  UtensilsCrossed,
  MapPin,
  RefreshCw,
  Search,
} from "lucide-react";

interface MarketItem {
  id: string;
  name: string;
  bazaarPrice: number;
  supermarketPrice: number;
  unit: string;
  category: "meat" | "produce" | "grocery" | "dairy";
  bestPlace: "bazaar" | "supermarket";
  note: string;
}

const GULISTON_PRICES: MarketItem[] = [
  {
    id: "1",
    name: "Говядина свежая (мякоть)",
    bazaarPrice: 90000,
    supermarketPrice: 105000,
    unit: "кг",
    category: "meat",
    bestPlace: "bazaar",
    note: "Брать утром на Деҳқон Бозори до 11:00",
  },
  {
    id: "2",
    name: "Баранина свежая",
    bazaarPrice: 95000,
    supermarketPrice: 115000,
    unit: "кг",
    category: "meat",
    bestPlace: "bazaar",
    note: "Свежий разруб на центральном рынке",
  },
  {
    id: "3",
    name: "Картофель отборный",
    bazaarPrice: 4500,
    supermarketPrice: 6200,
    unit: "кг",
    category: "produce",
    bestPlace: "bazaar",
    note: "Сетками на въезде на базар дешевле",
  },
  {
    id: "4",
    name: "Лук репчатый",
    bazaarPrice: 2500,
    supermarketPrice: 4000,
    unit: "кг",
    category: "produce",
    bestPlace: "bazaar",
    note: "Выгоднее брать от 5 кг",
  },
  {
    id: "5",
    name: "Помидоры розовые / Юсуповские",
    bazaarPrice: 12000,
    supermarketPrice: 18000,
    unit: "кг",
    category: "produce",
    bestPlace: "bazaar",
    note: "У частников с грядки ароматнее и дешевле",
  },
  {
    id: "6",
    name: "Масло подсолнечное (Олейна/Щедрое лето)",
    bazaarPrice: 20000,
    supermarketPrice: 18500,
    unit: "л",
    category: "grocery",
    bestPlace: "supermarket",
    note: "В Корзинке часто по желтым ценникам",
  },
  {
    id: "7",
    name: "Рис Лазер (хорезмский)",
    bazaarPrice: 26000,
    supermarketPrice: 32000,
    unit: "кг",
    category: "grocery",
    bestPlace: "bazaar",
    note: "Отборный рис для плова в рисовом ряду",
  },
  {
    id: "8",
    name: "Молоко Musaffo 3.2%",
    bazaarPrice: 14500,
    supermarketPrice: 13500,
    unit: "л",
    category: "dairy",
    bestPlace: "supermarket",
    note: "Ультрапастеризованное выгоднее в супермаркете",
  },
  {
    id: "9",
    name: "Яйца столовые (30 шт)",
    bazaarPrice: 38000,
    supermarketPrice: 44000,
    unit: "лоток",
    category: "dairy",
    bestPlace: "bazaar",
    note: "Оптовые лотки в глубине базара",
  },
  {
    id: "10",
    name: "Чай черный Greenfield 100 пакетиков",
    bazaarPrice: 58000,
    supermarketPrice: 52000,
    unit: "упак",
    category: "grocery",
    bestPlace: "supermarket",
    note: "Оригинальная продукция и скидки в Корзинке",
  },
];

export const GulistonMarketScreen: React.FC<{ onAddItem?: (name: string) => void }> = ({
  onAddItem,
}) => {
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [plovServings, setPlovServings] = useState<number>(6);
  const [isAddingPlov, setIsAddingPlov] = useState<boolean>(false);
  const [plovSuccess, setPlovSuccess] = useState<boolean>(false);

  const categories = [
    { id: "all", label: "Все товары" },
    { id: "meat", label: "Мясо" },
    { id: "produce", label: "Овощи" },
    { id: "grocery", label: "Бакалея" },
    { id: "dairy", label: "Молочное" },
  ];

  const filteredItems = GULISTON_PRICES.filter((item) => {
    const matchesCategory = selectedCategory === "all" || item.category === selectedCategory;
    const matchesSearch = item.name.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  // Calculate Plov recipe for Guliston
  const plovScale = plovServings / 6.0;
  const plovMeatCost = Math.round(1.0 * plovScale * 90000);
  const plovRiceCost = Math.round(1.0 * plovScale * 26000);
  const plovCarrotCost = Math.round(1.0 * plovScale * 3000);
  const plovOnionCost = Math.round(0.4 * plovScale * 2500);
  const plovOilCost = Math.round(0.3 * plovScale * 18500);
  const plovTotal = plovMeatCost + plovRiceCost + plovCarrotCost + plovOnionCost + plovOilCost;

  const handleAddAllPlov = async () => {
    setIsAddingPlov(true);
    try {
      const tg = (window as any).Telegram?.WebApp;
      const initData = tg?.initData ?? "";

      const ingredients = [
        `Говядина для плова (${(1.0 * plovScale).toFixed(1)} кг)`,
        `Рис Лазер (${(1.0 * plovScale).toFixed(1)} кг)`,
        `Морковь желтая/красная (${(1.0 * plovScale).toFixed(1)} кг)`,
        `Лук репчатый (${(0.4 * plovScale).toFixed(1)} кг)`,
        `Масло растительное (${(0.3 * plovScale).toFixed(2)} л)`,
      ];

      for (const ing of ingredients) {
        await fetch("/api/v1/checklist", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `tma ${initData}`,
          },
          body: JSON.stringify({
            item_name: ing,
            quantity: 1,
            unit: "порц",
            price_paid: 0,
          }),
        });
      }

      tg?.HapticFeedback?.notificationOccurred("success");
      setPlovSuccess(true);
      setTimeout(() => setPlovSuccess(false), 3000);
    } catch (err) {
      console.warn("Plov add error", err);
    } finally {
      setIsAddingPlov(false);
    }
  };

  const handleAddSingleItem = async (itemName: string) => {
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
          item_name: itemName,
          quantity: 1,
          unit: "шт",
          price_paid: 0,
        }),
      });

      tg?.HapticFeedback?.impactOccurred("light");
      if (onAddItem) onAddItem(itemName);
    } catch (err) {
      console.warn("Item add error", err);
    }
  };

  return (
    <div className="flex flex-col gap-6 px-4 pt-4 pb-28">
      {/* Header Overview Card */}
      <div className="ios-glass-card rounded-ios-lg p-5">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center text-white">
            <Store className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-white tracking-tight">
              Рынок Гулистана (Сырдарья)
            </h2>
            <div className="flex items-center gap-1.5 text-xs text-zinc-400">
              <MapPin className="w-3.5 h-3.5 text-zinc-500" />
              <span>Деҳқон Бозори vs Корзинка (ул. Сайхун)</span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2.5 pt-2">
          <div className="p-3 rounded-xl bg-black/40 border border-white/5">
            <div className="text-[11px] text-zinc-500 mb-0.5">Деҳқон Бозори</div>
            <div className="text-xs font-semibold text-white">Мясо, овощи, рис</div>
            <div className="text-[10px] text-zinc-400 mt-1">Дешевле до 25%</div>
          </div>

          <div className="p-3 rounded-xl bg-black/40 border border-white/5">
            <div className="text-[11px] text-zinc-500 mb-0.5">Корзинка Гулистан</div>
            <div className="text-xs font-semibold text-white">Масла, бакалея, быт. химия</div>
            <div className="text-[10px] text-zinc-400 mt-1">Акции недели</div>
          </div>
        </div>
      </div>

      {/* Plov Calculator Card */}
      <div className="ios-glass-card rounded-ios-lg p-5">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <UtensilsCrossed className="w-4 h-4 text-white" />
            <h3 className="text-sm font-semibold text-white tracking-tight">
              Калькулятор плова (Гулистан)
            </h3>
          </div>
          <span className="text-xs font-mono text-zinc-400">
            {plovServings} персон
          </span>
        </div>

        <div className="mb-4">
          <div className="flex justify-between text-xs text-zinc-400 mb-1.5">
            <span>Количество порций:</span>
            <span className="font-semibold text-white">{plovServings} человек</span>
          </div>
          <input
            type="range"
            min={4}
            max={20}
            step={2}
            value={plovServings}
            onChange={(e) => setPlovServings(Number(e.target.value))}
            className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-white"
          />
        </div>

        <div className="space-y-1.5 p-3 rounded-xl bg-black/40 border border-white/5 text-xs mb-3.5">
          <div className="flex justify-between text-zinc-300">
            <span>Мясо говядина ({(1.0 * plovScale).toFixed(1)} кг):</span>
            <span className="font-mono text-white">{plovMeatCost.toLocaleString()} сум</span>
          </div>
          <div className="flex justify-between text-zinc-300">
            <span>Рис Лазер ({(1.0 * plovScale).toFixed(1)} кг):</span>
            <span className="font-mono text-white">{plovRiceCost.toLocaleString()} сум</span>
          </div>
          <div className="flex justify-between text-zinc-300">
            <span>Морковь + Лук (базар):</span>
            <span className="font-mono text-white">{(plovCarrotCost + plovOnionCost).toLocaleString()} сум</span>
          </div>
          <div className="flex justify-between text-zinc-300">
            <span>Масло (Корзинка):</span>
            <span className="font-mono text-white">{plovOilCost.toLocaleString()} сум</span>
          </div>
          <div className="border-t border-white/10 pt-2 mt-1 flex justify-between font-semibold text-white">
            <span>Итого на {plovServings} чел:</span>
            <span className="font-mono text-sm">{plovTotal.toLocaleString()} сум</span>
          </div>
        </div>

        <button
          type="button"
          onClick={handleAddAllPlov}
          disabled={isAddingPlov}
          className="w-full py-2.5 px-4 rounded-xl bg-white text-black hover:bg-zinc-200 active:scale-98 transition text-xs font-semibold flex items-center justify-center gap-2 disabled:opacity-40"
        >
          {isAddingPlov ? (
            <RefreshCw className="w-4 h-4 animate-spin" />
          ) : plovSuccess ? (
            <Check className="w-4 h-4" />
          ) : (
            <Plus className="w-4 h-4" />
          )}
          {plovSuccess ? "Добавлено в чек-лист!" : "Добавить ингредиенты в чек-лист"}
        </button>
      </div>

      {/* Market Prices Explorer */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white tracking-tight">
            Сравнение цен товаров
          </h3>
          <span className="text-xs text-zinc-500">Гулистан 2026</span>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="w-4 h-4 text-zinc-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Поиск товара (мясо, картофель, масло...)"
            className="w-full pl-9 pr-4 py-2.5 rounded-xl bg-zinc-900 border border-white/10 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-white/30"
          />
        </div>

        {/* Category Pills */}
        <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
          {categories.map((cat) => (
            <button
              key={cat.id}
              type="button"
              onClick={() => setSelectedCategory(cat.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition ${
                selectedCategory === cat.id
                  ? "bg-white text-black font-semibold"
                  : "bg-white/5 text-zinc-400 hover:bg-white/10"
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* Price list */}
        <div className="space-y-2.5">
          {filteredItems.map((item) => {
            const isBazaarCheaper = item.bazaarPrice < item.supermarketPrice;
            const diff = Math.abs(item.bazaarPrice - item.supermarketPrice);

            return (
              <div
                key={item.id}
                className="ios-glass-card rounded-ios p-4 flex flex-col gap-2.5"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h4 className="text-xs font-semibold text-white">{item.name}</h4>
                    <p className="text-[11px] text-zinc-400 mt-0.5">{item.note}</p>
                  </div>

                  <button
                    type="button"
                    onClick={() => handleAddSingleItem(item.name)}
                    className="w-7 h-7 rounded-lg bg-white/10 hover:bg-white text-white hover:text-black flex items-center justify-center transition active:scale-95 shrink-0"
                    title="Добавить в чек-лист"
                  >
                    <Plus className="w-3.5 h-3.5" />
                  </button>
                </div>

                <div className="grid grid-cols-2 gap-2 pt-1">
                  <div
                    className={`p-2 rounded-lg border text-xs ${
                      isBazaarCheaper
                        ? "bg-white/10 border-white/30 text-white"
                        : "bg-black/30 border-white/5 text-zinc-400"
                    }`}
                  >
                    <div className="flex items-center justify-between text-[10px] text-zinc-400 mb-0.5">
                      <span>Деҳқон Бозори</span>
                      {isBazaarCheaper && (
                        <span className="text-white font-semibold flex items-center gap-0.5">
                          <TrendingDown className="w-2.5 h-2.5" /> Лучшая
                        </span>
                      )}
                    </div>
                    <div className="font-mono font-semibold">
                      {item.bazaarPrice.toLocaleString()} сум{" "}
                      <span className="text-[10px] font-normal text-zinc-500">/{item.unit}</span>
                    </div>
                  </div>

                  <div
                    className={`p-2 rounded-lg border text-xs ${
                      !isBazaarCheaper
                        ? "bg-white/10 border-white/30 text-white"
                        : "bg-black/30 border-white/5 text-zinc-400"
                    }`}
                  >
                    <div className="flex items-center justify-between text-[10px] text-zinc-400 mb-0.5">
                      <span>Корзинка</span>
                      {!isBazaarCheaper && (
                        <span className="text-white font-semibold flex items-center gap-0.5">
                          <TrendingDown className="w-2.5 h-2.5" /> Лучшая
                        </span>
                      )}
                    </div>
                    <div className="font-mono font-semibold">
                      {item.supermarketPrice.toLocaleString()} сум{" "}
                      <span className="text-[10px] font-normal text-zinc-500">/{item.unit}</span>
                    </div>
                  </div>
                </div>

                <div className="text-[10px] text-zinc-500 flex justify-between items-center pt-0.5">
                  <span>Разница: {diff.toLocaleString()} сум/{item.unit}</span>
                  <span className="text-zinc-400 font-medium">
                    {item.bestPlace === "bazaar" ? "Рекомендуем: Деҳқон Бозори" : "Рекомендуем: Корзинка"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default GulistonMarketScreen;
