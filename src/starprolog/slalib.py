from __future__ import annotations

__all__ = ("extract_slalib_prologues",)

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

_START_RE = re.compile(r"^(?P<comment>[*Cc#])\+\s*$")
_RULE_RE = re.compile(r"^[*Cc#]\s+-(?: -)+\s*$")
_BANNER_NAME_RE = re.compile(r"^[*Cc#]\s+\S(?: \S)*\s*$")
_END_RE = re.compile(r"^[*Cc#]-.*$")
_HEADING_RE = re.compile(r"^[*Cc#]\s{1,4}(?P<title>[A-Z][A-Za-z'/ -]*?)\s*:\s*$")
_LABEL_RE = re.compile(r"^[*Cc#]\s{1,4}(?P<title>[A-Z][A-Za-z-]*)\s*:\s+(?P<value>\S.*)$")
"""A one-word label with its whole content on the heading line.

Prose in these prologues frequently contains a colon, so a line is only read
as a heading when it also passes `_introduces_a_section`.
"""
_SUBROUTINE_RE = re.compile(r"^ {6,}SUBROUTINE\s+(?P<name>\w+)\s*(?P<arguments>.*)$")
_PROGRAM_RE = re.compile(r"^ {6,}(?:PROGRAM|BLOCK\s+DATA)\s+(?P<name>\w+)\s*$")
_FUNCTION_RE = re.compile(
    r"^ {6,}(?:[A-Za-z][A-Za-z0-9*() ]*\s+)?FUNCTION\s+(?P<name>\w+)\s*(?P<arguments>.*)$"
)
_CONTINUATION_RE = re.compile(r"^ {5}[^ 0]")

_BANNER_SEARCH = 4
"""Lines after the delimiter that may hold the banner."""

_TITLE_ALIASES = {"result": "Returned Value"}

_ARGUMENT_MODES = {
    "given": "Given",
    "returned": "Returned",
    "given and returned": "Given and Returned",
}
"""Headings that list arguments, and the access mode each one implies."""

_FIELDS_RE = re.compile(r"\s{2,}")


def extract_slalib_prologues(
    text: str,
    source: str,
) -> tuple[list[RawPrologue], list[Diagnostic]]:
    """Extract SLALIB-style prologues introduced by a spaced-dash banner.

    The convention, used throughout SLALIB and the Wallace-derived
    applications, opens with a bare ``*+`` followed by a rule of spaced
    hyphens, the routine name spelled out letter by letter, and a second
    rule. There is no ``Name:`` or ``Purpose:`` heading, so both are
    recovered from the banner's surroundings.

    This reader is experimental. No SST tool read the convention, so there is
    no original implementation to check it against, and the rules that
    separate a heading from prose containing a colon are judgements rather
    than a port. Both those rules and the shape of the resulting sections may
    change. The README records what it does not yet handle.

    Parameters
    ----------
    text
        Complete source text.
    source
        Source name used in model locations and diagnostics.

    Returns
    -------
    prologues : `list` [`RawPrologue`]
        Prologues normalized for the shared structural parser.
    diagnostics : `list` [`Diagnostic`]
        Non-fatal problems encountered while reading the source.
    """
    lines = text.splitlines()
    prologues: list[RawPrologue] = []
    diagnostics: list[Diagnostic] = []
    index = 0
    while index < len(lines):
        match = _START_RE.fullmatch(lines[index])
        if match is None or not _has_banner(lines, index):
            index += 1
            continue

        start = index + 1
        name, invocation = _declaration(lines, index)
        body_start = _banner_end(lines, index)
        end, terminated, next_index = _find_end(lines, body_start)
        normalized = _normalize(lines, body_start, end, name, invocation, start)

        if not terminated:
            diagnostics.append(
                Diagnostic(
                    severity=DiagnosticSeverity.WARNING,
                    code="unterminated-slalib-prologue",
                    message="SLALIB prologue reached end of file without a terminator.",
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
                syntax=PrologueSyntax.SLALIB,
                source=SourceSpan(path=source, start_line=start, end_line=end),
                lines=tuple(normalized),
            )
        )
        index = next_index

    return prologues, diagnostics


def _content_indent(line: str) -> int:
    """Indentation of a comment line's text, counting the comment character."""
    body = f" {line[1:]}"
    return len(body) - len(body.lstrip())


def _introduces_a_section(lines: list[str], index: int) -> bool:
    """Whether a colon-bearing line reads as a heading rather than as prose.

    A heading is followed by its body, so the next line is either blank or
    indented past the heading. Purpose text such as ``Projection of spherical
    coordinates onto tangent plane:`` continues at its own column instead.

    Parameters
    ----------
    lines
        Complete source lines.
    index
        Index of the candidate heading.

    Returns
    -------
    heading : `bool`
        `True` when the line introduces a section.
    """
    if index + 1 >= len(lines):
        return True
    following = lines[index + 1]
    if following[:1] not in ("*", "C", "c", "#"):
        return True
    if _END_RE.fullmatch(following) or _START_RE.fullmatch(following):
        return True
    if not following[1:].strip():
        return True
    return _content_indent(following) > _content_indent(lines[index])


def _has_banner(lines: list[str], marker: int) -> bool:
    """Whether the delimiter is followed by a spaced-dash name banner."""
    window = lines[marker + 1 : marker + 1 + _BANNER_SEARCH]
    rules = [offset for offset, line in enumerate(window) if _RULE_RE.fullmatch(line)]
    if len(rules) < 2:
        return False
    name_line = rules[0] + 1
    return name_line < len(window) and _BANNER_NAME_RE.fullmatch(window[name_line]) is not None


def _banner_end(lines: list[str], marker: int) -> int:
    """Index of the first line after the banner's closing rule."""
    window = lines[marker + 1 : marker + 1 + _BANNER_SEARCH]
    rules = [offset for offset, line in enumerate(window) if _RULE_RE.fullmatch(line)]
    return marker + 1 + rules[1] + 1


def _find_end(lines: list[str], body_start: int) -> tuple[int, bool, int]:
    """Locate the prologue terminator.

    Returns
    -------
    end : `int`
        Line number of the last line belonging to the prologue.
    terminated : `bool`
        Whether an explicit terminator was found.
    next_index : `int`
        Index at which to resume scanning the source.
    """
    for index in range(body_start, len(lines)):
        line = lines[index]
        if _END_RE.fullmatch(line):
            return index + 1, True, index + 1
        if _START_RE.fullmatch(line):
            # A second bare delimiter closes the prologue, but one that opens
            # its own banner belongs to the next routine.
            if _has_banner(lines, index):
                return index, True, index
            return index + 1, True, index + 1
    return max(len(lines), body_start), False, len(lines)


def _declaration(lines: list[str], marker: int) -> tuple[str | None, str | None]:
    """Recover the routine name and an invocation from the program unit.

    Parameters
    ----------
    lines
        Complete source lines.
    marker
        Index of the prologue's opening delimiter.

    Returns
    -------
    name : `str` or `None`
        Declared routine name, if a declaration precedes the prologue.
    invocation : `str` or `None`
        The declaration rewritten as the call or assignment used to invoke
        it, following the forms ``SST_TRCVT`` supplies for each unit type.
    """
    end = marker
    while end > 0 and not lines[end - 1].strip():
        end -= 1
    if end == 0:
        return None, None
    first = end - 1
    while first > 0 and _CONTINUATION_RE.match(lines[first]):
        first -= 1
    statement = " ".join(part.strip() for part in (lines[first][:], *(x[6:] for x in lines[first + 1 : end])))
    statement = " ".join(statement.split())

    program = _PROGRAM_RE.match(f"      {statement}")
    if program is not None:
        # A main program or block data unit is never invoked.
        return program.group("name"), None
    subroutine = _SUBROUTINE_RE.match(f"      {statement}")
    if subroutine is not None:
        return subroutine.group("name"), f"CALL {statement.split(None, 1)[1]}"
    function = _FUNCTION_RE.match(f"      {statement}")
    if function is not None:
        name = function.group("name")
        arguments = function.group("arguments").strip()
        call = f"{name} {arguments}".strip() if arguments else name
        return name, f"RESULT = {call}"
    return None, None


def _normalize(
    lines: list[str],
    body_start: int,
    end: int,
    name: str | None,
    invocation: str | None,
    number: int,
) -> list[LocatedLine]:
    """Rewrite the prologue as headed sections for the shared parser."""
    span = range(body_start, min(end, len(lines)))
    headings = {
        index: heading for index in span for heading in (_heading(lines, index),) if heading is not None
    }
    # Unlabelled lines such as the author and copyright entries sit at the
    # same column as the headings, so keeping each heading in its own column
    # leaves them as topics of their own rather than folding them into
    # whichever section happens to precede them.
    level = min((_content_indent(lines[index]) for index in headings), default=3)

    arguments, consumed = _arguments(lines, span, headings, level)
    purpose: list[LocatedLine] = []
    body: list[LocatedLine] = []
    in_body = False
    written_arguments = False

    for index in span:
        line = lines[index]
        if _END_RE.fullmatch(line) or _START_RE.fullmatch(line):
            break
        if not line[:1] or line[0] not in "*Cc#":
            continue
        heading = headings.get(index)
        if heading is not None:
            in_body = True
            title = " ".join(heading.group("title").split())
            column = " " * _content_indent(line)
            if title.casefold() in _ARGUMENT_MODES:
                # Every argument heading contributes to one Arguments section,
                # emitted where the first of them appeared.
                if not written_arguments:
                    written_arguments = True
                    body.append(LocatedLine(number=index + 1, text=f"{column}Arguments:"))
                    body.extend(arguments)
                continue
            title = _TITLE_ALIASES.get(title.casefold(), title)
            body.append(LocatedLine(number=index + 1, text=f"{column}{title}:"))
            groups = heading.groupdict()
            if "value" in groups:
                # Short sections such as "Called:" and "Result:" put their
                # whole content on the heading line.
                body.append(
                    LocatedLine(
                        number=index + 1,
                        text=f"{column}   {groups['value'].strip()}",
                    )
                )
            continue
        if index in consumed:
            continue
        content = f" {line[1:]}".rstrip()
        target = body if in_body else purpose
        target.append(LocatedLine(number=index + 1, text=content if content.strip() else ""))

    column = " " * level
    normalized: list[LocatedLine] = []
    if name is not None:
        normalized.extend(
            (
                LocatedLine(number=number, text=f"{column}Name:"),
                LocatedLine(number=number, text=f"{column}   {name}"),
                LocatedLine(number=number, text=""),
            )
        )
    normalized.append(LocatedLine(number=number, text=f"{column}Purpose:"))
    normalized.extend(_reindent(_trim(purpose), level + 3))
    normalized.append(LocatedLine(number=number, text=""))
    if invocation is not None:
        normalized.extend(
            (
                LocatedLine(number=number, text=f"{column}Invocation:"),
                LocatedLine(number=number, text=f"{column}   {invocation}"),
                LocatedLine(number=number, text=""),
            )
        )
    normalized.extend(body)
    return normalized


def _entry(text: str) -> tuple[str, str, str] | None:
    """Split one argument line into its name, type and description.

    Parameters
    ----------
    text
        The argument line, stripped of leading and trailing space.

    Returns
    -------
    entry : `tuple` [`str`, `str`, `str`] or `None`
        Name, type and description, or `None` when the line does not read as
        an argument at all. The description is set off by a run of spaces;
        the name and type are usually too, but not always.
    """
    fields = _FIELDS_RE.split(text, maxsplit=2)
    if len(fields) >= 3 and " " not in fields[1]:
        return fields[0], fields[1], fields[2]
    if len(fields) == 2 and " " in fields[0]:
        name, kind = fields[0].split(None, 1)
        return name, kind, fields[1]
    if len(fields) == 2 and " " not in fields[1]:
        return fields[0], fields[1], ""
    return None


def _arguments(
    lines: list[str],
    span: range,
    headings: dict[int, re.Match[str]],
    level: int,
) -> tuple[list[LocatedLine], set[int]]:
    """Rewrite the argument lists as the subsections the renderers expect.

    ``Given:``, ``Returned:`` and ``Given and returned:`` are columnar lists of
    ``NAME  type  description`` rather than the ``NAME = TYPE (Given)`` form
    used elsewhere, and the access mode belongs to the heading rather than to
    the entry. They become one ``Arguments:`` section whose entries each carry
    their own mode.

    Parameters
    ----------
    lines
        Complete source lines.
    span
        Range of line indices covered by the prologue body.
    headings
        Section headings found in that range, keyed by line index.
    level
        Column at which section headings are written.

    Returns
    -------
    lines : `list` [`LocatedLine`]
        Subsection headers and bodies for the merged section.
    consumed : `set` [`int`]
        Indices of the source lines the merged section accounts for.
    """
    output: list[LocatedLine] = []
    consumed: set[int] = set()
    mode: str | None = None
    heading_indent = 0
    entry_indent: int | None = None

    for index in span:
        line = lines[index]
        if _END_RE.fullmatch(line) or _START_RE.fullmatch(line):
            break
        if not line[:1] or line[0] not in "*Cc#":
            continue
        heading = headings.get(index)
        if heading is not None:
            title = " ".join(heading.group("title").split())
            mode = _ARGUMENT_MODES.get(title.casefold())
            heading_indent = _content_indent(line)
            entry_indent = None
            value = heading.groupdict().get("value", "").strip()
            if mode is not None and value:
                # A qualifier such as "Given:  (all B1950.0,FK4)" applies to
                # the whole list rather than to any one argument.
                output.append(LocatedLine(number=index + 1, text=f"{' ' * (level + 3)}{value}"))
            continue
        if mode is None or not line[1:].strip():
            continue

        indent = _content_indent(line)
        if indent <= heading_indent:
            # Prose that returns to the heading column, such as the result
            # statement, is not part of the argument list.
            mode = None
            continue

        consumed.add(index)
        text = line[1:].strip()
        if entry_indent is None:
            entry_indent = indent
        if indent > entry_indent:
            # A continuation is aligned under the description column of the
            # whole table, which means nothing once each entry stands alone.
            output.append(LocatedLine(number=index + 1, text=f"{' ' * (level + 6)}{text}"))
            continue

        entry = _entry(text)
        if entry is None:
            output.append(LocatedLine(number=index + 1, text=f"{' ' * (level + 3)}{text}"))
            continue
        name, kind, description = entry
        # TODO: an entry naming several variables, such as "XI,ETA  dp  ...",
        # should become one subsection per variable. The description covers
        # them all and cannot be divided, so it has to be repeated on each.
        # TODO: the type keeps its SLALIB shorthand, "d" or "dp" for double
        # precision and so on, and should be normalized to the spelling the
        # rest of Starlink uses. A dimension is written on the type here,
        # "d(3,3)", where Starlink writes it on the name.
        output.append(LocatedLine(number=index + 1, text=f"{' ' * (level + 3)}{name} = {kind} ({mode})"))
        if description:
            output.append(LocatedLine(number=index + 1, text=f"{' ' * (level + 6)}{description}"))
    return output, consumed


def _heading(lines: list[str], index: int) -> re.Match[str] | None:
    """Match a section heading, rejecting prose that merely holds a colon."""
    line = lines[index]
    match = _HEADING_RE.fullmatch(line) or _LABEL_RE.fullmatch(line)
    if match is None or not _introduces_a_section(lines, index):
        return None
    return match


def _reindent(lines: list[LocatedLine], level: int) -> list[LocatedLine]:
    """Shift lines so their shallowest sits at the given column."""
    indents = [len(x.text) - len(x.text.lstrip()) for x in lines if x.text.strip()]
    shift = level - min(indents, default=0)
    return [
        LocatedLine(
            number=line.number,
            text=f"{' ' * max(shift, 0)}{line.text}" if line.text.strip() else "",
        )
        for line in lines
    ]


def _trim(lines: list[LocatedLine]) -> list[LocatedLine]:
    first = 0
    last = len(lines)
    while first < last and not lines[first].text.strip():
        first += 1
    while last > first and not lines[last - 1].text.strip():
        last -= 1
    return lines[first:last]
