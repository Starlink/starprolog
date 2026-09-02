from __future__ import annotations

__all__ = ("extract_adamsse_prologues",)

import re

from .models import (
    Diagnostic,
    DiagnosticSeverity,
    PrologueKind,
    PrologueMarker,
    PrologueSyntax,
    SourceSpan,
)
from .raw import LocatedLine, RawPrologue

_FORTRAN_START_RE = re.compile(
    r"^\s*(?P<comment>[*Cc#])\+\s*(?P<name>[A-Za-z_][A-Za-z0-9_$]*)"
    r"\s*(?:-\s*(?P<purpose>.*))?$"
)
_FORTRAN_HEADING_RE = re.compile(r"^\s*[*Cc#]\s+(?P<title>[A-Za-z][A-Za-z -]*?)\s*:\s*$")
_FORTRAN_MODULE_RE = re.compile(
    r"^\s{6}(?P<type>SUBROUTINE|(?:[A-Za-z][A-Za-z0-9* ]*\s+)?FUNCTION|BLOCK\s+DATA)\b",
    re.IGNORECASE,
)
_FORTRAN_END_RE = re.compile(r"^\s*[*Cc#]-.*$")

_C_START_RE = re.compile(
    r"^\s*/\*[+=]\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"\s*(?:-\s*(?P<purpose>.*?))?\s*\*/\s*$"
)
_C_FIRST_HEADING_RE = re.compile(r"^\s*/\*\s*(?P<title>[A-Za-z][A-Za-z -]*?)\s*:\s*$")
_C_HEADING_RE = re.compile(r"^\s+(?P<title>[A-Z][A-Za-z -]*?)\s*:\s*$")
_C_END_RE = re.compile(r"^\s*\*/\s*$")

_TITLE_ALIASES = {
    "author": "Authors",
    "deficiencies": "Implementation Deficiencies",
    "method": "Algorithm",
    "parameters": "Arguments",
}
_FORTRAN_TERMINATORS = {
    "export",
    "external references",
    "function declarations",
    "global constants",
    "global data",
    "global variables",
    "import",
    "import-export",
    "internal references",
    "local constants",
    "local data",
    "local variables",
    "status",
    "type definitions",
}


def extract_adamsse_prologues(
    text: str,
    source: str,
) -> tuple[list[RawPrologue], list[Diagnostic]]:
    """Extract old ADAM/SSE Fortran and BDK-style C prologues.

    Parameters
    ----------
    text
        Complete source text.
    source
        Source name used in model locations and diagnostics.

    Returns
    -------
    prologues : `list` [`RawPrologue`]
        Legacy prologues normalized for the shared structural parser.
    diagnostics : `list` [`Diagnostic`]
        Non-fatal problems encountered while reading the source.
    """
    lines = text.splitlines()
    fortran, fortran_diagnostics = _extract_fortran(lines, source)
    c_prologues, c_diagnostics = _extract_c(lines, source)
    prologues = sorted(fortran + c_prologues, key=lambda item: item.source.start_line)
    return prologues, fortran_diagnostics + c_diagnostics


def _extract_fortran(
    lines: list[str],
    source: str,
) -> tuple[list[RawPrologue], list[Diagnostic]]:
    prologues: list[RawPrologue] = []
    diagnostics: list[Diagnostic] = []
    c_block_lines = _c_block_lines(lines)
    index = 0
    while index < len(lines):
        match = _FORTRAN_START_RE.fullmatch(lines[index])
        if match is None or c_block_lines[index]:
            index += 1
            continue

        start = index + 1
        normalized = _identity_sections(
            match.group("name"),
            match.group("purpose") or "",
            start,
        )
        end = start
        terminated = False
        index += 1

        while index < len(lines):
            number = index + 1
            line = lines[index]
            if _FORTRAN_END_RE.fullmatch(line):
                end = number
                terminated = True
                index += 1
                break

            heading = _FORTRAN_HEADING_RE.fullmatch(line)
            if heading is not None:
                title = heading.group("title").strip()
                if _title_key(title) in _FORTRAN_TERMINATORS:
                    end = max(start, number - 1)
                    terminated = True
                    break
                normalized.append(LocatedLine(number=number, text=f"  {_normalize_title(title)}:"))
            else:
                module = _FORTRAN_MODULE_RE.match(line)
                if module is not None:
                    normalized.extend(
                        (
                            LocatedLine(number=number, text="  Type of Module:"),
                            LocatedLine(number=number, text=f"     {module.group('type').strip()}"),
                        )
                    )
                elif line and line[0] in "*Cc#":
                    content = line[1:].rstrip()
                    if content.strip().casefold() != "endhistory":
                        normalized.append(_content_line(number, content))
            end = number
            index += 1

        if not terminated:
            diagnostics.append(
                Diagnostic(
                    severity=DiagnosticSeverity.WARNING,
                    code="unterminated-adamsse-prologue",
                    message="Old ADAM/SSE prologue reached end of file without a terminator.",
                    source=SourceSpan(path=source, start_line=start, end_line=end),
                )
            )
        prologues.append(
            RawPrologue(
                marker=PrologueMarker(
                    comment_character=match.group("comment"),
                    delimiter_width=1,
                    kind=PrologueKind.STANDARD,
                ),
                syntax=PrologueSyntax.ADAMSSE_FORTRAN,
                source=SourceSpan(path=source, start_line=start, end_line=end),
                lines=tuple(normalized),
            )
        )

    return prologues, diagnostics


def _extract_c(
    lines: list[str],
    source: str,
) -> tuple[list[RawPrologue], list[Diagnostic]]:
    prologues: list[RawPrologue] = []
    diagnostics: list[Diagnostic] = []
    index = 0
    while index < len(lines):
        match = _C_START_RE.fullmatch(lines[index])
        if match is None:
            index += 1
            continue

        start = index + 1
        normalized = _identity_sections(
            match.group("name"),
            match.group("purpose") or "",
            start,
        )
        end = start
        search = index + 1
        body_start: int | None = None
        first_heading: re.Match[str] | None = None
        while search < len(lines):
            if _C_START_RE.fullmatch(lines[search]) is not None:
                break
            first_heading = _C_FIRST_HEADING_RE.fullmatch(lines[search])
            if first_heading is not None:
                body_start = search
                break
            search += 1

        if body_start is not None and first_heading is not None:
            normalized.append(
                LocatedLine(
                    number=body_start + 1,
                    text=f"  {_normalize_title(first_heading.group('title'))}:",
                )
            )
            search = body_start + 1
            terminated = False
            while search < len(lines):
                number = search + 1
                line = lines[search]
                if _C_END_RE.fullmatch(line):
                    end = number
                    terminated = True
                    search += 1
                    break
                heading = _C_HEADING_RE.fullmatch(line)
                if heading is not None:
                    normalized.append(
                        LocatedLine(
                            number=number,
                            text=f"  {_normalize_title(heading.group('title'))}:",
                        )
                    )
                else:
                    normalized.append(_content_line(number, _strip_c_content(line)))
                end = number
                search += 1
            if not terminated:
                diagnostics.append(
                    Diagnostic(
                        severity=DiagnosticSeverity.WARNING,
                        code="unterminated-adamsse-c-prologue",
                        message="Old ADAM/SSE C prologue reached end of file without a terminator.",
                        source=SourceSpan(path=source, start_line=start, end_line=end),
                    )
                )
            index = search
        else:
            index += 1

        prologues.append(
            RawPrologue(
                marker=PrologueMarker(
                    comment_character="*",
                    delimiter_width=1,
                    kind=PrologueKind.STANDARD,
                ),
                syntax=PrologueSyntax.ADAMSSE_C,
                source=SourceSpan(path=source, start_line=start, end_line=end),
                lines=tuple(normalized),
            )
        )

    return prologues, diagnostics


def _identity_sections(name: str, purpose: str, number: int) -> list[LocatedLine]:
    return [
        LocatedLine(number=number, text="  Name:"),
        LocatedLine(number=number, text=f"     {name}"),
        LocatedLine(number=number, text=""),
        LocatedLine(number=number, text="  Purpose:"),
        LocatedLine(number=number, text=f"     {purpose.rstrip()}"),
        LocatedLine(number=number, text=""),
    ]


def _normalize_title(title: str) -> str:
    stripped = " ".join(title.split())
    return _TITLE_ALIASES.get(stripped.casefold(), stripped.title())


def _title_key(title: str) -> str:
    return " ".join(title.casefold().split())


def _content_line(number: int, content: str) -> LocatedLine:
    if not content.strip():
        return LocatedLine(number=number, text="")
    stripped = content.lstrip()
    if stripped.casefold().startswith("<description of "):
        return LocatedLine(number=number, text="")
    indentation = len(content.expandtabs(8)) - len(content.expandtabs(8).lstrip())
    return LocatedLine(number=number, text=" " * max(5, indentation) + stripped)


def _strip_c_content(line: str) -> str:
    content = line.rstrip()
    stripped = content.lstrip()
    if stripped.startswith("*"):
        stripped = stripped[1:]
    return stripped


def _c_block_lines(lines: list[str]) -> list[bool]:
    result: list[bool] = []
    in_block = False
    for line in lines:
        result.append(in_block)
        offset = 0
        while offset < len(line):
            token = "*/" if in_block else "/*"
            found = line.find(token, offset)
            if found < 0:
                break
            in_block = not in_block
            offset = found + 2
    return result
