import { Reveal } from "@/components/ui/reveal";

const STAGES = [
  { name: "Discover", text: "Scores angles by data availability, anomaly size and novelty, not by company name." },
  { name: "Connect", text: "Every number carries its passage, page and publisher, counted by origin, not by document." },
  { name: "Calculate", text: "Forty-plus formulas, peer z-scores and change-point tests turn filings into ranked anomalies." },
  { name: "Reason", text: "Hypotheses are written as predictions that later evidence can confirm or break." },
  { name: "Challenge", text: "Five kinds of contradiction and nine falsification tests stand between a hypothesis and the report." },
  { name: "Prove", text: "Evidence strength is a rule, not a mood; every falsification condition names a metric and a date." },
];

export function MethodStrip() {
  return (
    <section className="border-b border-rule px-4 py-12">
      <div className="mx-auto max-w-6xl">
        <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-signal">
          File 04 // How it works
        </p>
        <div className="mt-6 grid grid-cols-1 gap-6 sm:grid-cols-2 md:grid-cols-6">
          {STAGES.map((stage, i) => (
            <Reveal key={stage.name} delay={i * 0.04}>
              <div className="border-t-2 border-ink pt-3">
                <div className="font-mono text-xs font-semibold uppercase tracking-[0.08em] text-signal">
                  {String(i + 1).padStart(2, "0")}
                </div>
                <div className="mt-1 font-serif text-xl">{stage.name}</div>
                <p className="mt-2 text-[13px] leading-relaxed text-ink-2">{stage.text}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
