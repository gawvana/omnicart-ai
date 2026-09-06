import React, { useEffect } from "react";
import ChecklistScreen from "./screens/ChecklistScreen";

export const App: React.FC = () => {
  useEffect(() => {
    const tg = (window as any).Telegram?.WebApp;
    if (tg) {
      tg.ready();
      try {
        tg.expand();
      } catch (err) {
        console.warn("Telegram expand not available:", err);
      }
      try {
        tg.setHeaderColor?.("#0a0a0f");
        tg.setBackgroundColor?.("#0a0a0f");
      } catch (err) {
        console.warn("Telegram header/bg color not set:", err);
      }
    }
  }, []);

  return (
    <main className="min-h-screen w-full bg-[#0a0a0f] text-white">
      <ChecklistScreen />
    </main>
  );
};

export default App;
