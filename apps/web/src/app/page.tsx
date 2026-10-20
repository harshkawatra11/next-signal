import { Suspense } from "react";
import { Topbar } from "@/components/layout/Topbar";
import { Footer } from "@/components/layout/Footer";
import { Masthead } from "@/components/home/Masthead";
import { RunConsole } from "@/components/home/RunConsole";
import { RecentRuns } from "@/components/home/RecentRuns";
import { UniverseGrid } from "@/components/home/UniverseGrid";
import { MethodStrip } from "@/components/home/MethodStrip";

export default function Home() {
  return (
    <>
      <Topbar />
      <main className="flex-1">
        <Masthead />
        {/* RunConsole reads the ?q= search param (set when a UniverseGrid card is clicked), which
            Next.js can only resolve at request time, so it needs a Suspense boundary to keep the
            rest of the page statically prerenderable. */}
        <Suspense fallback={<div className="border-b border-rule px-4 py-12" />}>
          <RunConsole />
        </Suspense>
        <RecentRuns />
        <UniverseGrid />
        <MethodStrip />
      </main>
      <Footer />
    </>
  );
}
