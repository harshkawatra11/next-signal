import { cn } from "@/lib/utils";

// Content width is wider than the marketing-site 6xl, since this is a dense data app, not a landing
// page: 1180px holds a two-column report section plus a side rail without feeling cramped.
export function Container({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("mx-auto w-full max-w-[1180px] px-4 md:px-8", className)}>{children}</div>;
}
