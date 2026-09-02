from __future__ import annotations

__all__ = ("parse_paths", "parse_text")

import re
from collections.abc import Iterable, Sequence
from enum import StrEnum
from pathlib import Path

from .models import (
    Block,
    CollectionMetadata,
    Diagnostic,
    DiagnosticSeverity,
    FrozenModel,
    InputFormat,
    InputLanguage,
    ItemListBlock,
    LineBlock,
    ListItem,
    ParagraphBlock,
    Prologue,
    PrologueCollection,
    PrologueKind,
    PrologueMarker,
    Section,
    SectionRole,
    SourceSpan,
)
from .raw import LocatedLine, RawPrologue

_MARKER_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<comment>[*CcFf#])(?P<tag>[A-Za-z]*)(?P<sign>[+-]{1,2})[ \t]*$"
)
_C_BLOCK_LINE_RE = re.compile(r"^[ \t]*\*(?P<text>.*)$")
_PLAIN_SELECTOR_RE = re.compile(r"^(?P<language>[cf])(?P<text>(?:[ \t].*)?)$")
_HASH_SELECTOR_RE = re.compile(r"^#(?P<language>[cf])(?P<text>(?:[ \t].*)?)$")
_PLACEHOLDERS = (
    "{enter_new_authors_here}",
    "{enter_changes_here}",
    "{enter_further_changes_here}",
    "{note_any_bugs_here}",
    "{note_new_bugs_here}",
)

_SECTION_ROLES = {
    "adam parameters": SectionRole.ADAM_PARAMETERS,
    "algorithm": SectionRole.ALGORITHM,
    "applicability": SectionRole.APPLICABILITY,
    "arguments": SectionRole.ARGUMENTS,
    "authors": SectionRole.AUTHORS,
    "bugs": SectionRole.BUGS,
    "class membership": SectionRole.CLASS_MEMBERSHIP,
    "constructor function": SectionRole.CONSTRUCTOR_FUNCTION,
    "copyright": SectionRole.COPYRIGHT,
    "description": SectionRole.DESCRIPTION,
    "examples": SectionRole.EXAMPLES,
    "history": SectionRole.HISTORY,
    "implementation status": SectionRole.IMPLEMENTATION_STATUS,
    "implementation deficiencies": SectionRole.IMPLEMENTATION_DEFICIENCIES,
    "invocation": SectionRole.INVOCATION,
    "language": SectionRole.LANGUAGE,
    "licence": SectionRole.LICENCE,
    "license": SectionRole.LICENCE,
    "name": SectionRole.NAME,
    "notes": SectionRole.NOTES,
    "parameters": SectionRole.PARAMETERS,
    "purpose": SectionRole.PURPOSE,
    "return value": SectionRole.RETURNED_VALUE,
    "returned value": SectionRole.RETURNED_VALUE,
    "synopsis": SectionRole.SYNOPSIS,
    "type": SectionRole.TYPE,
    "type of module": SectionRole.TYPE_OF_MODULE,
    "usage": SectionRole.USAGE,
}

_SUBSECTION_ROLES = {
    SectionRole.ADAM_PARAMETERS,
    SectionRole.APPLICABILITY,
    SectionRole.ARGUMENTS,
    SectionRole.AUTHORS,
    SectionRole.EXAMPLES,
    SectionRole.HISTORY,
    SectionRole.PARAMETERS,
    SectionRole.RETURNED_VALUE,
}


class SourceContainer(StrEnum):
    """Source construct containing the prologue text."""

    PLAIN = "plain"
    C_BLOCK = "c_block"
    PYTHON_STRING = "python_string"


class ReaderOptions(FrozenModel):
    """Options controlling the Starlink source reader."""

    language: InputLanguage = InputLanguage.ALL
    input_format: InputFormat = InputFormat.AUTO


def parse_paths(
    paths: Iterable[Path],
    *,
    language: InputLanguage = InputLanguage.ALL,
    input_format: InputFormat = InputFormat.AUTO,
) -> PrologueCollection:
    """Parse Starlink prologues from source files.

    Parameters
    ----------
    paths
        Paths to source files. Files are processed in the supplied order.
    language
        Language-specific lines to retain in AST-style public prologues.
    input_format
        Source-prologue format to detect and parse.

    Returns
    -------
    collection : `PrologueCollection`
        Parsed prologues and any non-fatal diagnostics.
    """
    path_list = tuple(paths)
    prologues: list[Prologue] = []
    diagnostics: list[Diagnostic] = []
    options = ReaderOptions(language=language, input_format=input_format)

    for path in path_list:
        data = path.read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("utf-8", errors="replace")
            diagnostics.append(
                Diagnostic(
                    severity=DiagnosticSeverity.WARNING,
                    code="invalid-utf8",
                    message="Input contains invalid UTF-8; undecodable bytes were replaced.",
                    source=SourceSpan(path=str(path), start_line=1, end_line=1),
                )
            )
        parsed, found_diagnostics = _parse_source(text, str(path), options)
        prologues.extend(parsed)
        diagnostics.extend(found_diagnostics)

    return PrologueCollection(
        metadata=CollectionMetadata(
            language=language,
            input_format=input_format,
            source_count=len(path_list),
        ),
        prologues=tuple(prologues),
        diagnostics=tuple(diagnostics),
    )


def parse_text(
    text: str,
    *,
    source: str = "<memory>",
    language: InputLanguage = InputLanguage.ALL,
    input_format: InputFormat = InputFormat.AUTO,
) -> PrologueCollection:
    """Parse Starlink prologues from an in-memory source string.

    Parameters
    ----------
    text
        Complete source text.
    source
        Source name recorded in model locations and diagnostics.
    language
        Language-specific lines to retain in AST-style public prologues.
    input_format
        Source-prologue format to detect and parse.

    Returns
    -------
    collection : `PrologueCollection`
        Parsed prologues and any non-fatal diagnostics.
    """
    prologues, diagnostics = _parse_source(
        text,
        source,
        ReaderOptions(language=language, input_format=input_format),
    )
    return PrologueCollection(
        metadata=CollectionMetadata(
            language=language,
            input_format=input_format,
            source_count=1,
        ),
        prologues=tuple(prologues),
        diagnostics=tuple(diagnostics),
    )


def _parse_source(text: str, source: str, options: ReaderOptions) -> tuple[list[Prologue], list[Diagnostic]]:
    raw_prologues: list[RawPrologue] = []
    diagnostics: list[Diagnostic] = []
    if options.input_format in {InputFormat.AUTO, InputFormat.STARLSE}:
        modern, modern_diagnostics = _extract_prologues(text, source, options)
        raw_prologues.extend(modern)
        diagnostics.extend(modern_diagnostics)
    if options.input_format in {InputFormat.AUTO, InputFormat.ADAMSSE}:
        from .adamsse import extract_adamsse_prologues

        legacy, legacy_diagnostics = extract_adamsse_prologues(text, source)
        if options.input_format is InputFormat.AUTO:
            legacy = [
                candidate
                for candidate in legacy
                if not any(_spans_overlap(candidate.source, modern.source) for modern in raw_prologues)
            ]
            legacy_diagnostics = [
                diagnostic
                for diagnostic in legacy_diagnostics
                if diagnostic.source is None
                or any(diagnostic.source == candidate.source for candidate in legacy)
            ]
        raw_prologues.extend(legacy)
        diagnostics.extend(legacy_diagnostics)
    raw_prologues.sort(key=lambda prologue: prologue.source.start_line)
    prologues = [_parse_prologue(raw, diagnostics) for raw in raw_prologues]
    return prologues, diagnostics


def _spans_overlap(first: SourceSpan, second: SourceSpan) -> bool:
    return first.start_line <= second.end_line and second.start_line <= first.end_line


def _extract_prologues(
    text: str, source: str, options: ReaderOptions
) -> tuple[list[RawPrologue], list[Diagnostic]]:
    lines = text.splitlines()
    prologues: list[RawPrologue] = []
    diagnostics: list[Diagnostic] = []
    active_marker: PrologueMarker | None = None
    active_container = SourceContainer.PLAIN
    active_quote: str | None = None
    active_start = 0
    active_lines: list[LocatedLine] = []

    for index, raw_line in enumerate(lines, 1):
        if active_marker is None:
            match = _MARKER_RE.fullmatch(raw_line)
            if match is None or not match.group("sign").startswith("+"):
                continue
            active_marker = _make_marker(match)
            active_container, active_quote = _detect_container(lines, index, match.group("indent"))
            active_start = index
            active_lines = []
            continue

        if active_container is SourceContainer.C_BLOCK and raw_line.strip() == "*/":
            prologues.append(_finish_raw(source, active_start, index, active_marker, active_lines))
            active_marker = None
            continue

        if (
            active_container is SourceContainer.PYTHON_STRING
            and active_quote is not None
            and raw_line.strip() == active_quote
        ):
            prologues.append(_finish_raw(source, active_start, index, active_marker, active_lines))
            active_marker = None
            continue

        marker_match = _MARKER_RE.fullmatch(raw_line)
        if (
            marker_match is not None
            and marker_match.group("sign").startswith("-")
            and marker_match.group("tag").casefold() == active_marker.tag.casefold()
        ):
            prologues.append(_finish_raw(source, active_start, index, active_marker, active_lines))
            active_marker = None
            continue

        normalized = _normalize_line(raw_line, index, active_marker, active_container, options)
        if normalized is not None:
            active_lines.append(normalized)

    if active_marker is not None:
        end_line = max(len(lines), active_start)
        prologues.append(_finish_raw(source, active_start, end_line, active_marker, active_lines))
        diagnostics.append(
            Diagnostic(
                severity=DiagnosticSeverity.WARNING,
                code="unterminated-prologue",
                message="Prologue reached end of file without an explicit or container terminator.",
                source=SourceSpan(path=source, start_line=active_start, end_line=end_line),
            )
        )

    return prologues, diagnostics


def _make_marker(match: re.Match[str]) -> PrologueMarker:
    tag = match.group("tag")
    width = len(match.group("sign"))
    if tag.casefold() == "att":
        kind = PrologueKind.ATTRIBUTE
    elif tag.casefold() == "class":
        kind = PrologueKind.CLASS
    elif tag:
        kind = PrologueKind.TAGGED
    elif width == 2:
        kind = PrologueKind.PUBLIC
    else:
        kind = PrologueKind.STANDARD
    return PrologueMarker(
        comment_character=match.group("comment"),
        tag=tag,
        delimiter_width=width,
        kind=kind,
    )


def _detect_container(
    lines: Sequence[str], start_line: int, marker_indent: str
) -> tuple[SourceContainer, str | None]:
    previous = ""
    for line in reversed(lines[: start_line - 1]):
        if line.strip():
            previous = line.strip()
            break
    if previous.startswith("/*") or marker_indent:
        return SourceContainer.C_BLOCK, None
    if previous in {"'''", '"""'}:
        return SourceContainer.PYTHON_STRING, previous
    return SourceContainer.PLAIN, None


def _finish_raw(
    source: str,
    start_line: int,
    end_line: int,
    marker: PrologueMarker,
    lines: list[LocatedLine],
) -> RawPrologue:
    return RawPrologue(
        marker=marker,
        source=SourceSpan(path=source, start_line=start_line, end_line=end_line),
        lines=tuple(lines),
    )


def _normalize_line(
    raw_line: str,
    number: int,
    marker: PrologueMarker,
    container: SourceContainer,
    options: ReaderOptions,
) -> LocatedLine | None:
    if not raw_line.strip():
        return LocatedLine(number=number, text="")

    if marker.delimiter_width == 2 or marker.tag:
        selector_match = (
            _HASH_SELECTOR_RE.fullmatch(raw_line)
            if marker.comment_character == "#"
            else _PLAIN_SELECTOR_RE.fullmatch(raw_line)
        )
        if selector_match is not None:
            selector = selector_match.group("language")
            if options.language is InputLanguage.C and selector != "c":
                return None
            if options.language is InputLanguage.FORTRAN and selector != "f":
                return None
            return LocatedLine(
                number=number,
                text=_remove_placeholders(selector_match.group("text")).rstrip(),
            )

    if container is SourceContainer.C_BLOCK:
        match = _C_BLOCK_LINE_RE.fullmatch(raw_line)
        if match is None:
            return None
        value = match.group("text")
    elif raw_line[0] in "*CcFf#":
        value = raw_line[1:]
    else:
        return None

    return LocatedLine(number=number, text=_remove_placeholders(value).rstrip())


def _remove_placeholders(value: str) -> str:
    for placeholder in _PLACEHOLDERS:
        value = value.replace(placeholder, "")
    return value


def _parse_prologue(raw: RawPrologue, diagnostics: list[Diagnostic]) -> Prologue:
    sections = _parse_sections(raw.lines, raw.source.path, diagnostics)
    name = _extract_name(sections)
    return Prologue(
        name=name,
        syntax=raw.syntax,
        marker=raw.marker,
        source=raw.source,
        sections=tuple(sections),
    )


def _parse_sections(
    lines: Sequence[LocatedLine], source: str, diagnostics: list[Diagnostic]
) -> list[Section]:
    nonblank = [line for line in lines if line.text.strip()]
    if not nonblank:
        return []
    base_indent = min(_indent(line.text) for line in nonblank)
    header_indexes = [
        index for index, line in enumerate(lines) if line.text.strip() and _indent(line.text) == base_indent
    ]
    sections: list[Section] = []

    for position, header_index in enumerate(header_indexes):
        header = lines[header_index]
        stop_index = header_indexes[position + 1] if position + 1 < len(header_indexes) else len(lines)
        body = _trim_blank_lines(lines[header_index + 1 : stop_index])
        title = header.text.strip().removesuffix(":").rstrip()
        role = _role_for_title(title)
        end_line = lines[stop_index - 1].number if stop_index > header_index + 1 else header.number
        span = SourceSpan(path=source, start_line=header.number, end_line=end_line)
        parse_as_subsections = role in _SUBSECTION_ROLES or "parameters" in title.casefold()
        if body and parse_as_subsections:
            subsections = tuple(_parse_subsections(body, source, diagnostics))
            blocks: tuple[Block, ...] = ()
        else:
            subsections = ()
            blocks = tuple(_parse_blocks(body, source, diagnostics))
        sections.append(
            Section(
                title=title,
                role=role,
                source=span,
                blocks=blocks,
                subsections=subsections,
            )
        )

    return sections


def _parse_subsections(
    lines: Sequence[LocatedLine], source: str, diagnostics: list[Diagnostic]
) -> list[Section]:
    nonblank = [line for line in lines if line.text.strip()]
    if not nonblank:
        return []
    base_indent = min(_indent(line.text) for line in nonblank)
    header_indexes = [
        index for index, line in enumerate(lines) if line.text.strip() and _indent(line.text) == base_indent
    ]
    subsections: list[Section] = []
    for position, header_index in enumerate(header_indexes):
        header = lines[header_index]
        stop_index = header_indexes[position + 1] if position + 1 < len(header_indexes) else len(lines)
        body = _trim_blank_lines(lines[header_index + 1 : stop_index])
        end_line = lines[stop_index - 1].number if stop_index > header_index + 1 else header.number
        subsections.append(
            Section(
                title=header.text.strip(),
                source=SourceSpan(path=source, start_line=header.number, end_line=end_line),
                blocks=tuple(_parse_blocks(body, source, diagnostics)),
            )
        )
    return subsections


def _parse_blocks(lines: Sequence[LocatedLine], source: str, diagnostics: list[Diagnostic]) -> list[Block]:
    if not lines:
        return []
    blocks: list[Block] = []
    ordinary: list[LocatedLine] = []
    preserved: list[LocatedLine] | None = None
    marker_line: LocatedLine | None = None

    for line in lines:
        if line.text.strip() == "---":
            if preserved is None:
                blocks.extend(_parse_ordinary_blocks(ordinary, source))
                ordinary = []
                preserved = []
                marker_line = line
            else:
                first = marker_line.number if marker_line is not None else line.number
                content = _dedent_lines(preserved)
                blocks.append(
                    LineBlock(
                        lines=tuple(item.text for item in content),
                        source=SourceSpan(path=source, start_line=first, end_line=line.number),
                    )
                )
                preserved = None
                marker_line = None
            continue
        if preserved is None:
            ordinary.append(line)
        else:
            preserved.append(line)

    if preserved is not None:
        first = marker_line.number if marker_line is not None else preserved[0].number
        last = preserved[-1].number if preserved else first
        blocks.append(
            LineBlock(
                lines=tuple(item.text for item in _dedent_lines(preserved)),
                source=SourceSpan(path=source, start_line=first, end_line=last),
            )
        )
        diagnostics.append(
            Diagnostic(
                severity=DiagnosticSeverity.WARNING,
                code="unterminated-line-block",
                message="Preserved-line block has no closing '---' marker.",
                source=SourceSpan(path=source, start_line=first, end_line=last),
            )
        )
    else:
        blocks.extend(_parse_ordinary_blocks(ordinary, source))

    return blocks


def _parse_ordinary_blocks(lines: Sequence[LocatedLine], source: str) -> list[Block]:
    chunks: list[list[LocatedLine]] = []
    current: list[LocatedLine] = []
    for line in lines:
        if line.text.strip():
            current.append(line)
        elif current:
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)

    blocks: list[Block] = []
    for chunk in chunks:
        dedented = _dedent_lines(chunk)
        paragraph: list[LocatedLine] = []
        items: list[ListItem] = []
        active_item: list[LocatedLine] | None = None

        def flush_paragraph() -> None:
            if not paragraph:
                return
            blocks.append(
                ParagraphBlock(
                    lines=tuple(line.text for line in paragraph),
                    source=SourceSpan(
                        path=source,
                        start_line=paragraph[0].number,
                        end_line=paragraph[-1].number,
                    ),
                )
            )
            paragraph.clear()

        def flush_item() -> None:
            nonlocal active_item
            if active_item is None:
                return
            items.append(
                ListItem(
                    lines=tuple(line.text for line in active_item),
                    source=SourceSpan(
                        path=source,
                        start_line=active_item[0].number,
                        end_line=active_item[-1].number,
                    ),
                )
            )
            active_item = None

        for line in dedented:
            stripped = line.text.lstrip()
            if stripped.startswith("-") and stripped != "---":
                flush_paragraph()
                flush_item()
                item_text = stripped[1:]
                if item_text.startswith(" "):
                    item_text = item_text[1:]
                active_item = [LocatedLine(number=line.number, text=item_text)]
            elif active_item is not None:
                active_item.append(LocatedLine(number=line.number, text=line.text.strip()))
            else:
                paragraph.append(line)
        flush_paragraph()
        flush_item()

        if items:
            item_block = ItemListBlock(
                items=tuple(items),
                source=SourceSpan(
                    path=source,
                    start_line=items[0].source.start_line,
                    end_line=items[-1].source.end_line,
                ),
            )
            if blocks and isinstance(blocks[-1], ItemListBlock):
                previous = blocks[-1]
                blocks.pop()
                blocks.append(
                    ItemListBlock(
                        items=previous.items + item_block.items,
                        source=SourceSpan(
                            path=source,
                            start_line=previous.source.start_line,
                            end_line=item_block.source.end_line,
                        ),
                    )
                )
            else:
                blocks.append(item_block)

    return blocks


def _dedent_lines(lines: Sequence[LocatedLine]) -> list[LocatedLine]:
    nonblank = [line for line in lines if line.text.strip()]
    if not nonblank:
        return [LocatedLine(number=line.number, text="") for line in lines]
    base_indent = min(_indent(line.text) for line in nonblank)
    return [
        LocatedLine(
            number=line.number,
            text=line.text.expandtabs(8)[base_indent:] if line.text.strip() else "",
        )
        for line in lines
    ]


def _trim_blank_lines(lines: Sequence[LocatedLine]) -> list[LocatedLine]:
    first = 0
    last = len(lines)
    while first < last and not lines[first].text.strip():
        first += 1
    while last > first and not lines[last - 1].text.strip():
        last -= 1
    return list(lines[first:last])


def _role_for_title(title: str) -> SectionRole | None:
    normalized = " ".join(title.casefold().split())
    return _SECTION_ROLES.get(normalized)


def _extract_name(sections: Sequence[Section]) -> str | None:
    for section in sections:
        if section.role is not SectionRole.NAME:
            continue
        for block in section.blocks:
            if isinstance(block, ParagraphBlock) and block.lines:
                return " ".join(line.strip() for line in block.lines).strip() or None
        if section.subsections:
            return section.subsections[0].title.strip() or None
    return None


def _indent(value: str) -> int:
    leading = value[: len(value) - len(value.lstrip())]
    return len(leading.expandtabs(8))
