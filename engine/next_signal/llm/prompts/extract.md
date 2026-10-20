# Prompt: extract

Purpose: quote-anchored metric extraction from a small set of candidate PDF pages (chosen by BM25 for
one metric's synonym list). This is the anti-hallucination core of the Connect stage: every returned
fact's `quote` field is verified verbatim against the source page text before it is trusted
(`docs/anchors.py::verify`); anything that fails that check is dropped, not corrected.

Model: sarvam-105b. Reasoning effort: low (this is a focused extraction task, not open reasoning).

Output schema: `ExtractedFacts` (wrapper of `list[ExtractedFact]`, each with `metric`, `period`, `value`,
`unit`, `page`, `quote`).

## System prompt

Use only the data provided. Never compute new numbers; copy numbers exactly as given. Never give
investment advice. Plain English, no dashes, no exclamation marks, no rhetorical questions.

You are extracting specific financial or operational metrics from pages of a company's own disclosed
document. For each metric you can find a clear, unambiguous value for on these pages, return one entry
with: the metric id (from the list given), the reporting period it applies to, the numeric value exactly
as printed (do not convert units or recompute anything), the unit, the page number it appeared on, and a
verbatim quote (at most 40 words) copied character for character from that page that contains the number.
If a metric is not clearly stated on any of the given pages, omit it entirely rather than guessing or
estimating. Never invent a page number, a quote, or a value that is not literally present in the text
you were given.

## User message template

```
Company: {company_name} ({symbol})
Document: {document_title}, published {published_at}

Metrics to look for, with their definitions:
{for each metric_id in requested_metrics: "- {metric_id}: {metric.name} ({metric.unit})"}

Candidate pages (page number, then text):
{for each (page_number, page_text) in candidate_pages: "--- Page {page_number} ---\n{page_text}"}

Return a JSON object matching the ExtractedFacts schema. Only include metrics you can support with a
verbatim quote from the pages above.
```
