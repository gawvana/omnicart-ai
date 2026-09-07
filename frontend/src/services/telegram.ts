/**
 * OmniCart AI — Telegram WebApp Service
 * Typed wrapper for window.Telegram.WebApp.
 * All Telegram-specific access goes through here.
 */

// ── Telegram WebApp Type Definitions ────────────────────────────────────────

interface TelegramHaptic {
  impactOccurred: (style: "light" | "medium" | "heavy" | "rigid" | "soft") => void;
  notificationOccurred: (type: "error" | "success" | "warning") => void;
  selectionChanged: () => void;
}

interface TelegramThemeParams {
  bg_color?: string;
  text_color?: string;
  hint_color?: string;
  link_color?: string;
  button_color?: string;
  button_text_color?: string;
  secondary_bg_color?: string;
  header_bg_color?: string;
  section_bg_color?: string;
  section_header_text_color?: string;
  subtitle_text_color?: string;
  destructive_text_color?: string;
}

interface TelegramMainButton {
  text: string;
  isVisible: boolean;
  isActive: boolean;
  show: () => void;
  hide: () => void;
  setText: (text: string) => void;
  onClick: (cb: () => void) => void;
  offClick: (cb: () => void) => void;
  enable: () => void;
  disable: () => void;
}

interface TelegramBackButton {
  isVisible: boolean;
  show: () => void;
  hide: () => void;
  onClick: (cb: () => void) => void;
  offClick: (cb: () => void) => void;
}

interface TelegramWebApp {
  initData: string;
  initDataUnsafe: {
    user?: {
      id: number;
      first_name: string;
      last_name?: string;
      username?: string;
      language_code?: string;
    };
    query_id?: string;
  };
  colorScheme: "light" | "dark";
  themeParams: TelegramThemeParams;
  viewportHeight: number;
  viewportStableHeight: number;
  isExpanded: boolean;
  HapticFeedback: TelegramHaptic;
  MainButton: TelegramMainButton;
  BackButton: TelegramBackButton;
  ready: () => void;
  expand: () => void;
  close: () => void;
  setHeaderColor: (color: string) => void;
  setBackgroundColor: (color: string) => void;
  enableClosingConfirmation: () => void;
  disableClosingConfirmation: () => void;
  onEvent: (event: string, handler: () => void) => void;
  offEvent: (event: string, handler: () => void) => void;
  openTelegramLink: (url: string) => void;
}

// ── Access ───────────────────────────────────────────────────────────────────

function getTg(): TelegramWebApp | null {
  const win = window as unknown as { Telegram?: { WebApp?: TelegramWebApp } };
  return win.Telegram?.WebApp ?? null;
}

// ── Public API ──────────────────────────────────────────────────────────────

export function getInitData(): string {
  return getTg()?.initData ?? "";
}

export function getUser() {
  return getTg()?.initDataUnsafe?.user ?? null;
}

export function getUserId(): string {
  const user = getUser();
  return user?.id ? String(user.id) : "demo";
}

export function isDarkMode(): boolean {
  return getTg()?.colorScheme !== "light";
}

export function getThemeParams(): TelegramThemeParams {
  return getTg()?.themeParams ?? {};
}

/** Call once on app start */
export function initTelegram(): void {
  const tg = getTg();
  if (!tg) return;
  try {
    tg.ready();
    tg.expand();
    tg.enableClosingConfirmation();
  } catch (err) {
    console.warn("[telegram] init error:", err);
  }
}

/** Apply Telegram theme colors to header/background */
export function applyThemeColors(): void {
  const tg = getTg();
  if (!tg) return;
  try {
    const params = tg.themeParams;
    const bg = params.bg_color || (tg.colorScheme === "dark" ? "#000000" : "#ffffff");
    tg.setHeaderColor(params.header_bg_color || bg);
    tg.setBackgroundColor(bg);
  } catch {}
}

/** Subscribe to theme changes. Returns cleanup function. */
export function onThemeChange(handler: () => void): () => void {
  const tg = getTg();
  if (!tg) return () => {};
  tg.onEvent("themeChanged", handler);
  return () => tg.offEvent("themeChanged", handler);
}

// ── Haptic Feedback ─────────────────────────────────────────────────────────

export type HapticStyle = "light" | "medium" | "heavy";

export function haptic(style: HapticStyle = "light"): void {
  try {
    getTg()?.HapticFeedback?.impactOccurred(style);
  } catch {}
}

export function hapticSuccess(): void {
  try {
    getTg()?.HapticFeedback?.notificationOccurred("success");
  } catch {}
}

export function hapticSelection(): void {
  try {
    getTg()?.HapticFeedback?.selectionChanged();
  } catch {}
}

export function openTelegramLink(url: string): void {
  const tg = getTg();
  if (tg?.openTelegramLink) {
    tg.openTelegramLink(url);
  } else {
    window.open(url, "_blank");
  }
}
