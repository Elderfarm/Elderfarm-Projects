import { type HTMLAttributes } from "react";
import { cn } from "@/lib/cn";

export type BadgeStatus = "success" | "warning" | "danger" | "neutral";

const statusClasses: Record<BadgeStatus, string> = {
  success: "bg-success-subtle text-success",
  warning: "bg-warning-subtle text-warning",
  danger: "bg-danger-subtle text-danger",
  neutral: "bg-muted-subtle text-muted",
};

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  status?: BadgeStatus;
}

export function Badge({ status = "neutral", className, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
        statusClasses[status],
        className
      )}
      {...props}
    />
  );
}
