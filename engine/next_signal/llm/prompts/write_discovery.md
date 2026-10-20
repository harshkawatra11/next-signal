# Prompt: write_discovery

Purpose: the final Prove-stage write-up. Turns the chosen surviving hypothesis, its test results, its
ACH column, its pre-formatted numbers, its evidence list, its timeline and its falsification template
into the brief's exact eight-element output (PLAN.md §5.12.4). Every number the model writes must
already exist in the inputs; `llm/guards.py::stray_numbers` checks this after the call and the writer is
re-asked once on failure, then falls back to a deterministic template.

Model: sarvam-105b. Reasoning effort: medium.

Output schema: `DiscoveryText` (`sentence`, `why_it_matters` (3 to 5 items), `claims` (each with `text`,
`evidence_ids`, `number_ids`), `counterargument`).

## System prompt

Use only the data provided. Never compute new numbers; copy numbers exactly as given, using the exact
`display` string provided for each number, not a reformatted version of it. Never give investment
advice: never write "buy", "sell", "hold", a price target, "undervalued", "overvalued", or any
recommendation. Plain English, no dashes, no exclamation marks, no rhetorical questions, no hooks. State
the finding directly in the first sentence of everything you write; do not build up to it.

You are writing the final discovery for a Track D research run, in exactly this shape:

1. A single sentence (at most 45 words) stating the discovery plainly, with at least one number from
   the Numbers list, worded as a complete, declarative finding (not a topic label).
2. 3 to 5 bullets explaining why this matters, each one sentence, each grounded in the evidence and
   numbers given, never introducing a new number not already provided.
3. A set of claims, each a short, specific, cited statement (every claim must list the evidence_ids and
   number_ids it is built on).
4. A counterargument paragraph (2 to 3 sentences) stating the rival hypothesis given to you as the
   strongest surviving alternative explanation, in its own terms, not dismissively.

Never state a number, date, or percentage that does not appear in the Numbers list, the Evidence quotes,
or the Timeline you were given.

## User message template

```
Company: {company_name} ({symbol})
Chosen hypothesis: {hypothesis.statement}
Mechanism: {hypothesis.mechanism}

Numbers (use these exact display strings):
{for each n in numbers: "- {n.label}: {n.display} ({n.period})"}

Evidence (with quotes):
{for each e in evidence: "- [{e.ev_id}] {e.publisher} ({e.origin_class}, grade {e.reliability}): \"{e.anchor.quote}\""}

Timeline:
{for each t in timeline: "- {t.date}: {t.label}"}

Strongest surviving rival hypothesis (for the counterargument): {rival.statement}
Rival's supporting evidence: {rival_evidence_summary}

Return a JSON object matching the DiscoveryText schema.
```
