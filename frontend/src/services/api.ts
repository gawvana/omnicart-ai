/**
 * OmniCart AI — HTTP API Client
 * Centralized fetch wrapper with auth, error handling, and timeout.
 */

import { getInitData } from "./telegram";
import type { ApiError } from "../types";

const API_TIMEOUT = 10_000; // 10 seconds

class ApiClientError extends Error {
  status: number;
  requestId?: string;

  constructor(message: string, status: number, requestId?: string) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.requestId = requestId;
  }
}

async function request<T>(
  url: string,
  options: RequestInit = {}
): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT);

  const initData = getInitData();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(initData ? { Authorization: `tma ${initData}` } : {}),
    ...(options.headers as Record<string, string> || {}),
  };

  try {
    const res = await fetch(url, {
      ...options,
      headers,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (res.status === 204) {
      return undefined as T;
    }

    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      let requestId: string | undefined;
      try {
        const body: ApiError = await res.json();
        detail = body.error || detail;
        requestId = body.request_id;
      } catch {}

      // User-friendly messages for common HTTP errors
      if (res.status === 401) {
        detail = "Сессия истекла. Откройте приложение заново из Telegram";
      } else if (res.status === 403) {
        detail = "Доступ запрещён";
      } else if (res.status === 429) {
        detail = "Слишком много запросов. Подождите минуту";
      }

      throw new ApiClientError(detail, res.status, requestId);
    }

    return await res.json() as T;
  } catch (err) {
    clearTimeout(timeoutId);
    if (err instanceof ApiClientError) throw err;
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiClientError("Request timed out", 408);
    }
    throw new ApiClientError(
      err instanceof Error ? err.message : "Network error",
      0
    );
  }
}

export const api = {
  get: <T>(url: string) => request<T>(url),

  post: <T>(url: string, body?: unknown) =>
    request<T>(url, {
      method: "POST",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),

  patch: <T>(url: string, body?: unknown) =>
    request<T>(url, {
      method: "PATCH",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),

  delete: <T>(url: string) =>
    request<T>(url, { method: "DELETE" }),
};

export { ApiClientError };
export default api;
