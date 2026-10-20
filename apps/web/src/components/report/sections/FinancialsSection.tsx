import { Section, SectionHeading } from "@/components/system";
import { ChartCard, DataTable, LineSeries, type Column } from "@/components/viz";
import { fmtCrore, fmtPeriod } from "@/lib/format";
import { financialsTitle } from "@/lib/headlines";
import type { FinancialRow } from "@/types/report";

const COLUMN_LABELS: Record<string, string> = {
  revenue: "Revenue",
  cogs: "COGS",
  gross_profit: "Gross profit",
  ebitda: "EBITDA",
  other_income: "Other income",
  pbt: "PBT",
  tax_expense: "Tax",
  pat: "PAT",
};

const LINE_ITEMS = ["revenue", "ebitda", "pat"];

export function FinancialsSection({ financials, company }: { financials: FinancialRow[]; company: string }) {
  if (financials.length === 0) return null;

  // financials arrives newest-first (Connect sorts it that way for the report); the table should read
  // the same way (most recent quarter first), but a line chart needs chronological order left to right.
  const chronological = [...financials].reverse();
  const chartData = chronological.map((row) => ({
    period: fmtPeriod(row.period),
    revenue: row.values.revenue ?? null,
    ebitda: row.values.ebitda ?? null,
  }));

  const columns: Column<FinancialRow>[] = [
    { key: "period", header: "Quarter", accessor: (r) => fmtPeriod(r.period), mono: true, width: "96px" },
    ...LINE_ITEMS.filter((item) => financials.some((r) => r.values[item] !== undefined)).map((item) => ({
      key: item,
      header: COLUMN_LABELS[item] ?? item,
      accessor: (r: FinancialRow) => (r.values[item] !== undefined ? fmtCrore(r.values[item], 1) : "-"),
      sortValue: (r: FinancialRow) => r.values[item] ?? 0,
      align: "right" as const,
      mono: true,
    })),
  ];

  return (
    <Section id="financials">
      <SectionHeading
        index="02"
        kicker="Financial base"
        title={financialsTitle(financials, company)}
        lede="Every figure below traces to a verified line item in a real XBRL filing, in INR crore, newest quarter first."
      />
      <div className="grid gap-5 md:grid-cols-2">
        <ChartCard title="Revenue and EBITDA" source="NSE XBRL filings" soWhat="Each point is a verified quarterly figure from the company's own XBRL filing, not an estimate.">
          <LineSeries
            data={chartData}
            lines={[
              { key: "revenue", label: "Revenue" },
              { key: "ebitda", label: "EBITDA" },
            ]}
            unit={(v) => fmtCrore(v, 0)}
          />
        </ChartCard>
        <div className="border border-rule p-5 md:p-6">
          <h3 className="text-h3 font-sans font-semibold text-ink">Quarterly P&amp;L</h3>
          <div className="mt-4">
            <DataTable columns={columns} rows={financials.slice(0, 8)} rowKey={(r) => r.period} dense />
          </div>
        </div>
      </div>
    </Section>
  );
}
