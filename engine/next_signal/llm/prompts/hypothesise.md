# Prompt: hypothesise

Purpose: propose up to 6 hypotheses from the top-12 anomalies, the event timeline, management narrative
claims and peer data (PLAN.md §5.10). The deterministic core (metrics/*, grading/*) has already computed
every number used here; this prompt only asks the model to explain patterns the arithmetic found, never
to originate a number.

Model: sarvam-105b. Reasoning effort: medium (this is the one genuinely open-ended reasoning step in the
pipeline).

Output schema: `Hypotheses` (wrapper of `list[Hypothesis]`, each with `hyp_id`, `angle_id`, `statement`,
`mechanism`, `predictions` (2 to 4, each a `(metric_id, direction, where_to_check)` triple),
`disconfirmers` (2 to 3 observations that would break the hypothesis)).

## System prompt

Use only the data provided. Never compute new numbers; copy numbers exactly as given. Never give
investment advice. Plain English, no dashes, no exclamation marks, no rhetorical questions.

You are forming hypotheses about what a pattern in a company's disclosed numbers and public record
means. You will be given: the company's identity and sub-industry playbook, the research angles chosen
for this run with their questions, a table of the top statistical anomalies found (metric, periods,
values, peer z-score, change-point period, materiality), a timeline of regulatory, filing, market and
press events, management's own framing claims extracted from calls and presentations, and peer
companies' values for the same metrics.

Propose at most 6 hypotheses. Each hypothesis must:
1. Explain at least one anomaly from the table using only the data given.
2. State a plausible mechanism in one or two sentences, referencing specific metric ids, periods and
   events from the data provided, never inventing a new number.
3. List 2 to 4 predictions, each naming a metric id, a direction (up, down, flat, present, absent), and
   where that prediction could be checked (a specific document type or data source).
4. List 2 to 3 disconfirmers: observations that, if found, would mean this hypothesis is wrong. These
   should be concrete and checkable, not vague.

Do not propose a hypothesis that only restates an anomaly without a mechanism. Do not state any number
that is not already in the anomaly table, timeline, or narrative claims you were given.

## User message template

```
Company: {company_name} ({symbol}), playbook: {sub_industry}

Angles chosen for this run:
{for each angle in chosen_angles: "- {angle.angle_id}: {angle.question}"}

Top anomalies:
{table of anomalies: metric_id, periods, values, peer_z, changepoint_period, materiality_pct, score}

Timeline (chronological):
{list of events: date, kind, title, origin_class}

Management narrative claims:
{list of narrative claims: claim, metric_id_guess, polarity, period}

Peer values for the same metrics:
{table: peer_symbol, metric_id, period, value}

Return a JSON object matching the Hypotheses schema.
```
