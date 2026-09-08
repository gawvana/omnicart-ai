/**
 * Offline Sync and Storage Layer Tests
 * Verifies reconciliation, conflict resolution, corrupted cache recovery, and queue management.
 * Built using Node standard test runner (node:test) with zero external dependencies.
 */

import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { offlineStore, onCorruptedCache } from "../storage/offlineStore.ts";
import type { CartItem } from "../types/index.ts";

// In-memory mock for localStorage if running in non-browser environment
class LocalStorageMock {
  private store: Record<string, string> = {};

  getItem(key: string): string | null {
    return this.store[key] ?? null;
  }

  setItem(key: string, value: string): void {
    this.store[key] = String(value);
  }

  removeItem(key: string): void {
    delete this.store[key];
  }

  clear(): void {
    this.store = {};
  }
}

if (typeof globalThis.localStorage === "undefined" || !globalThis.localStorage.setItem) {
  (globalThis as any).localStorage = new LocalStorageMock();
}

describe("offlineStore - Offline Sync & Conflict Resolution", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("should reconcile basic server items and remove locally-deleted items", () => {
    const item1: CartItem = {
      id: "item-1",
      item_name: "Молоко",
      category: "🥛 Молочное",
      quantity: "1",
      unit: "л",
      price_paid: "12000",
      currency_code: "UZS",
      is_purchased: false,
      created_at: new Date(Date.now() - 10000).toISOString(),
    };

    const item2: CartItem = {
      id: "item-2",
      item_name: "Хлеб",
      category: "🥖 Хлеб",
      quantity: "2",
      unit: "шт",
      price_paid: "4000",
      currency_code: "UZS",
      is_purchased: false,
      created_at: new Date(Date.now() - 10000).toISOString(),
    };

    offlineStore.saveItems([item1, item2]);
    offlineStore.removeItem("item-1");

    const reconciled = offlineStore.reconcile([item1, item2]);

    assert.equal(reconciled.find((i) => i.id === "item-1"), undefined);
    assert.ok(reconciled.find((i) => i.id === "item-2"));
  });

  it("should preserve locally-created items in reconcile", () => {
    const localNewItem: CartItem = {
      id: "local-new-1",
      item_name: "Яблоки",
      category: "🍎 Фрукты и овощи",
      quantity: "1.5",
      unit: "кг",
      price_paid: "18000",
      currency_code: "UZS",
      is_purchased: false,
      created_at: new Date().toISOString(),
    };

    offlineStore.addItem(localNewItem);

    const serverItems: CartItem[] = [
      {
        id: "server-existing",
        item_name: "Сахар",
        category: "🥫 Бакалея",
        quantity: "1",
        unit: "кг",
        price_paid: "14000",
        currency_code: "UZS",
        is_purchased: false,
        created_at: new Date(Date.now() - 20000).toISOString(),
      },
    ];

    const reconciled = offlineStore.reconcile(serverItems);
    assert.equal(reconciled.length, 2);
    assert.ok(reconciled.some((i) => i.id === "local-new-1"));
    assert.ok(reconciled.some((i) => i.id === "server-existing"));
  });

  it("should resolve conflict in favor of local mutation when local is newer", () => {
    const baseTime = Date.now() - 60000;
    const serverItem: CartItem = {
      id: "item-conflict",
      item_name: "Сыр",
      category: "🥛 Молочное",
      quantity: "1",
      unit: "кг",
      price_paid: "80000",
      currency_code: "UZS",
      is_purchased: false,
      created_at: new Date(baseTime).toISOString(),
      updated_at: baseTime,
    };

    offlineStore.saveItems([serverItem]);
    offlineStore.toggleItem("item-conflict");

    const reconciled = offlineStore.reconcile([serverItem]);
    const reconciledItem = reconciled.find((i) => i.id === "item-conflict");
    assert.equal(reconciledItem?.is_purchased, true);
  });

  it("should resolve conflict in favor of server when server is strictly newer", () => {
    const oldTime = Date.now() - 120000;
    const initialItem: CartItem = {
      id: "item-remote-win",
      item_name: "Кофе",
      category: "🥫 Бакалея",
      quantity: "1",
      unit: "упак",
      price_paid: "45000",
      currency_code: "UZS",
      is_purchased: false,
      created_at: new Date(oldTime).toISOString(),
      updated_at: oldTime,
    };

    offlineStore.saveItems([initialItem]);

    const state = (offlineStore as any)._read();
    state.pendingSyncQueue.push({
      id: "mut-1",
      action: "UPDATE",
      item: { ...initialItem, is_purchased: false },
      clientTimestamp: Date.now() - 60000,
      retryCount: 0,
      status: "queued",
    });
    (offlineStore as any)._write(state);

    const newerServerItem: CartItem = {
      ...initialItem,
      is_purchased: true,
      updated_at: Date.now(),
    };

    const reconciled = offlineStore.reconcile([newerServerItem]);
    const res = reconciled.find((i) => i.id === "item-remote-win");
    assert.equal(res?.is_purchased, true);
  });

  it("should prune failed mutations exceeding max retries", () => {
    const state = (offlineStore as any)._read();
    state.pendingSyncQueue = [
      { id: "mut-ok", action: "CREATE", item: {} as any, clientTimestamp: Date.now(), retryCount: 2, status: "failed" },
      { id: "mut-dead", action: "CREATE", item: {} as any, clientTimestamp: Date.now(), retryCount: 6, status: "failed" },
    ];
    (offlineStore as any)._write(state);

    offlineStore.pruneFailedMutations(5);
    const remaining = offlineStore.getQueue();
    assert.equal(remaining.length, 1);
    assert.equal(remaining[0].id, "mut-ok");
  });

  it("should recover pending queue and fire callback on corrupted schema", () => {
    let notifiedCount = -1;
    const unsub = onCorruptedCache((count) => {
      notifiedCount = count;
    });

    const corruptedData = {
      version: "invalid_version_string",
      items: "invalid_items_array",
      pendingSyncQueue: [
        {
          id: "recovered-mut-1",
          action: "CREATE",
          item: { id: "rec-item-1", item_name: "Тест" },
        },
      ],
    };
    localStorage.setItem("omnicart_v3", JSON.stringify(corruptedData));

    const items = offlineStore.getItems();
    assert.deepEqual(items, []);

    const queue = offlineStore.getQueue();
    assert.equal(queue.length, 1);
    assert.equal(queue[0].id, "recovered-mut-1");
    assert.equal(notifiedCount, 1);

    unsub();
  });
});
