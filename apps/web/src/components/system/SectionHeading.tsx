import { Kicker } from "./Kicker";

export function SectionHeading({
  kicker,
  title,
  lede,
  index,
}: {
  kicker: string;
  title: string;
  lede?: string;
  index?: string;
}) {
  return (
    <div className="mb-8 md:mb-10">
      <div className="flex items-baseline gap-3">
        {index && <span className="font-mono text-kicker text-ink-3">{index}</span>}
        <Kicker>{kicker}</Kicker>
      </div>
      <h2 className="mt-3 text-h2 font-serif leading-h2 text-ink">{title}</h2>
      {lede && <p className="mt-4 max-w-2xl text-lede leading-lede text-ink-2">{lede}</p>}
    </div>
  );
}
