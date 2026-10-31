"use client";
import * as React from "react";
import { CheckCircle2, AlertTriangle, Info, X } from "lucide-react";
import { cn } from "@/lib/utils";

type Toast = { id: number; title: string; description?: string; variant: "success" | "error" | "info" };
const Ctx = React.createContext<(t: Omit<Toast, "id">) => void>(() => {});

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<Toast[]>([]);
  const push = React.useCallback((t: Omit<Toast, "id">) => {
    const id = Date.now() + Math.random();
    setToasts((x) => [...x, { ...t, id }]);
    setTimeout(() => setToasts((x) => x.filter((y) => y.id !== id)), t.variant === "error" ? 7000 : 4000);
  }, []);
  return (
    <Ctx.Provider value={push}>
      {children}
      <div className="fixed bottom-4 right-4 left-4 sm:left-auto z-[60] flex flex-col gap-2 sm:w-96" aria-live="polite">
        {toasts.map((t) => {
          const Icon = t.variant === "success" ? CheckCircle2 : t.variant === "error" ? AlertTriangle : Info;
          return (
            <div key={t.id} className="flex items-start gap-3 rounded-lg border bg-popover p-3 shadow-lg animate-fade-in">
              <Icon className={cn("size-5 shrink-0 mt-0.5", t.variant === "success" && "text-success", t.variant === "error" && "text-destructive", t.variant === "info" && "text-primary")} />
              <div className="flex-1 text-sm">
                <p className="font-medium">{t.title}</p>
                {t.description && <p className="text-muted-foreground mt-0.5">{t.description}</p>}
              </div>
              <button onClick={() => setToasts((x) => x.filter((y) => y.id !== t.id))} aria-label="Dismiss" className="text-muted-foreground hover:text-foreground"><X className="size-4" /></button>
            </div>
          );
        })}
      </div>
    </Ctx.Provider>
  );
}

export function useToast() {
  const push = React.useContext(Ctx);
  return React.useMemo(() => ({
    success: (title: string, description?: string) => push({ title, description, variant: "success" }),
    error: (title: string, description?: string) => push({ title, description, variant: "error" }),
    info: (title: string, description?: string) => push({ title, description, variant: "info" }),
  }), [push]);
}
