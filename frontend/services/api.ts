/* API client: access token kept in memory only; the refresh token lives in an httpOnly cookie.
   On a 401 the client silently refreshes once and retries. */
import type { User } from "@/types";

let accessToken: string | null = null;
let refreshing: Promise<boolean> | null = null;
let onAuthLost: (() => void) | null = null;

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export const setAccessToken = (t: string | null) => { accessToken = t; };
export const getAccessToken = () => accessToken;
export const setAuthLostHandler = (fn: () => void) => { onAuthLost = fn; };

export async function refreshSession(): Promise<{ access_token: string; user: User } | null> {
  const r = await fetch("/api/auth/refresh", { method: "POST", credentials: "include", headers: { "X-Requested-With": "BUI" } });
  if (!r.ok) return null;
  const data = await r.json();
  accessToken = data.access_token;
  return data;
}

async function tryRefresh(): Promise<boolean> {
  if (!refreshing) refreshing = refreshSession().then((d) => !!d).finally(() => { refreshing = null; });
  return refreshing;
}

function errorMessage(body: unknown, status: number): string {
  const d = (body as { detail?: unknown })?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d[0]?.msg) return d.map((e: { msg: string; loc?: string[] }) => `${e.loc?.slice(-1)[0] ?? ""}: ${e.msg}`).join("; ");
  if (status === 429) return "Too many requests — please slow down.";
  if (status >= 500) return "The server had a problem. Please try again.";
  return `Request failed (${status})`;
}

export async function apiFetch(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const headers = new Headers(init.headers);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { ...init, headers, credentials: "include" });
  } catch {
    throw new ApiError(0, "Cannot reach the BUI server. Check your connection.");
  }
  if (res.status === 401 && retry && !path.startsWith("/auth/login")) {
    if (await tryRefresh()) return apiFetch(path, init, false);
    onAuthLost?.();
  }
  if (!res.ok) {
    let body: unknown = null;
    try { body = await res.json(); } catch { /* ignore */ }
    throw new ApiError(res.status, errorMessage(body, res.status));
  }
  return res;
}

export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, ...rest } = init;
  const res = await apiFetch(path, json !== undefined ? { ...rest, body: JSON.stringify(json) } : rest);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const qs = (params: Record<string, string | number | boolean | null | undefined>) => {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") p.set(k, String(v)); });
  const s = p.toString();
  return s ? `?${s}` : "";
};
