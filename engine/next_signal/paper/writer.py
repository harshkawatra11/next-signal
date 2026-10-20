"""The writer: asks Sarvam (via the shared router) to turn a PaperSpec's facts into prose, checks
every section against the plain-language and no-invented-number guards, repairs once, and falls back
to the deterministic paragraphs (fallback.py) for any section that still fails.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

import httpx
from pydantic import BaseModel

from ..config import settings
from ..llm import guards
from ..llm import router as R
from ..schemas import Report
from . import fallback
from .spec import PaperSpec, build_spec

_PROMPT_PATH = Path(__file__).resolve().parents[1] / "llm" / "prompts" / "write_paper.md"
SECTIONS = ["abstract", "introduction", "company_and_data", "findings", "explanations", "outlook", "conclusion"]

_IDENT_RE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
_OPERATOR_RE = re.compile(r"(<=|>=|==|!=|\s[<>]\s)")
_INTERNAL_ID_RE = re.compile(r"\b(?:H|P|T|EV|N|C|D)\d{1,2}\b")
_SOFTWARE_RE = re.compile(r"\b(the run|pipeline|language model|LLM|algorithm|the engine|angle|stage)\b", re.I)
_DASH_RE = re.compile("[–—]")
_CITE_RE = re.compile(r"\[(\d+)\]")


class PaperText(BaseModel):
    title: str
    abstract: str
    introduction: list[str]
    company_and_data: list[str]
    findings: list[str]
    explanations: list[str]
    outlook: list[str]
    conclusion: list[str]


class PaperTextPartial(BaseModel):
    """Repair-call output type: only the sections flagged with issues need to be present."""

    title: Optional[str] = None
    abstract: Optional[str] = None
    introduction: Optional[list[str]] = None
    company_and_data: Optional[list[str]] = None
    findings: Optional[list[str]] = None
    explanations: Optional[list[str]] = None
    outlook: Optional[list[str]] = None
    conclusion: Optional[list[str]] = None


def _word_count(text: str) -> int:
    return len(text.split())


def check_section(text: str, spec: PaperSpec, *, is_abstract: bool = False) -> list[str]:
    """Returns a list of human-readable issues; an empty list means the section passes."""
    issues: list[str] = []
    stray = guards.stray_numbers(text, spec.allowed_numbers)
    if stray:
        issues.append(f"numbers not in the allowed set: {', '.join(stray)}")
    if _IDENT_RE.search(text):
        issues.append("contains a snake_case identifier")
    if _OPERATOR_RE.search(text):
        issues.append("contains a comparison operator")
    if _INTERNAL_ID_RE.search(text):
        issues.append("contains an internal id (H/P/T/EV/N/C/D plus digits)")
    if _SOFTWARE_RE.search(text):
        issues.append("talks about the software itself")
    for n in _CITE_RE.findall(text):
        if int(n) > len(spec.references):
            issues.append(f"citation [{n}] has no matching reference")
    copy_problems = guards.copy_issues(text)
    if copy_problems:
        issues.extend(copy_problems)
    if _DASH_RE.search(text):
        issues.append("contains a dash character")
    words = _word_count(text)
    if is_abstract:
        if not (90 <= words <= 200):
            issues.append(f"abstract word count {words} is outside 90 to 200")
    else:
        for para in text.split("\n\n"):
            if _word_count(para) > 170:
                issues.append("a paragraph exceeds 170 words")
                break
    return issues


def _issues_for_text(spec: PaperSpec, section: str, text: str) -> list[str]:
    return check_section(text, spec, is_abstract=(section == "abstract"))


def _issues_for_paragraphs(spec: PaperSpec, section: str, paragraphs: list[str]) -> list[str]:
    issues: list[str] = []
    for p in paragraphs:
        issues.extend(check_section(p, spec, is_abstract=False))
    return issues


def _build_messages(spec: PaperSpec, report: Report) -> list[dict]:
    system = _PROMPT_PATH.read_text(encoding="utf-8")
    lines: list[str] = []
    lines.append(f"Company: {spec.company}")
    lines.append(f"Sector: {spec.sector_phrase}")
    lines.append(f"Financial data as of: {spec.as_of}")
    lines.append(f"A finding survived the checks: {'yes' if spec.has_finding else 'no'}")
    for key in ("intro", "company", "findings", "explanations", "outlook"):
        lines.append(f"\nFacts for {key}:")
        for f in spec.facts.get(key, []):
            cites = " ".join(f"[{c}]" for c in f.cite)
            lines.append(f"- {f.text}{(' ' + cites) if cites else ''}")
    lines.append("\nFigures and tables available to refer to by number:")
    for t in spec.tables:
        lines.append(f"- Table {t.number}. {t.caption}")
    for fg in spec.figures:
        lines.append(f"- Figure {fg.number}. {fg.caption}")
    lines.append(f"\nAllowed reference numbers: {', '.join(str(r.number) for r in spec.references)}")
    user = "\n".join(lines)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _section_to_fallback(spec: PaperSpec, section: str) -> list[str] | str:
    mapping = {
        "abstract": fallback.abstract,
        "introduction": fallback.introduction,
        "company_and_data": fallback.company_and_data,
        "findings": fallback.findings,
        "explanations": fallback.explanations,
        "outlook": fallback.outlook,
        "conclusion": fallback.conclusion,
    }
    return mapping[section](spec)


def _cache_path(report: Report) -> Path:
    return settings.db_path.parent / "exports" / report.meta.run_id / "paper.json"


async def ensure_paper_text(report: Report) -> PaperText:
    cache = _cache_path(report)
    if cache.exists():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            return PaperText.model_validate({k: v for k, v in data.items() if k in PaperText.model_fields})
        except Exception:
            pass

    spec = build_spec(report)
    sources: dict[str, str] = {}
    sections: dict[str, object] = {}
    title = None

    try:
        client = httpx.AsyncClient(timeout=180)
        try:
            messages = _build_messages(spec, report)
            text = await R.llm_json(client, None, report.meta.run_id, "write_paper", messages, PaperText, effort="medium")
            provider = getattr(R, "RECENT", [{}])[-1].get("provider", "") if getattr(R, "RECENT", None) else ""
            title = text.title
            for s in SECTIONS:
                sections[s] = getattr(text, s)
                sources[s] = provider or "sarvam"

            # Guard every section; collect issues per section for one repair pass.
            section_issues: dict[str, list[str]] = {}
            for s in SECTIONS:
                val = sections[s]
                issues = _issues_for_text(spec, s, val) if isinstance(val, str) else _issues_for_paragraphs(spec, s, val)
                if issues:
                    section_issues[s] = issues

            if section_issues:
                repair_lines = ["The following sections have issues and must be rewritten. Return JSON with only these keys, each in the same shape as before (abstract is a string, the rest are lists of paragraphs)."]
                for s, issues in section_issues.items():
                    repair_lines.append(f"\n{s}: {'; '.join(issues)}")
                repair_messages = messages + [
                    {"role": "assistant", "content": json.dumps(text.model_dump())},
                    {"role": "user", "content": "\n".join(repair_lines)},
                ]
                try:
                    repaired = await R.llm_json(client, None, report.meta.run_id, "write_paper_repair", repair_messages, PaperTextPartial, effort="medium")
                    for s in list(section_issues.keys()):
                        val = getattr(repaired, s, None)
                        if val is None:
                            continue
                        issues = _issues_for_text(spec, s, val) if isinstance(val, str) else _issues_for_paragraphs(spec, s, val)
                        if not issues:
                            sections[s] = val
                            section_issues.pop(s, None)
                except Exception:
                    pass

            for s in list(section_issues.keys()):
                sections[s] = _section_to_fallback(spec, s)
                sources[s] = "fallback"
        finally:
            await client.aclose()
    except Exception:
        for s in SECTIONS:
            sections[s] = _section_to_fallback(spec, s)
            sources[s] = "fallback"
        title = fallback.title(spec)

    if title is None:
        title = fallback.title(spec)

    out = PaperText(
        title=title,
        abstract=sections["abstract"] if isinstance(sections["abstract"], str) else "\n\n".join(sections["abstract"]),
        introduction=sections["introduction"] if isinstance(sections["introduction"], list) else [sections["introduction"]],
        company_and_data=sections["company_and_data"] if isinstance(sections["company_and_data"], list) else [sections["company_and_data"]],
        findings=sections["findings"] if isinstance(sections["findings"], list) else [sections["findings"]],
        explanations=sections["explanations"] if isinstance(sections["explanations"], list) else [sections["explanations"]],
        outlook=sections["outlook"] if isinstance(sections["outlook"], list) else [sections["outlook"]],
        conclusion=sections["conclusion"] if isinstance(sections["conclusion"], list) else [sections["conclusion"]],
    )

    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        payload = out.model_dump()
        payload["sources"] = sources
        cache.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        pass

    return out
