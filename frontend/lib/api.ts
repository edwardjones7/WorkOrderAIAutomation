import type { WorkOrder, WorkOrderDetail } from "./types";
import { DEMO_ORDERS, demoDetail } from "./demo";

async function j<T>(p: Promise<Response>): Promise<T> {
  const res = await p;
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

// True once any request has failed to reach the backend — drives the demo banner.
export const backend = { live: true };

function markDown() {
  backend.live = false;
}

export const api = {
  list: async (status?: string): Promise<WorkOrder[]> => {
    try {
      const rows = await j<WorkOrder[]>(fetch(`/api/work-orders${status ? `?status=${status}` : ""}`));
      backend.live = true;
      return rows;
    } catch {
      markDown();
      if (!status) return DEMO_ORDERS;
      const wanted = new Set(status.split(","));
      return DEMO_ORDERS.filter((o) => wanted.has(o.status));
    }
  },

  stats: async (): Promise<Record<string, number>> => {
    try {
      return await j<Record<string, number>>(fetch("/api/work-orders/stats"));
    } catch {
      markDown();
      return DEMO_ORDERS.reduce<Record<string, number>>((acc, o) => {
        acc[o.status] = (acc[o.status] || 0) + 1;
        return acc;
      }, {});
    }
  },

  get: async (id: string): Promise<WorkOrderDetail> => {
    try {
      const d = await j<WorkOrderDetail>(fetch(`/api/work-orders/${id}`));
      backend.live = true;
      return d;
    } catch {
      markDown();
      return demoDetail(id);
    }
  },

  update: (id: string, patch: Partial<WorkOrder>) =>
    j<WorkOrder>(
      fetch(`/api/work-orders/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      })
    ).catch(() => { markDown(); return {} as WorkOrder; }),

  approve: (id: string) =>
    j<{ ok: boolean; message: string }>(
      fetch(`/api/work-orders/${id}/approve`, { method: "POST" })
    ).catch(() => { markDown(); return { ok: false, message: "Demo mode — approval not sent" }; }),

  ignore: (id: string) =>
    j<WorkOrder>(fetch(`/api/work-orders/${id}/ignore`, { method: "POST" }))
      .catch(() => { markDown(); return {} as WorkOrder; }),

  copyText: (id: string) =>
    j<{ text: string }>(fetch(`/api/work-orders/${id}/copy-text`)).catch(() => {
      markDown();
      const wo = DEMO_ORDERS.find((o) => o.id === id) || DEMO_ORDERS[0];
      return {
        text: [
          `Property: ${wo.property_address || ""}`,
          `Unit: ${wo.unit || ""}`,
          `Resident: ${wo.resident_name || ""}`,
          `Category: ${wo.category || ""}`,
          `Priority: ${wo.priority || ""}`,
          `Vendor: ${wo.vendor || ""}`,
          `Description: ${wo.issue || ""}`,
        ].join("\n"),
      };
    }),

  pollNow: () => j<{ ingested: number }>(fetch("/api/poll-now", { method: "POST" })),
};
