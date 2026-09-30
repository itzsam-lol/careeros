"""LaTeX helpers: escaping, engine compatibility, sandboxed compilation and page counting."""

from __future__ import annotations

import asyncio
import io
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from careeros.core.errors import CareerOSError

_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}
_ESCAPE_RE = re.compile("|".join(re.escape(k) for k in _ESCAPES))

# Typographic characters that 8-bit fonts (T1 + charter, etc.) cannot show under XeTeX.
_PUNCTUATION = {
    "\u2019": "'",
    "\u2018": "`",
    "\u201c": "``",
    "\u201d": "''",
    "\u2013": "--",
    "\u2014": "---",
    "\u2026": r"\ldots{}",
    "\u00a0": "~",
}

# pdfTeX-only primitives some templates use to make PDFs copy-paste friendly.
_GLYPH_TO_UNICODE = re.compile(r"\\input\{glyphtounicode\}\s*\\pdfgentounicode\s*=\s*1")
_GUARDED = r"\ifdefined\pdfgentounicode\input{glyphtounicode}\pdfgentounicode=1\fi"


class LatexError(CareerOSError):
    """The resume could not be compiled."""

    code = "latex_failed"
    http_status = 422


def escape(text: str) -> str:
    """Escape plain text for use inside a LaTeX document."""
    return normalize_punctuation(_ESCAPE_RE.sub(lambda m: _ESCAPES[m.group(0)], text))


def normalize_punctuation(tex: str) -> str:
    for char, replacement in _PUNCTUATION.items():
        tex = tex.replace(char, replacement)
    return tex


def make_portable(tex: str) -> str:
    """Make a pdfLaTeX template compile unchanged under XeTeX/Tectonic too."""
    tex = _GLYPH_TO_UNICODE.sub(lambda _m: _GUARDED, tex)
    return normalize_punctuation(tex)


def page_count(pdf: bytes) -> int:
    return len(PdfReader(io.BytesIO(pdf)).pages)


def pdf_text(pdf: bytes) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf)).pages)


@dataclass(frozen=True, slots=True)
class CompileResult:
    pdf: bytes
    pages: int
    engine: str
    log_tail: str


def find_engine(preference: str = "auto") -> tuple[str, list[str]] | None:
    """Return (name, argv-prefix) for the first available engine; the file name is appended."""
    candidates = {
        "tectonic": ["tectonic", "-X", "compile", "--untrusted", "--keep-logs"],
        "xelatex": ["xelatex", "-interaction=nonstopmode", "-halt-on-error", "-no-shell-escape"],
        "lualatex": ["lualatex", "-interaction=nonstopmode", "-halt-on-error", "-no-shell-escape"],
        "pdflatex": ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "-no-shell-escape"],
    }
    order = list(candidates) if preference == "auto" else [preference]
    extra = os.environ.get("CAREEROS_LATEX_BIN_DIR")
    for name in order:
        binary = shutil.which(name) or (shutil.which(name, path=extra) if extra else None)
        if binary:
            return name, [binary, *candidates[name][1:]]
    return None


async def compile_tex(
    tex: str, *, engine: str = "auto", time_limit: float = 240.0
) -> CompileResult:
    """Compile `tex` in a throwaway directory. Shell escape is disabled for every engine."""
    found = find_engine(engine)
    if found is None:
        raise LatexError("No LaTeX engine is installed (tectonic, xelatex, lualatex or pdflatex)")
    name, argv = found
    with tempfile.TemporaryDirectory(prefix="careeros-tex-") as tmp:
        src = Path(tmp) / "resume.tex"
        src.write_text(make_portable(tex), encoding="utf-8")
        proc = await asyncio.create_subprocess_exec(
            *argv,
            src.name,
            cwd=tmp,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            output, _ = await asyncio.wait_for(proc.communicate(), timeout=time_limit)
        except TimeoutError as exc:
            proc.kill()
            raise LatexError("LaTeX compilation timed out") from exc
        log = output.decode("utf-8", "replace")
        pdf_path = Path(tmp) / "resume.pdf"
        if proc.returncode != 0 or not pdf_path.exists():
            raise LatexError(
                "LaTeX compilation failed", details={"engine": name, "log": _tail(log)}
            )
        pdf = pdf_path.read_bytes()
    return CompileResult(pdf=pdf, pages=page_count(pdf), engine=name, log_tail=_tail(log))


def _tail(log: str, lines: int = 40) -> str:
    kept = [line for line in log.splitlines() if not line.startswith("note: downloading")]
    return "\n".join(kept[-lines:])
