import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(value?: string | null, withTime = false) {
  if (!value) return "—";
  const d = new Date(value);
  return withTime
    ? d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
    : d.toLocaleDateString(undefined, { dateStyle: "medium" });
}

export function timeAgo(value?: string | null) {
  if (!value) return "";
  const s = (Date.now() - new Date(value).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  if (s < 86400 * 7) return `${Math.floor(s / 86400)}d ago`;
  return formatDate(value);
}

export function formatBytes(n?: number | null) {
  if (!n) return "—";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(i ? 1 : 0)} ${u[i]}`;
}

export const label = (s: string) => s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()).replace("Faq", "FAQ");

export const ROLE_LABEL: Record<string, string> = { super_admin: "Super Admin", admin: "Admin", team_member: "Team Member" };
export const roleLevel = (r?: string) => ({ team_member: 1, admin: 2, super_admin: 3 } as Record<string, number>)[r || ""] || 0;
