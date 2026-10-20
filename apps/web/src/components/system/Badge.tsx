import { cn } from "@/lib/utils";

const TONES = {
  ink: "border-ink bg-ink text-paper",
  signal: "border-signal bg-signal text-white",
  warn: "border-warn bg-paper text-warn",
  outline: "border-rule-strong bg-paper text-ink-2",
} as const;

export function Badge({
  tone = "outline",
  dashed = false,
  className,
  children,
}: {
  tone?: keyof typeof TONES;
  dashed?: boolean;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center border px-2 py-0.5 font-mono text-label uppercase tracking-[0.1em]",
        TONES[tone],
        dashed && "border-dashed",
        className
      )}
    >
      {children}
    </span>
  );
}
