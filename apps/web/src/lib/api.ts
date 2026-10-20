import type { Report, RunMeta, UniverseRow } from "@/types/report";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8080";

async function get<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(path, API_BASE);
  if (params) {
    for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
  }
  const res = await fetch(url.toString());
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${text.slice(0, 300)}`);
  }
  return res.json() as Promise<T>;
}

export interface HealthResponse {
  ok: boolean;
  llm_provider: string;
  sarvam: boolean;
  gemini: boolean;
  prices_chain: string[];
}

export async function getHealth(): Promise<HealthResponse> {
  return get<HealthResponse>("/api/health");
}

export async function getUniverse(track = "D"): Promise<UniverseRow[]> {
  return get<UniverseRow[]>("/api/universe", { track });
}

export async function resolveQuery(q: string) {
  return get("/api/resolve", { q });
}

export async function startRun(query: string, asOf?: string, disableChallenge?: boolean): Promise<{ run_id: string }> {
  const res = await fetch(new URL("/api/runs", API_BASE), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      as_of: asOf ?? null,
      disable_challenge: disableChallenge ?? false,
    }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${text.slice(0, 300)}`);
  }
  return res.json();
}

export async function getRunMeta(runId: string): Promise<RunMeta> {
  return get<RunMeta>(`/api/runs/${runId}`);
}

// Dev-only sentinel: /report/fixture renders the bundled contract-complete fixture (every section
// populated) without needing a live engine run. Never reachable through a real run_id, since NSE/BSE
// symbols are always uppercase letters only and run_ids always carry a numeric timestamp suffix.
const FIXTURE_RUN_ID = "fixture";

export async function getReport(runId: string): Promise<Report> {
  if (runId === FIXTURE_RUN_ID) {
    const fixture = await import("@/fixtures/report_full.json");
    return fixture.default as unknown as Report;
  }
  return get<Report>(`/api/runs/${runId}/report`);
}

export async function getRecentRuns(limit = 20): Promise<RunMeta[]> {
  return get<RunMeta[]>("/api/runs", { limit: String(limit) });
}

export interface EvalSummary {
  n_companies: number;
  hypotheses_total: number;
  killed_total: number;
  kill_rate: number;
  median_runtime_s: number;
  p90_runtime_s: number;
  share_with_discovery: number;
  label_counts: Record<string, number>;
  failed: number;
  documents_median: number;
  facts_median: number;
  anomalies_median: number;
  discoveries: number;
  numbers_traced_share: number;
}

export async function getEvalSummary(): Promise<EvalSummary> {
  return get<EvalSummary>("/api/eval/summary");
}

// Mirrors engine/next_signal/eval/harness.py RunMetrics, one row per company the harness evaluated.
export interface EvalCompany {
  symbol: string;
  company: string;
  runtime_s: number;
  status: string;
  documents: number;
  hypotheses_total: number;
  killed: number;
  survived: number;
  discovery_label: string | null;
  strength_total: number | null;
  novelty: number | null;
  numbers_total: number;
  contradictions_found: number;
  angle_chosen: string | null;
  run_id: string;
  facts_count: number;
  anomalies: number;
  numbers_traced: number;
}

export async function getEvalCompanies(): Promise<EvalCompany[]> {
  return get<EvalCompany[]>("/api/eval/companies");
}

export function exportUrl(runId: string, kind: "pdf" | "md" | "xlsx" | "zip"): string {
  return new URL(`/api/runs/${runId}/export.${kind}`, API_BASE).toString();
}

export function exportCsvUrl(runId: string, table: string): string {
  return new URL(`/api/runs/${runId}/export/csv/${table}`, API_BASE).toString();
}
