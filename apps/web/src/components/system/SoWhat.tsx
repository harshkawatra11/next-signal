import { cn } from "@/lib/utils";

// A chart or table footnote stating one plain analytical takeaway sentence, the "so what" a chart
// earns its keep with. Not a caption describing what the chart is; a sentence stating what it means.
export function SoWhat({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <p className={cn("mt-3 border-t border-rule pt-3 text-small leading-relaxed text-ink-2 md:mt-4", className)}>
      {children}
    </p>
  );
}
