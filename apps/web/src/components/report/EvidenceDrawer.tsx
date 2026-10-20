"use client";

import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { useEvidenceDrawer } from "@/store/drawer";
import { fmtDateIN } from "@/lib/format";

const GRADE_DEFINITION: Record<string, string> = {
  A: "Primary record from the entity itself, a regulator, the exchange, or raw market data.",
  B: "Reputable secondary institution (rating agency, industry body, company IR page not filed with an exchange).",
  C: "Mainstream press or a data aggregator reproducing primary figures.",
  D: "Unverified aggregator or a page that could not be matched to a known publisher class.",
  E: "Low-reliability source used only as a lead, never as sole support for a number.",
  F: "Source could not be verified at all; excluded from any claim.",
};

function highlightQuote(quote: string) {
  const parts = quote.split(/(\d[\d,.]*%?)/);
  return parts.map((part, i) =>
    /^\d/.test(part) ? (
      <mark key={i} className="bg-signal-tint px-0.5 font-tnum text-ink">
        {part}
      </mark>
    ) : (
      <span key={i}>{part}</span>
    )
  );
}

export function EvidenceDrawer() {
  const { open, item, related, close } = useEvidenceDrawer();

  return (
    <Sheet open={open} onOpenChange={(v) => !v && close()}>
      <SheetContent className="w-full max-w-xl border-l border-rule bg-background p-6 sm:max-w-xl">
        {item && (
          <>
            <SheetHeader className="px-0">
              <SheetTitle className="font-serif text-xl leading-snug">{item.title}</SheetTitle>
              <SheetDescription className="text-ink-2">
                {item.publisher}
                {item.published_at ? ` · ${fmtDateIN(item.published_at)}` : ""}
              </SheetDescription>
            </SheetHeader>

            <div className="mt-4 flex items-center gap-2">
              <span className="border border-ink px-2 py-0.5 font-mono text-[10px] font-semibold uppercase">
                {item.origin_class.replace(/_/g, " ")}
              </span>
              <span className="border border-ink bg-ink px-2 py-0.5 font-mono text-[10px] font-semibold text-white">
                Grade {item.reliability}
              </span>
            </div>
            <p className="mt-1 text-[11px] text-ink-3">{GRADE_DEFINITION[item.reliability]}</p>

            <blockquote className="mt-4 border-l-2 border-signal bg-paper-2 p-4 text-[14px] leading-relaxed">
              {highlightQuote(item.anchor.quote)}
            </blockquote>
            {item.anchor.page && (
              <p className="mt-1 text-[11px] text-ink-3">Page {item.anchor.page}</p>
            )}

            <a
              href={item.url}
              target="_blank"
              rel="noreferrer"
              className="mt-4 inline-block border-b border-signal font-mono text-xs font-semibold uppercase text-signal"
            >
              Open source
            </a>

            {related.length > 0 && (
              <div className="mt-8">
                <h4 className="font-mono text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-3">
                  Other evidence for this claim
                </h4>
                <ul className="mt-2 space-y-2">
                  {related.map((r) => (
                    <li key={r.ev_id} className="text-[13px] text-ink-2">
                      <span className="font-semibold">{r.publisher}</span>: {r.anchor.quote.slice(0, 80)}
                      {r.anchor.quote.length > 80 ? "…" : ""}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
