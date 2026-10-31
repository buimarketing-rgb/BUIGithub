"use client";
import * as React from "react";
import { useRouter, usePathname } from "next/navigation";
import type { User } from "@/types";
import { api, refreshSession, setAccessToken, setAuthLostHandler } from "@/services/api";
import { ToastProvider } from "@/components/ui/toast";
import { ConfirmProvider } from "@/components/ui/dialog";
import { roleLevel } from "@/lib/utils";

/* ---------------- theme ---------------- */
type Theme = "light" | "dark" | "system";
const ThemeCtx = React.createContext<{ theme: Theme; setTheme: (t: Theme) => void; resolved: "light" | "dark" }>({ theme: "system", setTheme: () => {}, resolved: "light" });

function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = React.useState<Theme>("system");
  const [resolved, setResolved] = React.useState<"light" | "dark">("light");
  React.useEffect(() => {
    try { setThemeState((localStorage.getItem("bui-theme") as Theme) || "system"); } catch { /* storage unavailable */ }
  }, []);
  React.useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      const r = theme === "system" ? (mq.matches ? "dark" : "light") : theme;
      document.documentElement.classList.toggle("dark", r === "dark");
      document.documentElement.dataset.theme = r;
      setResolved(r);
    };
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, [theme]);
  const setTheme = (t: Theme) => { setThemeState(t); try { localStorage.setItem("bui-theme", t); } catch { /* ignore */ } };
  return <ThemeCtx.Provider value={{ theme, setTheme, resolved }}>{children}</ThemeCtx.Provider>;
}
export const useTheme = () => React.useContext(ThemeCtx);

/* ---------------- auth ---------------- */
interface AuthState {
  user: User | null; loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  setUser: (u: User) => void;
  can: (minRole: "team_member" | "admin" | "super_admin") => boolean;
}
const AuthCtx = React.createContext<AuthState>(null as unknown as AuthState);

function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<User | null>(null);
  const [loading, setLoading] = React.useState(true);
  const router = useRouter();
  const pathname = usePathname();

  React.useEffect(() => {
    setAuthLostHandler(() => {
      setUser(null);
      setAccessToken(null);
      if (!window.location.pathname.startsWith("/login")) router.replace(`/login?next=${encodeURIComponent(window.location.pathname)}`);
    });
    refreshSession().then((s) => setUser(s?.user ?? null)).finally(() => setLoading(false));
  }, [router]);

  // Refresh the short-lived access token before it expires
  React.useEffect(() => {
    if (!user) return;
    const t = setInterval(() => refreshSession().then((s) => { if (!s) setUser(null); }), 12 * 60 * 1000);
    return () => clearInterval(t);
  }, [user]);

  const login = async (email: string, password: string) => {
    const res = await api<{ access_token: string; user: User }>("/auth/login", { method: "POST", json: { email, password } });
    setAccessToken(res.access_token);
    setUser(res.user);
  };
  const logout = async () => {
    try { await api("/auth/logout", { method: "POST", headers: { "X-Requested-With": "BUI" } }); } catch { /* ignore */ }
    setAccessToken(null);
    setUser(null);
    window.speechSynthesis?.cancel();
    router.replace("/login");
  };
  const can = React.useCallback((r: "team_member" | "admin" | "super_admin") => roleLevel(user?.role) >= roleLevel(r), [user]);
  void pathname;
  return <AuthCtx.Provider value={{ user, loading, login, logout, setUser, can }}>{children}</AuthCtx.Provider>;
}
export const useAuth = () => React.useContext(AuthCtx);

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <ToastProvider>
        <ConfirmProvider>
          <AuthProvider>{children}</AuthProvider>
        </ConfirmProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}
