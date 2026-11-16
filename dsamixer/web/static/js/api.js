// Thin fetch wrapper for the FastAPI backend under /api.
import { setFeatureConfig } from "./features.js";
import { toast } from "./ui.js";

export async function api(path, opts = {}) {
  const res = await fetch("/api" + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    const msg = typeof detail === "string" ? detail : res.statusText;
    toast(msg);
    throw new Error(msg);
  }
  const data = await res.json();
  if (path === "/settings") setFeatureConfig(data);
  return data;
}

export const patchTicket = (id, body) => api(`/tickets/${id}`, { method: "PATCH", body });
