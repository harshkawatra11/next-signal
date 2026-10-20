import { cn } from "@/lib/utils";

export function Kicker({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <p className={cn("text-kicker font-mono font-semibold uppercase tracking-[0.16em] text-signal", className)}>
      {children}
    </p>
  );
}
