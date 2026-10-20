// Mirrors engine/next_signal/schemas.py. Keep these in sync by hand (no codegen yet); if a field is
// added there, add it here with the same name and shape.

export type OriginClass =
  | "company_filing"
  | "company_ir"
  | "exchange"
  | "regulator_us"
  | "regulator_in"
  | "sec"
  | "rating_agency"
  | "industry_body"
  | "market_data"
  | "press"
  | "aggregator"
  | "peer_filing";

export type Grade = "A" | "B" | "C" | "D" | "E" | "F";
export type StrengthLabel = "Strong" | "Moderate" | "Weak";
export type HypothesisStatus = "proposed" | "survived" | "downgraded" | "killed";
export type RunStatus = "running" | "done" | "failed" | "partial";
export type Playbook = "pharma" | "hospital" | "diagnostics" | "generic";

export interface Anchor {
  doc_id: string;
  page?: number | null;
  quote: string;
  verified: boolean;
}

export interface Document {
  doc_id: string;
  kind: string;
  title: string;
  url: string;
  publisher: string;
  origin_class: OriginClass;
  published_at?: string | null;
  fetched_at: string;
  pages: number;
  reliability: Grade;
}

export interface EventItem {
  event_id: string;
  date: string;
  kind: string;
  title: string;
  origin_class: OriginClass;
  url: string;
  anchor?: Anchor | null;
}

export interface MetricValue {
  metric_id: string;
  period: string;
  value: number;
  unit: string;
  inputs: string[];
  formula: string;
}

export interface Anomaly {
  anomaly_id: string;
  metric_id: string;
  description: string;
  peer_z?: number | null;
  changepoint_period?: string | null;
  trend_t?: number | null;
  materiality_pct?: number | null;
  score: number;
}

export interface Prediction {
  metric_id: string;
  direction: "up" | "down" | "flat" | "present" | "absent";
  where_to_check: string;
}

export interface Hypothesis {
  hyp_id: string;
  angle_id: string;
  statement: string;
  mechanism: string;
  predictions: Prediction[];
  disconfirmers: string[];
  is_rival_of?: string | null;
  status: HypothesisStatus;
  kill_reason?: string | null;
}

export interface TestResult {
  hyp_id: string;
  test_id: string;
  applicable: boolean;
  passed?: boolean | null;
  detail: string;
  plain?: string;
  evidence_ids: string[];
}

export type ContradictionType =
  | "numeric"
  | "narrative_vs_number"
  | "temporal"
  | "cross_channel"
  | "aggregator_vs_primary";

export interface Contradiction {
  con_id: string;
  type: ContradictionType;
  claim: string;
  side_a: string;
  side_b: string;
  anchors: Anchor[];
  ruling: string;
  resolved: boolean;
}

export interface EvidenceItem {
  ev_id: string;
  doc_id: string;
  title: string;
  url: string;
  publisher: string;
  origin_class: OriginClass;
  reliability: Grade;
  published_at?: string | null;
  supports: string[];
  contradicts: string[];
  anchor: Anchor;
}

export interface Claim {
  claim_id: string;
  text: string;
  evidence_ids: string[];
  number_ids: string[];
}

export interface NumberBlock {
  number_id: string;
  label: string;
  value: number;
  unit: string;
  period: string;
  formula: string;
  inputs: string[];
  display: string;
}

export interface TimelinePoint {
  date: string;
  label: string;
  kind: string;
  event_id?: string | null;
  is_changepoint: boolean;
}

export interface Falsification {
  statement: string;
  metric_id: string;
  comparator: ">" | "<" | ">=" | "<=" | "==";
  threshold: number;
  periods_required: number;
  next_check: string;
  check_source: string;
  plain?: string;
}

export interface StrengthBreakdown {
  independence: number;
  reliability: number;
  corroboration: number;
  survival: number;
  persistence: number;
  penalties: number;
  total: number;
  label: StrengthLabel;
  reasoning: string[];
}

export interface Discovery {
  sentence: string;
  why_it_matters: string[];
  evidence: EvidenceItem[];
  timeline: TimelinePoint[];
  numbers: NumberBlock[];
  counterargument: string;
  counter_evidence_ids: string[];
  falsification: Falsification;
  strength: StrengthBreakdown;
  claims: Claim[];
  novelty: number;
  angle_id: string;
  hyp_id: string;
}

export interface RunMeta {
  run_id: string;
  symbol: string;
  company: string;
  sub_industry: string;
  as_of: string;
  started_at: string;
  finished_at?: string | null;
  runtime_s?: number | null;
  llm_calls: number;
  llm_provider_mix: Record<string, number>;
  sources_hit: number;
  documents: number;
  status: RunStatus;
}

export interface AngleConsidered {
  angle_id: string;
  score: number;
  reason: string;
}

export interface ACHMatrix {
  hypotheses: string[];
  evidence: string[];
  cells: string[][];
  inconsistency?: number[];
  ranked?: string[];
}

export interface SeriesPoint {
  period: string;
  period_end: string;
  value: number;
}

export interface Series {
  entity: string;
  metric_id: string;
  unit: string;
  points: SeriesPoint[];
  changepoint_period?: string | null;
}

export interface FinancialRow {
  period: string;
  period_end: string;
  values: Record<string, number>;
  doc_id: string;
}

export interface Report {
  meta: RunMeta;
  discovery?: Discovery | null;
  runners_up: Hypothesis[];
  killed: Hypothesis[];
  tests: TestResult[];
  ach: ACHMatrix | Record<string, never>;
  contradictions: Contradiction[];
  documents: Document[];
  events: EventItem[];
  metrics: MetricValue[];
  anomalies: Anomaly[];
  angles_considered: AngleConsidered[];
  trace: Record<string, unknown>[];
  facts_count: number;
  financials: FinancialRow[];
  series: Series[];
  peers: string[];
  stage_ms: Record<string, number>;
  glossary?: Record<string, string>;
  peer_names?: Record<string, string>;
}

export interface UniverseRow {
  symbol: string;
  name: string;
  industry: string;
  basic_industry: string;
  playbook: Playbook;
  in_nifty50: boolean;
  weight?: number | null;
}
