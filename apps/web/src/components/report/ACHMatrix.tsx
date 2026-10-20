import type { ACHMatrix as ACHMatrixType } from "@/types/report";

const GLYPH_STYLE: Record<string, string> = {
  CC: "bg-ink text-white",
  C: "bg-ink-2 text-white",
  N: "bg-background text-ink-3 border border-rule",
  I: "bg-signal-tint text-signal",
  II: "bg-signal text-white",
};

export function ACHMatrix({ matrix, mainHypId }: { matrix: ACHMatrixType; mainHypId?: string }) {
  if (!matrix.hypotheses?.length || !matrix.evidence?.length) return null;

  return (
    <div className="border border-rule p-5">
      <h3 className="font-mono text-[11px] font-semibold uppercase tracking-[0.1em] text-ink-3">
        Analysis of competing hypotheses
      </h3>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-left text-[12px]">
          <thead>
            <tr>
              <th className="min-w-[160px] p-2" />
              {matrix.hypotheses.map((h) => (
                <th
                  key={h}
                  className={`p-2 text-center font-mono text-[10px] uppercase ${
                    h === mainHypId ? "border-2 border-ink" : "text-ink-3"
                  }`}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.evidence.map((e, i) => (
              <tr key={e} className="border-t border-rule">
                <td className="max-w-[200px] truncate p-2 text-ink-2">{e}</td>
                {matrix.hypotheses.map((h, j) => {
                  const glyph = matrix.cells[i]?.[j] ?? "N";
                  return (
                    <td key={h} className="p-1 text-center">
                      <span
                        className={`inline-flex h-7 w-10 items-center justify-center font-mono text-[11px] font-semibold ${GLYPH_STYLE[glyph] ?? GLYPH_STYLE.N}`}
                      >
                        {glyph}
                      </span>
                    </td>
                  );
                })}
              </tr>
            ))}
            {matrix.inconsistency && (
              <tr className="border-t-2 border-ink">
                <td className="p-2 font-mono text-[10px] uppercase text-ink-3">Inconsistency</td>
                {matrix.inconsistency.map((v, j) => (
                  <td key={j} className="p-2 text-center font-tnum text-[11px] font-semibold">
                    {v}
                  </td>
                ))}
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-[11px] text-ink-3">
        CC/C: consistent. N: neutral. I/II: inconsistent. The column with the lowest inconsistency score
        is the strongest surviving hypothesis.
      </p>
    </div>
  );
}
