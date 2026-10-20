"use client";

import { Topbar } from "@/components/layout/Topbar";
import { Footer } from "@/components/layout/Footer";
import { DataTable, type Column } from "@/components/viz";

// One row per source module that actually exists under engine/next_signal/sources/ (checked by
// grepping that folder before writing this list; a row with no backing module is dropped rather than
// invented, per the project's "no invented names or numbers" rule).
interface SourceModule {
  source: string;
  module: string;
  host: string;
  grade: string;
  category: string;
}

const SOURCE_MODULES: SourceModule[] = [
  { source: "NSE corporate filings and XBRL", module: "sources/nse_financials.py", host: "nseindia.com", grade: "A", category: "Exchange" },
  { source: "NSE announcements", module: "sources/nse.py", host: "nseindia.com", grade: "A", category: "Exchange" },
  { source: "BSE announcements", module: "sources/bse.py", host: "bseindia.com", grade: "A", category: "Exchange" },
  { source: "openFDA recalls and approvals", module: "sources/openfda.py", host: "api.fda.gov", grade: "A", category: "US regulator" },
  { source: "FDA accessdata pages", module: "sources/fda_web.py", host: "accessdata.fda.gov", grade: "A", category: "US regulator" },
  { source: "Screener", module: "sources/screener.py", host: "screener.in", grade: "C", category: "Aggregator" },
];

const SOURCE_CLASSES = [
  { label: "Company filing / IR", grade: "A/B", note: "NSE and BSE exchange filings, annual reports, investor presentations, earnings-call transcripts." },
  { label: "Exchange and market data", grade: "A", note: "NSE MCP, Angel One, Upstox, NSE bhavcopy archives, used as a fallback chain." },
  { label: "US regulator", grade: "A", note: "openFDA (drugsfda, enforcement), FDA warning letters, Import Alert 66-40, the Orange Book." },
  { label: "India regulator", grade: "A", note: "CDSCO, NPPA, SEBI, PIB, RBI." },
  { label: "SEC", grade: "A", note: "SEC EDGAR filings for Indian companies that file as US ADR issuers." },
  { label: "Rating agency", grade: "B", note: "CRISIL, ICRA, CARE Ratings rationales." },
  { label: "Industry body", grade: "B", note: "Pharmexcil, IQVIA/Pharmarack as reported in Indian financial press." },
  { label: "Peer filing", grade: "A", note: "The same exchange-filing class, applied to comparable companies." },
  { label: "Press", grade: "C", note: "Mainstream financial media, used for timing (first mainstream coverage) and corroboration, never as sole support." },
  { label: "Aggregator", grade: "C/D", note: "Screener, Moneycontrol and similar data pages. Useful for speed; any number cited in a Discovery must also be anchored in a primary document." },
];

const MODULE_COLUMNS: Column<SourceModule>[] = [
  { key: "source", header: "Source", accessor: (m) => m.source },
  { key: "module", header: "Module", accessor: (m) => m.module, mono: true },
  { key: "host", header: "Host", accessor: (m) => m.host, mono: true },
  { key: "grade", header: "Grade", accessor: (m) => m.grade, mono: true, align: "right", width: "72px" },
  { key: "category", header: "Category", accessor: (m) => m.category, width: "140px" },
];

export default function AboutPage() {
  return (
    <>
      <Topbar />
      <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-12">
        <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-signal">
          File 05 // About
        </p>
        <h1 className="mt-2 font-serif text-3xl">What this system is, and what it is not</h1>

        <div className="mt-8 space-y-4 text-[15px] leading-relaxed text-ink-2">
          <p>
            Next Signal is an autonomous research agent built for the ATMOS 2026 hackathon, Track D
            (Pharma and Healthcare). Given any NIFTY 50 pharma or healthcare company, it collects public
            evidence from exchange filings, USFDA records, peers and market data, computes what changed
            and when, tests every hypothesis against its strongest rival, and reports only what survives,
            with a verbatim source behind every number.
          </p>
          <p>
            It is not a summariser. A system that only reads a company&apos;s own documents cannot find
            the kind of story the brief&apos;s own worked example describes, because that story is a
            calculated gap between what management says and what the numbers show, not a quote from
            either source alone.
          </p>
          <p>
            It does not give investment advice. Nothing in this dashboard, its exports, or its voice
            analyst states a buy, sell or hold view, a price target, or a recommendation. The brief
            explicitly asks for a discovery and its evidence, not a trading call.
          </p>
        </div>

        <h2 className="mt-12 font-mono text-[11px] font-semibold uppercase tracking-[0.1em] text-ink-3">
          Source classes and how they are graded
        </h2>
        <div className="mt-4 divide-y divide-rule border border-rule">
          {SOURCE_CLASSES.map((s) => (
            <div key={s.label} className="flex gap-4 p-4">
              <div className="w-40 flex-shrink-0">
                <div className="text-sm font-semibold text-ink">{s.label}</div>
                <div className="font-mono text-xs text-signal">Grade {s.grade}</div>
              </div>
              <p className="text-sm text-ink-2">{s.note}</p>
            </div>
          ))}
        </div>

        <h2 className="mt-12 font-mono text-[11px] font-semibold uppercase tracking-[0.1em] text-ink-3">
          Source modules in this codebase
        </h2>
        <p className="mt-3 text-small text-ink-2">
          Each row below is a module that fetches from the named host today, checked against
          engine/next_signal/sources/ directly. A source class with no module behind it yet (the NIFTY
          index constituent list) is left out rather than listed ahead of the code.
        </p>
        <div className="mt-4">
          <DataTable columns={MODULE_COLUMNS} rows={SOURCE_MODULES} rowKey={(m) => m.module} dense />
        </div>

        <h2 className="mt-12 font-mono text-[11px] font-semibold uppercase tracking-[0.1em] text-ink-3">
          Research and data
        </h2>
        <div className="mt-4 space-y-2">
          <a
            href="https://harshkawatra11.github.io/next-signal/Next-Signal-Research-Note-CIPLA.pdf"
            className="flex items-center justify-between border border-rule px-4 py-3 text-ink hover:bg-paper-2"
          >
            <span className="text-blue-700">Research paper (PDF)</span>
            <span className="text-blue-700">&rarr;</span>
          </a>
          <a
            href="https://harshkawatra11.github.io/next-signal/Next-Signal-Model-Workbook-CIPLA.xlsx"
            download
            className="flex items-center justify-between border border-rule px-4 py-3 text-ink hover:bg-paper-2"
          >
            <span className="text-blue-700">Model workbook (XLSX, downloads)</span>
            <span className="text-blue-700">&rarr;</span>
          </a>
          <a
            href="https://github.com/harshkawatra11/next-signal"
            className="flex items-center justify-between border border-rule px-4 py-3 text-ink hover:bg-paper-2"
          >
            <span className="text-blue-700">Source code on GitHub</span>
            <span className="text-blue-700">&rarr;</span>
          </a>
        </div>
      </main>
      <Footer />
    </>
  );
}
