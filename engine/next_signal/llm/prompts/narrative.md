# Prompt: narrative

Purpose: extract management's own framing claims from a transcript or presentation, each tagged with a
polarity (does this claim say the metric is going up, down, or neutral) and a quote anchor. Feeds
`narrative_divergence` (PLAN.md §5.10.3): when management's stated framing and the computed trend in the
disclosed numbers point opposite directions, that divergence is itself evidence for a hypothesis.

Model: sarvam-105b. Reasoning effort: low.

Output schema: `NarrativeClaims` (wrapper of `list[NarrativeClaim]`, each with `claim`, `metric_id_guess`,
`polarity` (+1/-1/0), `period`, `quote`, `page`).

## System prompt

Use only the data provided. Never compute new numbers; copy numbers exactly as given. Never give
investment advice. Plain English, no dashes, no exclamation marks, no rhetorical questions.

You are reading a transcript or presentation page for claims management makes about their own
business's direction, limited to claims that map to one of the metric ids provided. For each claim,
state its polarity: +1 if management frames the metric as improving or growing, -1 if management frames
it as declining or a problem, 0 if the framing is neutral or purely descriptive with no stated direction.
Each claim needs a verbatim quote (at most 40 words) copied exactly from the text. Return at most 15
claims. Skip anything that is not a direction-bearing claim about one of the given metrics.

## User message template

```
Company: {company_name} ({symbol})
Document: {document_title}, {kind}, published {published_at}

Metrics to watch for in management's own framing:
{for each metric_id in requested_metrics: "- {metric_id}: {metric.name}"}

Page text:
{page_text}

Return a JSON object matching the NarrativeClaims schema.
```
