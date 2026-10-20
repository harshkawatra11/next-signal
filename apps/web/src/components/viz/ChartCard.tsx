import { cn } from "@/lib/utils";
import { SoWhat } from "@/components/system/SoWhat";
import { SourceLine } from "@/components/system/SourceLine";

export function ChartCard({
  title,
  source,
  soWhat,
  className,
  children,
}: {
  title: string;
  source?: string;
  soWhat?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("border border-rule p-5 md:p-6", className)}>
      <h3 className="text-h3 font-sans font-semibold text-ink">{title}</h3>
      <div className="mt-4">{children}</div>
      {soWhat && <SoWhat>{soWhat}</SoWhat>}
      {source && <SourceLine className="mt-3">{source}</SourceLine>}
    </div>
  );
}
