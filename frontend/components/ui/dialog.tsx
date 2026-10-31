"use client";
import * as React from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "./button";

export function Dialog({ open, onClose, title, description, children, footer, size = "md" }: {
  open: boolean; onClose: () => void; title: string; description?: string; children?: React.ReactNode; footer?: React.ReactNode; size?: "sm" | "md" | "lg" | "xl";
}) {
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", onKey); document.body.style.overflow = ""; };
  }, [open, onClose]);
  if (!open || typeof document === "undefined") return null;
  const width = { sm: "max-w-md", md: "max-w-lg", lg: "max-w-2xl", xl: "max-w-4xl" }[size];
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-[2px]" onClick={onClose} />
      <div role="dialog" aria-modal="true" aria-label={title}
        className={cn("relative w-full max-h-[92vh] flex flex-col rounded-t-xl sm:rounded-xl border bg-card shadow-xl animate-fade-in", width)}>
        <div className="flex items-start justify-between gap-4 border-b p-5">
          <div>
            <h2 className="text-lg font-semibold">{title}</h2>
            {description && <p className="text-sm text-muted-foreground mt-1">{description}</p>}
          </div>
          <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Close"><X /></Button>
        </div>
        <div className="overflow-y-auto p-5 scrollbar-thin">{children}</div>
        {footer && <div className="flex flex-wrap justify-end gap-2 border-t p-4">{footer}</div>}
      </div>
    </div>,
    document.body
  );
}

type ConfirmOpts = { title: string; description?: string; confirmLabel?: string; destructive?: boolean };
const ConfirmCtx = React.createContext<(o: ConfirmOpts) => Promise<boolean>>(async () => false);

export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = React.useState<(ConfirmOpts & { resolve: (v: boolean) => void }) | null>(null);
  const confirm = React.useCallback((o: ConfirmOpts) => new Promise<boolean>((resolve) => setState({ ...o, resolve })), []);
  const close = (v: boolean) => { state?.resolve(v); setState(null); };
  return (
    <ConfirmCtx.Provider value={confirm}>
      {children}
      <Dialog open={!!state} onClose={() => close(false)} title={state?.title || ""} description={state?.description} size="sm"
        footer={<>
          <Button variant="outline" onClick={() => close(false)}>Cancel</Button>
          <Button variant={state?.destructive ? "destructive" : "default"} onClick={() => close(true)}>{state?.confirmLabel || "Confirm"}</Button>
        </>} />
    </ConfirmCtx.Provider>
  );
}
export const useConfirm = () => React.useContext(ConfirmCtx);
