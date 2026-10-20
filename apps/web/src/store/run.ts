import { create } from "zustand";
import type { RunEvent } from "@/lib/sse";

export const STAGES = ["Discover", "Connect", "Calculate", "Reason", "Challenge", "Prove"] as const;
export type StageName = (typeof STAGES)[number];

export interface StageState {
  name: StageName;
  state: "pending" | "running" | "done" | "timeout";
  ms?: number;
}

export interface SourceFetchLogEntry {
  host: string;
  url: string;
  status: number;
  ms: number;
  cached: boolean;
}

export interface HypothesisCardState {
  hyp_id: string;
  statement: string;
  status: "proposed" | "survived" | "downgraded" | "killed";
  kill_reason?: string;
  tests: Record<string, boolean | null>;
}

export interface RunUiState {
  runId: string | null;
  connected: boolean;
  stages: Record<StageName, StageState>;
  sourceLog: SourceFetchLogEntry[];
  documentsCount: number;
  factsCount: number;
  hypotheses: Record<string, HypothesisCardState>;
  contradictions: Array<{ type: string; claim: string }>;
  discoverySentence: string | null;
  discoveryLabel: string | null;
  done: boolean;
  error: string | null;
  angles: Array<{ angle_id: string; score: number; chosen: boolean; reason: string }>;
  anomalies: Array<{
    anomaly_id: string;
    metric_id: string;
    label?: string;
    score: number;
    peer_z?: number | null;
    changepoint_period?: string | null;
  }>;
  rivalsCount: number;
  fetchCount: number;
  runtimeS: number | null;
  // Every event's seq is recorded here once applied. The server replays past events on every fresh
  // subscription (reconnect after a network blip, StrictMode double-mount), so without this guard a
  // replay double-counts documents/facts, duplicates contradictions, and resets a killed hypothesis
  // card back to "proposed".
  appliedSeq: Set<number>;

  reset: (runId: string) => void;
  applyEvent: (ev: RunEvent) => void;
}

function freshStages(): Record<StageName, StageState> {
  return STAGES.reduce((acc, name) => {
    acc[name] = { name, state: "pending" };
    return acc;
  }, {} as Record<StageName, StageState>);
}

export const useRunStore = create<RunUiState>((set, get) => ({
  runId: null,
  connected: false,
  stages: freshStages(),
  sourceLog: [],
  documentsCount: 0,
  factsCount: 0,
  hypotheses: {},
  contradictions: [],
  discoverySentence: null,
  discoveryLabel: null,
  done: false,
  error: null,
  angles: [],
  anomalies: [],
  rivalsCount: 0,
  fetchCount: 0,
  runtimeS: null,
  appliedSeq: new Set<number>(),

  reset: (runId) =>
    set({
      runId,
      connected: true,
      stages: freshStages(),
      sourceLog: [],
      documentsCount: 0,
      factsCount: 0,
      hypotheses: {},
      contradictions: [],
      discoverySentence: null,
      discoveryLabel: null,
      done: false,
      error: null,
      angles: [],
      anomalies: [],
      rivalsCount: 0,
      fetchCount: 0,
      runtimeS: null,
      appliedSeq: new Set<number>(),
    }),

  applyEvent: (ev) => {
    const { type, data, seq } = ev;
    const state = get();

    if (seq > 0) {
      if (state.appliedSeq.has(seq)) return;
      state.appliedSeq.add(seq);
    }

    switch (type) {
      case "stage": {
        const name = data.stage as StageName;
        if (!STAGES.includes(name)) return;
        const existing = state.stages[name];
        let nextState: StageState["state"];
        if (data.state === "start") nextState = "running";
        else if (data.state === "timeout") nextState = "timeout";
        else if (data.state === "end") {
          // A stage that already timed out stays "timeout" even though the engine still sends a
          // trailing "end" event right after: the timed-out stage ran to completion under a hard cap,
          // and the rail should keep showing that it was slow, not quietly mark it "done".
          nextState = existing?.state === "timeout" ? "timeout" : "done";
        } else {
          nextState = "done";
        }
        set({
          stages: {
            ...state.stages,
            [name]: { name, state: nextState, ms: typeof data.ms === "number" ? data.ms : existing?.ms },
          },
        });
        return;
      }
      case "source_fetch": {
        const entry = data as unknown as SourceFetchLogEntry;
        set({ sourceLog: [entry, ...state.sourceLog].slice(0, 14), fetchCount: state.fetchCount + 1 });
        return;
      }
      case "doc_parsed":
        set({ documentsCount: state.documentsCount + (typeof data.count === "number" ? data.count : 1) });
        return;
      case "fact":
        set({
          factsCount:
            state.factsCount + (typeof data.verified === "number" ? data.verified : data.verified ? 1 : 0),
        });
        return;
      case "hypothesis": {
        const hypId = data.hyp_id as string;
        if (data.is_rival_of) {
          set({ rivalsCount: state.rivalsCount + 1 });
          return;
        }
        set({
          hypotheses: {
            ...state.hypotheses,
            [hypId]: {
              hyp_id: hypId,
              statement: (data.statement as string) ?? "",
              status: "proposed",
              tests: {},
            },
          },
        });
        return;
      }
      case "angle": {
        const a = {
          angle_id: String(data.angle_id),
          score: Number(data.score ?? 0),
          chosen: Boolean(data.chosen),
          reason: String(data.reason ?? ""),
        };
        set({ angles: [...state.angles.filter((x) => x.angle_id !== a.angle_id), a] });
        return;
      }
      case "anomaly": {
        const an = data as unknown as RunUiState["anomalies"][number];
        set({ anomalies: [...state.anomalies.filter((x) => x.anomaly_id !== an.anomaly_id), an] });
        return;
      }
      case "hyp_status": {
        const hypId = data.hyp_id as string;
        const existing = state.hypotheses[hypId];
        if (!existing) return;
        set({
          hypotheses: {
            ...state.hypotheses,
            [hypId]: { ...existing, status: data.status as HypothesisCardState["status"] },
          },
        });
        return;
      }
      case "test": {
        const hypId = data.hyp_id as string;
        const existing = state.hypotheses[hypId];
        if (!existing) return;
        set({
          hypotheses: {
            ...state.hypotheses,
            [hypId]: {
              ...existing,
              tests: { ...existing.tests, [data.test_id as string]: data.passed as boolean | null },
            },
          },
        });
        return;
      }
      case "kill": {
        const hypId = data.hyp_id as string;
        const existing = state.hypotheses[hypId];
        if (!existing) return;
        set({
          hypotheses: {
            ...state.hypotheses,
            [hypId]: { ...existing, status: "killed", kill_reason: data.reason as string },
          },
        });
        return;
      }
      case "contradiction":
        set({
          contradictions: [
            ...state.contradictions,
            { type: data.type as string, claim: data.claim as string },
          ],
        });
        return;
      case "discovery":
        set({
          discoverySentence: data.sentence as string,
          discoveryLabel: data.label as string,
        });
        return;
      case "done":
        // Clears any error left over from a previous attempt on this run_id, and is itself the
        // signal that nothing went wrong: a native EventSource "error" Event fires on the stream
        // close that immediately follows "done", and must never be read as a run failure.
        set({
          done: true,
          connected: false,
          error: null,
          runtimeS: typeof data.runtime_s === "number" ? data.runtime_s : null,
        });
        return;
      case "run_error":
        set({ error: (data.message as string) ?? "unknown error", connected: false });
        return;
      default:
        return;
    }
  },
}));
