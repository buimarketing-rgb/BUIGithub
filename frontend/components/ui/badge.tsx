import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium whitespace-nowrap [&_svg]:size-3", {
  variants: {
    variant: {
      default: "border-transparent bg-primary/10 text-primary",
      secondary: "border-transparent bg-secondary text-secondary-foreground",
      success: "border-transparent bg-success/12 text-success",
      warning: "border-transparent bg-warning/15 text-warning",
      destructive: "border-transparent bg-destructive/10 text-destructive",
      outline: "text-muted-foreground",
    },
  },
  defaultVariants: { variant: "default" },
});

export function Badge({ className, variant, ...p }: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...p} />;
}

const STATUS: Record<string, VariantProps<typeof badgeVariants>["variant"]> = {
  verified: "success", published: "success", ready: "success", completed: "success", approved: "success", active: "success",
  draft: "secondary", archived: "outline", pending: "warning", queued: "warning", processing: "warning", running: "warning",
  needs_review: "warning", failed: "destructive", rejected: "destructive", restricted: "destructive", internal: "secondary",
};

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  return <Badge variant={STATUS[status] || "secondary"} className={className}>{status.replace(/_/g, " ")}</Badge>;
}
