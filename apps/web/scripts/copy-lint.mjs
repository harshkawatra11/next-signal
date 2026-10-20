// Scans src/**/*.{tsx,ts,mdx} string literals and JSX text for em/en dashes used as punctuation,
// exclamation marks in UI copy, and the banned AI-slop word list (PLAN.md §0.5, §6.9). Lines carrying
// a `// copy-lint-ignore` comment are skipped (for code identifiers that happen to contain a banned
// substring, e.g. an import path containing "harness").
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, extname } from "node:path";

const BAN = [
  "delve", "tapestry", "game-changer", "revolutioni", "cutting-edge", "seamless", "leverage",
  "unlock", "empower", "in today's", "it's important to note", "in conclusion", "holistic",
  "synergy", "paradigm", "imagine", "what if", "let's", "groundbreaking", "state-of-the-art",
  "supercharge", "harness the", "harnessing", "elevate", "journey", "world-class", "next-gen",
  // "harness" alone is not banned: "evaluation harness" / "eval.harness" is our own correct
  // technical term (standard testing vocabulary), not the AI-cliche "harness the power of...".
];

const ROOT = join(import.meta.dirname, "..", "src");
// shadcn's generated primitives (src/components/ui/**) are vendor code we don't author, and they
// legitimately use Tailwind's "!important" modifier suffix (e.g. "rounded-xl!"), which the
// exclamation check below cannot distinguish from an English exclamation mark. Skip that directory;
// everything we actually write (copy, content, logic) lives outside it.
const SKIP_DIR = join(ROOT, "components", "ui");
const hits = [];

function walk(dir) {
  for (const f of readdirSync(dir)) {
    const p = join(dir, f);
    if (statSync(p).isDirectory()) {
      if (p === SKIP_DIR) continue;
      walk(p);
      continue;
    }
    if (![".tsx", ".ts", ".mdx"].includes(extname(p))) continue;
    const src = readFileSync(p, "utf8");
    const lines = src.split("\n");
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      if (line.includes("copy-lint-ignore")) continue;
      if (/[—–]/.test(line)) hits.push([p, i + 1, "dash", line.trim().slice(0, 80)]);
      if (/[A-Za-z]\.\.\.(["'`<\s]|$)/.test(line)) hits.push([p, i + 1, "ellipsis", line.trim().slice(0, 80)]);
      if (/[A-Za-z]!(\s|["'`]|$)/.test(line) && !line.includes("!==") && !line.includes("!=")) {
        hits.push([p, i + 1, "exclamation", line.trim().slice(0, 80)]);
      }
      const low = line.toLowerCase();
      for (const b of BAN) {
        if (low.includes(b)) hits.push([p, i + 1, "banned:" + b, line.trim().slice(0, 80)]);
      }
    }
  }
}

walk(ROOT);
console.log("copy hits:", JSON.stringify(hits));
process.exit(hits.length ? 1 : 0);
