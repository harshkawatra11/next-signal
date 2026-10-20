import { RunView } from "./RunView";

// This route is a live SSE view keyed by a dynamic run id; it can never be meaningfully
// prerendered, so Next 16's Cache Components model needs this opt-out explicitly. It must live in
// this server component file (route-segment config exports are not allowed in a "use client" file);
// all client-only logic lives in RunView.
export const instant = false;

export default async function RunPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  return <RunView runId={runId} />;
}
