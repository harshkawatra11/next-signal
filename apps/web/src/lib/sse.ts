import { API_BASE } from "@/lib/api";

export interface RunEvent {
  seq: number;
  type: string;
  data: Record<string, unknown>;
}

export type RunEventHandler = (ev: RunEvent) => void;

/**
 * Opens an EventSource against /api/runs/{id}/events and dispatches every named event type the
 * engine emits: stage, source_fetch, doc_parsed, fact, anomaly, angle, hypothesis, test, kill,
 * hyp_status, contradiction, llm, discovery, done, run_error. Returns a cleanup function.
 *
 * Note on "run_error" vs the browser's native "error" event: the engine's own failure event is
 * named "run_error" on the wire, specifically so it never collides with EventSource's built-in
 * "error" Event, which fires on every connection close for any reason, including a normal close
 * after "done". That native event is not a MessageEvent (no e.data), so it must never be parsed
 * as JSON or treated as a run failure; es.onerror below only logs it.
 */
export function subscribeToRun(runId: string, onEvent: RunEventHandler, afterSeq = 0): () => void {
  const url = new URL(`/api/runs/${runId}/events`, API_BASE);
  if (afterSeq > 0) url.searchParams.set("after", String(afterSeq));
  const es = new EventSource(url.toString());

  const types = [
    "stage", "source_fetch", "doc_parsed", "fact", "anomaly", "angle", "hypothesis",
    "test", "kill", "hyp_status", "contradiction", "llm", "discovery", "done", "run_error",
  ];

  const listeners: Array<[string, (e: MessageEvent) => void]> = types.map((type) => {
    const handler = (e: MessageEvent) => {
      let data: Record<string, unknown> = {};
      try {
        data = JSON.parse(e.data);
      } catch {
        // malformed payload; surface as an empty-data event rather than throwing inside the listener
      }
      onEvent({ seq: Number(e.lastEventId) || 0, type, data });
      // Close explicitly on terminal events so the native EventSource does not auto-reconnect and
      // replay the whole stream from the server's own replay buffer (observed hitting /events three
      // times for a single run before this fix).
      if (type === "done" || type === "run_error") es.close();
    };
    es.addEventListener(type, handler);
    return [type, handler];
  });

  es.onerror = () => {
    // This fires on every connection close, including the normal close after "done"/"run_error"
    // above, and on transient network blips that EventSource will retry on its own. It is never
    // synthesized into a run_error here; only a genuinely dead, non-retrying connection is worth
    // logging, and even then the caller's "done"/"run_error" handlers remain the only source of
    // truth for run outcome.
    if (es.readyState === EventSource.CLOSED) {
      console.warn(`[sse] connection to run ${runId} closed`);
    }
  };

  return () => {
    for (const [type, handler] of listeners) es.removeEventListener(type, handler);
    es.close();
  };
}
