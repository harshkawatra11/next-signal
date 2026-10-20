import { cn } from "@/lib/utils";

export function SourceLine({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <p className={cn("text-right font-mono text-label text-ink-3", className)}>
      Source: {children}
    </p>
  );
}
