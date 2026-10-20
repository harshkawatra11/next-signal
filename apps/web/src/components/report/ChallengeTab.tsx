import type { ACHMatrix as ACHMatrixType, Contradiction, Discovery, Hypothesis, TestResult } from "@/types/report";
import { ACHMatrix } from "./ACHMatrix";
import { DataTable, type Column } from "@/components/viz";
import { fmtDateIN } from "@/lib/format";

function PassCell({ cell }: { cell: TestResult | undefined }) {
  const passed = cell?.passed;
  const title = cell?.plain || cell?.detail;
  if (passed === true) return <span className="text-ink" title={title}>Pass</span>;
  if (passed === false) return <span className="text-signal" title={title}>Fail</span>;
  return <span className="text-ink-3" title={title}>n/a</span>;
}

const CONTRADICTION_LABELS: Record<Contradiction["type"], string> = {
  numeric: "Numeric mismatch",
  narrative_vs_number: "Narrative vs number",
  temporal: "Temporal",
  cross_channel: "Cross channel",
  aggregator_vs_primary: "Aggregator vs primary",
};

export function ChallengeTab({
  discovery,
  tests,
  killed,
  ach,
  contradictions = [],
}: {
  discovery: Discovery;
  tests: TestResult[];
  killed: Hypothesis[];
  ach?: ACHMatrixType;
  contradictions?: Contradiction[];
}) {
  const testIds = Array.from(new Set(tests.map((t) => t.test_id))).sort();
  const hypIds = Array.from(new Set(tests.map((t) => t.hyp_id)));

  const contradictionColumns: Column<Contradiction>[] = [
    { key: "type", header: "Type", accessor: (c) => CONTRADICTION_LABELS[c.type] ?? c.type, width: "160px" },
    { key: "claim", header: "Claim", accessor: (c) => c.claim },
    { key: "side_a", header: "Side A", accessor: (c) => c.side_a },
    { key: "side_b", header: "Side B", accessor: (c) => c.side_b },
    {
      key: "ruling",
      header: "Ruling",
      accessor: (c) => (
        <span className={c.resolved ? "text-ink-2" : "text-signal"}>{c.ruling}</span>
      ),
    },
  ];

  return (
    <div className="grid gap-4">
      {ach && <ACHMatrix matrix={ach} mainHypId={discovery.hyp_id} />}

      <div className="grid gap-4 md:grid-cols-2">
        <div className="border-2 border-signal border-dashed p-5">
          <h3 className="font-mono text-label font-semibold uppercase tracking-[0.1em] text-signal">
            Counterargument
          </h3>
          <p className="mt-2 text-small leading-relaxed text-ink-2">{discovery.counterargument}</p>
        </div>
        <div className="border border-rule p-5">
          <h3 className="font-mono text-label font-semibold uppercase tracking-[0.1em] text-ink-3">
            Falsification condition
          </h3>
          <p className="mt-2 text-small leading-relaxed text-ink-2">
            {discovery.falsification.plain || discovery.falsification.statement}
          </p>
          <p className="mt-2 font-mono text-label text-ink-3">
            Next check: {fmtDateIN(discovery.falsification.next_check)} ({discovery.falsification.check_source})
          </p>
        </div>
      </div>

      {testIds.length > 0 && (
        <div className="border border-rule p-5">
          <h3 className="font-mono text-label font-semibold uppercase tracking-[0.1em] text-ink-3">
            {testIds.length} falsification {testIds.length === 1 ? "test" : "tests"}
          </h3>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-small">
              <thead>
                <tr>
                  <th className="p-2" />
                  {hypIds.map((h) => (
                    <th key={h} className="p-2 font-mono text-[10px] uppercase text-ink-3">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {testIds.map((testId) => (
                  <tr key={testId} className="border-t border-rule">
                    <td className="p-2 font-mono text-[11px] font-semibold">{testId}</td>
                    {hypIds.map((h) => {
                      const cell = tests.find((t) => t.test_id === testId && t.hyp_id === h);
                      return (
                        <td key={h} className="p-2 font-mono text-[11px]">
                          <PassCell cell={cell} />
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {tests.some((t) => t.applicable && t.passed === false && t.plain) && (
            <div className="mt-3 border-t border-rule pt-3">
              <h4 className="font-mono text-label font-semibold uppercase tracking-[0.1em] text-ink-3">Why</h4>
              <ul className="mt-2 space-y-1">
                {tests
                  .filter((t) => t.applicable && t.passed === false && t.plain)
                  .map((t) => (
                    <li key={`${t.hyp_id}-${t.test_id}`} className="text-small text-ink-2">
                      {t.plain}
                    </li>
                  ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {contradictions.length > 0 && (
        <div className="border border-rule p-5">
          <h3 className="font-mono text-label font-semibold uppercase tracking-[0.1em] text-ink-3">
            Contradictions found while checking the claim
          </h3>
          <div className="mt-3">
            <DataTable columns={contradictionColumns} rows={contradictions} rowKey={(c) => c.con_id} dense />
          </div>
        </div>
      )}

      {killed.length > 0 && (
        <div className="border border-rule p-5">
          <h3 className="font-mono text-label font-semibold uppercase tracking-[0.1em] text-ink-3">
            Kill log
          </h3>
          <ul className="mt-3 space-y-2">
            {killed.map((h) => (
              <li key={h.hyp_id} className="text-small">
                <span className="font-semibold text-ink">{h.statement}</span>
                <span className="ml-2 text-ink-3">{h.kill_reason}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
