"""PDF export: print an already-written HTML file to PDF with headless Chrome (same mechanism proven
in the research deliverable's build_pdf.py across prior projects in this account). The research paper
(next_signal/paper/render.py) writes its own HTML (paper.html.j2) and calls print_html_to_pdf directly;
this module no longer renders HTML itself.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

_CHROME_CANDIDATES = [
    shutil.which("chrome"),
    shutil.which("google-chrome"),
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def _find_chrome() -> str:
    for c in _CHROME_CANDIDATES:
        if c and Path(c).exists():
            return c
    raise RuntimeError("Chrome or Edge not found; cannot render PDF export")


def print_html_to_pdf(html_path: Path, pdf_path: Path, timeout: int = 120) -> Path:
    """Prints an already-written HTML file to PDF with headless Chrome. Shared by every export path
    that needs a PDF (the research paper's render.py, and the QA report)."""
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    if pdf_path.exists():
        pdf_path.unlink()
    profile = tempfile.mkdtemp(prefix="ns-pdf-")
    try:
        cmd = [
            _find_chrome(), "--headless=new", "--disable-gpu", "--no-first-run",
            "--no-default-browser-check", f"--user-data-dir={profile}", "--no-pdf-header-footer",
            "--run-all-compositor-stages-before-draw", "--virtual-time-budget=20000",
            f"--print-to-pdf={pdf_path}", html_path.resolve().as_uri(),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    if not pdf_path.exists() or pdf_path.stat().st_size < 1000:
        raise RuntimeError(f"PDF render failed (exit {proc.returncode}): {proc.stderr[-400:]}")
    return pdf_path
