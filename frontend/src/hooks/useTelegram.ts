/**
 * OmniCart AI — useTelegram Hook
 * Ergonomic React hook for Telegram WebApp features.
 */

import { useEffect, useState } from "react";
import {
  initTelegram,
  applyThemeColors,
  onThemeChange,
  isDarkMode,
  getUser,
  getUserId,
  haptic,
  hapticSuccess,
} from "../services/telegram";

export function useTelegram() {
  const [dark, setDark] = useState(isDarkMode);

  useEffect(() => {
    initTelegram();
    applyThemeColors();
    return onThemeChange(() => {
      applyThemeColors();
      setDark(isDarkMode());
    });
  }, []);

  return {
    user: getUser(),
    userId: getUserId(),
    isDark: dark,
    haptic,
    hapticSuccess,
  };
}

export default useTelegram;
