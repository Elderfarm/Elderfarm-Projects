import { type HTMLAttributes } from "react";
import { cn } from "@/lib/cn";

type Tone = "success" | "warning" | "danger" | "info";

const toneClasses: Record<Tone, string> = {
  success: "bg-success-subtle text-success border-success/20",
  warning: "bg-warning-subtle text-warning border-warning/20",
  danger: "bg-danger-subtle text-danger border-danger/20",
  info: "bg-primary-subtle text-primary border-primary/20",
};

interface CalloutProps extends HTMLAttributes<HTMLDivElement> {
  tone?: Tone;
}

export function Callout({ tone = "info", className, ...props }: CalloutProps) {
  return (
    <div
      role="status"
      className={cn(
        "rounded-xl border px-4 py-3 text-sm",
        toneClasses[tone],
        className
      )}
      {...props}
    />
  );
}
