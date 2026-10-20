"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { Topbar } from "@/components/layout/Topbar";
import { Footer } from "@/components/layout/Footer";
import { Container } from "@/components/system/Container";
import { Kicker } from "@/components/system/Kicker";
import { KpiBand } from "@/components/system/KpiBand";
import { BarRanked } from "@/components/viz/BarRanked";
import { ChartCard } from "@/components/viz/ChartCard";
import { StageRail } from "@/components/run/StageRail";
import { SourceTicker } from "@/components/run/SourceTicker";
import { HypothesisBoard } from "@/components/run/HypothesisBoard";
import { Button } from "@/components/ui/button";
import { useRunStore } from "@/store/run";
import { subscribeToRun } from "@/lib/sse";
import { getRunMeta } from "@/lib/api";
import { fmtDateIN, fmtDuration } from "@/lib/format";

export function RunView({ runId }: { runId: string }) {
  const router = useRouter();
  const reset = useRunStore((s) => s.reset);
  const applyEvent = useRunStore((s) => s.applyEvent);
  const done = useRunStore((s) => s.done);
  const error = useRunStore((s) => s.error);
  const discoverySentence = useRunStore((s) => s.discoverySentence);
  const discoveryLabel = useRunStore((s) => s.discoveryLabel);
  const contradictions = useRunStore((s) => s.contradictions);
  const fetchCount = useRunStore((s) => s.fetchCount);
  const documentsCount = useRunStore((s) => s.documentsCount);
  const factsCount = useRunStore((s) => s.factsCount);
  const angles = useRunStore((s) => s.angles);
  const anomalies = useRunStore((s) => s.anomalies);
  const hypotheses = useRunStore((s) => s.hypotheses);
  const rivalsCount = useRunStore((s) => s.rivalsCount);
  const runtimeS = useRunStore((s) => s.runtimeS);

  const { data: meta } = useSWR(["meta", runId], () => getRunMeta(runId), {
    refreshInterval: done ? 0 : 5000,
  });

  const [elapsed, setElapsed] = useState(0);
  const [hold, setHold] = useState(false);

  useEffect(() => {
    reset(runId);
    const unsubscribe = subscribeToRun(runId, applyEvent);
    return unsubscribe;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  useEffect(() => {
    if (done) return;
    const t0 = Date.now();
    const id = setInterval(() => setElapsed(Math.round((Date.now() - t0) / 1000)), 1000);
    return () => clearInterval(id);
  }, [done]);

  useEffect(() => {
    if (done && !hold) {
      const t = setTimeout(() => router.push(`/report/${runId}`), 4000);
      return () => clearTimeout(t);
    }
  }, [done, hold, runId, router]);

  const hypCards = Object.values(hypotheses);
  const killedCount = hypCards.filter((c) => c.status === "killed").length;
  const symbolGuess = runId.split("-")[0];

  return (
    <>
      <Topbar />
      <Container className="flex-1 py-10">
        <Kicker>Live run // {runId}</Kicker>
        <h1 className="mt-3 text-h1 font-serif leading-h1">
          Investigating {meta?.company ?? symbolGuess}
        </h1>
        <p className="mt-2 text-small text-ink-3">
          As of {meta ? fmtDateIN(meta.as_of) : "-"}. Elapsed {fmtDuration(elapsed)}.
        </p>

        {error && (
          <div className="mt-6 border border-signal p-4 text-small text-signal">
            The run stopped: {error}
          </div>
        )}

        <div className="mt-6">
          <KpiBand
            items={[
              { label: "Requests", value: String(fetchCount) },
              { label: "Documents", value: String(documentsCount) },
              { label: "Verified facts", value: String(factsCount) },
              { label: "Angles", value: String(angles.length) },
              { label: "Anomalies", value: String(anomalies.length) },
              {
                label: "Hypotheses",
                value: String(hypCards.length),
                sub: rivalsCount > 0 ? `+ ${rivalsCount} rivals` : undefined,
              },
              { label: "Killed", value: String(killedCount) },
            ]}
          />
        </div>

        <div className="mt-6">
          <StageRail />
        </div>

        <div className="mt-6 grid gap-5 md:grid-cols-2">
          <div className="space-y-5">
            <SourceTicker />
            <ChartCard title="Where the agent looked">
              {angles.length === 0 ? (
                <p className="text-small text-ink-3">Waiting for Discover…</p>
              ) : (
                <BarRanked
                  data={[...angles]
                    .sort((a, b) => b.score - a.score)
                    .map((a) => ({ label: a.angle_id, value: a.score, highlight: a.chosen }))}
                />
              )}
            </ChartCard>
          </div>
          <div className="space-y-5">
            <ChartCard title="What changed">
              {anomalies.length === 0 ? (
                <p className="text-small text-ink-3">Waiting for Calculate…</p>
              ) : (
                <BarRanked
                  data={[...anomalies]
                    .sort((a, b) => b.score - a.score)
                    .map((a) => ({ label: a.label ?? a.metric_id.replace(/_/g, " "), value: a.score }))}
                />
              )}
            </ChartCard>
            <HypothesisBoard />
          </div>
        </div>

        {contradictions.length > 0 && (
          <div className="mt-6 border border-rule p-5">
            <h3 className="text-label font-mono font-semibold uppercase tracking-[0.1em] text-ink-3">
              Contradictions found
            </h3>
            <ul className="mt-2 space-y-1 text-small text-ink-2">
              {contradictions.map((c, i) => (
                <li key={i}>
                  <span className="font-mono text-label uppercase text-signal">{c.type}</span>{" "}
                  {c.claim}
                </li>
              ))}
            </ul>
          </div>
        )}

        {done && (
          <div
            className="mt-6 border-2 border-ink p-6"
            onMouseEnter={() => setHold(true)}
          >
            <p className="text-label font-mono font-semibold uppercase tracking-[0.1em] text-signal">
              Run complete
            </p>
            <p className="mt-2 text-h3 font-serif leading-snug">
              Finished in {fmtDuration(runtimeS ?? elapsed)}.{" "}
              {discoverySentence
                ? "A finding survived the challenge."
                : "No finding survived the challenge."}
            </p>
            {discoverySentence && (
              <p className="mt-2 text-small text-ink-2">
                {discoverySentence} ({discoveryLabel})
              </p>
            )}
            <Button
              className="mt-4 bg-signal text-white hover:bg-signal-deep"
              onClick={() => router.push(`/report/${runId}`)}
            >
              Open the case file
            </Button>
          </div>
        )}
      </Container>
      <Footer />
    </>
  );
}
