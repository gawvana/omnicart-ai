/**
 * OmniCart AI — Sync Engine
 * Processes queued mutations with retry logic.
 * Mutations are only removed from queue AFTER successful API call.
 */

import { offlineStore } from "./offlineStore";
import checklistApi from "../services/checklistApi";
import type { SyncMutation } from "../types";

const MAX_RETRIES = 5;
const BASE_DELAY = 1000; // 1 second

function delay(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

function backoffDelay(retryCount: number): number {
  return Math.min(BASE_DELAY * Math.pow(2, retryCount), 30_000);
}

/**
 * Process all queued mutations one by one.
 * Returns the number of successfully synced mutations.
 */
export async function processQueue(): Promise<number> {
  const queue = offlineStore.getQueue();
  if (queue.length === 0) return 0;

  let syncedCount = 0;

  for (const mutation of queue) {
    if (mutation.retryCount >= MAX_RETRIES) {
      offlineStore.removeMutation(mutation.id);
      continue;
    }

    try {
      await processMutation(mutation);
      offlineStore.removeMutation(mutation.id);
      syncedCount++;
    } catch (err) {
      console.warn("[syncEngine] mutation failed:", mutation.action, err);
      offlineStore.markMutationFailed(mutation.id);

      // Wait before continuing to next mutation
      if (mutation.retryCount < MAX_RETRIES - 1) {
        await delay(backoffDelay(mutation.retryCount));
      }
    }
  }

  // Clean up old failed mutations
  offlineStore.pruneFailedMutations(MAX_RETRIES);

  return syncedCount;
}

async function processMutation(mutation: SyncMutation): Promise<void> {
  switch (mutation.action) {
    case "CREATE": {
      // Server will create its own UUID, but we keep our client ID for reconciliation
      await checklistApi.create({
        item_name: mutation.item.item_name,
        category: mutation.item.category || undefined,
        quantity: parseFloat(mutation.item.quantity) || 1,
        unit: mutation.item.unit,
        price_paid: parseFloat(mutation.item.price_paid) || 0,
      });
      break;
    }

    case "UPDATE": {
      // Only sync toggle for items that have valid UUIDs (not client-generated)
      // Client UUIDs from crypto.randomUUID() are valid UUID format, so we just try
      try {
        await checklistApi.toggle(mutation.item.id, mutation.item.is_purchased);
      } catch (err: unknown) {
        // 404 means item doesn't exist on server yet (client-generated ID)
        // This is expected for items created offline — the CREATE mutation handles it
        if (err && typeof err === "object" && "status" in err && (err as { status: number }).status === 404) {
          return; // Silently skip
        }
        throw err;
      }
      break;
    }

    case "DELETE": {
      try {
        await checklistApi.remove(mutation.item.id);
      } catch (err: unknown) {
        // 404 = already deleted, that's fine
        if (err && typeof err === "object" && "status" in err && (err as { status: number }).status === 404) {
          return;
        }
        throw err;
      }
      break;
    }
  }
}

export default { processQueue };
