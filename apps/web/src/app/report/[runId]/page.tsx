import { ReportView } from "./ReportView";

// Same reasoning as /run/[runId]: a live, run-specific report cannot be meaningfully prerendered.
export const instant = false;

export default async function ReportPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  return <ReportView runId={runId} />;
}
