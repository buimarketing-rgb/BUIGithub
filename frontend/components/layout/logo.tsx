import Image from "next/image";
import { cn } from "@/lib/utils";

export function Logo({ className, withText = true }: { className?: string; withText?: boolean }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <Image src="/bui-logo.jpg" alt="BUI" width={36} height={36} className="rounded-lg ring-1 ring-border" priority />
      {withText && (
        <div className="leading-tight">
          <p className="font-bold tracking-tight">BUI</p>
          <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Business Unified Intelligence</p>
        </div>
      )}
    </div>
  );
}
