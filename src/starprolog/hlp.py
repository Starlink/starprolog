from __future__ import annotations

__all__ = (
    "HlpMode",
    "HlpOptions",
    "render_hlp",
    "render_prologue_hlp",
)

import re
from enum import StrEnum

from .models import (
    FrozenModel,
    ItemListBlock,
    LineBlock,
    ParagraphBlock,
    Prologue,
    PrologueCollection,
    Section,
    SectionRole,
)


class HlpMode(StrEnum):
    """Kind of Starlink help-library documentation being rendered."""

    AUTO = "auto"
    ATASK = "atask"
    LIBRARY = "library"


class HlpOptions(FrozenModel):
    """Options controlling Starlink help-library rendering."""

    mode: HlpMode = HlpMode.AUTO


_EXCLUDED_ROLES = {
    SectionRole.NAME,
    SectionRole.PURPOSE,
    SectionRole.INVOCATION,
    SectionRole.USAGE,
    SectionRole.DESCRIPTION,
    SectionRole.ADAM_PARAMETERS,
    SectionRole.ARGUMENTS,
    SectionRole.RETURNED_VALUE,
    SectionRole.EXAMPLES,
    SectionRole.NOTES,
    SectionRole.AUTHORS,
    SectionRole.HISTORY,
    SectionRole.IMPLEMENTATION_STATUS,
    SectionRole.BUGS,
    SectionRole.TYPE_OF_MODULE,
    SectionRole.ALGORITHM,
    SectionRole.IMPLEMENTATION_DEFICIENCIES,
    SectionRole.LANGUAGE,
    SectionRole.SYNOPSIS,
}


def render_hlp(
    collection: PrologueCollection,
    *,
    options: HlpOptions | None = None,
) -> str:
    """Render a collection in Starlink help-library source format.

    Parameters
    ----------
    collection
        Parsed prologues to render.
    options
        Help-library rendering options.

    Returns
    -------
    hlp : `str`
        Text suitable as input to the Starlink help-library compiler.
    """
    selected = options or HlpOptions()
    rendered = [render_prologue_hlp(prologue, options=selected).rstrip() for prologue in collection.prologues]
    return "\n".join(rendered) + ("\n" if rendered else "")


def render_prologue_hlp(
    prologue: Prologue,
    *,
    options: HlpOptions | None = None,
) -> str:
    """Render one prologue in Starlink help-library source format.

    Parameters
    ----------
    prologue
        Prologue to render.
    options
        Help-library rendering options.

    Returns
    -------
    hlp : `str`
        One level-1 help topic and its child topics.

    Raises
    ------
    ValueError
        Raised when a section required by the historical ``prohlp``
        contract is absent.
    """
    selected = options or HlpOptions()
    atask = _is_atask(prologue, selected.mode)
    purpose = _find_section(prologue, SectionRole.PURPOSE, nonempty=True)
    description = _find_section(prologue, SectionRole.DESCRIPTION, nonempty=True)
    invocation = None
    if not atask:
        invocation = _find_section(prologue, SectionRole.INVOCATION, nonempty=True)

    required: list[tuple[str, object | None]] = [
        ("Name", prologue.name),
        ("Purpose", purpose),
        ("Description", description),
    ]
    if not atask:
        required.append(("Invocation", invocation))
    missing = [label for label, value in required if value is None]
    if missing:
        location = f"{prologue.source.path}:{prologue.source.start_line}"
        raise ValueError(f"{location}: missing required section(s): {', '.join(missing)}")

    assert prologue.name is not None
    assert purpose is not None
    assert description is not None
    name = prologue.name
    if atask:
        name = name.replace("(", "").replace(")", "").upper()

    output = [f"1 {name}"]
    output.extend(_render_blocks(purpose, indent=0))
    output.append("")

    if atask:
        usage = _find_section(prologue, SectionRole.USAGE, nonempty=True)
        if usage is not None:
            output.extend(("Usage:", ""))
            output.extend(_render_blocks(usage, indent=3))
            output.append("")
    else:
        assert invocation is not None
        output.extend(_render_blocks(invocation, indent=0))
        output.append("")

    output.extend(("Description:", ""))
    output.extend(_render_blocks(description, indent=3))

    if atask:
        parameters = _find_section(prologue, SectionRole.ADAM_PARAMETERS, nonempty=True)
        if parameters is not None:
            output.extend(
                (
                    "2 Parameters",
                    "For information on individual parameters, select from the list below:",
                )
            )
            for parameter in parameters.subsections:
                parameter_name = parameter.title.partition("=")[0]
                output.extend((f"3 {_help_key(parameter_name)}", parameter.title))
                output.extend(_render_blocks(parameter, indent=3))
    else:
        arguments = _find_section(prologue, SectionRole.ARGUMENTS, nonempty=True)
        if arguments is not None:
            output.append("2 Arguments")
            output.extend(_render_subsections(arguments, header_indent=0, body_indent=3))

        returned = _find_section(prologue, SectionRole.RETURNED_VALUE, nonempty=True)
        if returned is not None:
            output.append("2 Returned_Value")
            output.extend(_render_subsections(returned, header_indent=0, body_indent=3))

    examples = _find_section(prologue, SectionRole.EXAMPLES, nonempty=True)
    if examples is not None:
        output.append("2 Examples")
        output.extend(_render_subsections(examples, header_indent=0, body_indent=3))

    notes = _find_section(prologue, SectionRole.NOTES, nonempty=True)
    if notes is not None:
        output.append("2 Notes")
        output.extend(_render_blocks(notes, indent=0))

    for section in prologue.sections:
        if section.role in _EXCLUDED_ROLES or not _section_has_content(section):
            continue
        output.append(f"2 {_help_key(section.title)}")
        output.extend(_render_section_content(section, indent=3))

    authors = _find_section(prologue, SectionRole.AUTHORS, nonempty=True)
    if authors is not None:
        output.append("2 Authors")
        output.extend(_render_subsections(authors, header_indent=0, body_indent=3))

    history = _find_section(prologue, SectionRole.HISTORY, nonempty=True)
    if history is not None:
        output.append("2 History")
        output.extend(_render_subsections(history, header_indent=1, body_indent=4))

    implementation = _find_section(
        prologue,
        SectionRole.IMPLEMENTATION_STATUS,
        nonempty=True,
    )
    if implementation is not None:
        output.append("2 Implementation_Status")
        output.extend(_render_blocks(implementation, indent=3))

    bugs = _find_section(prologue, SectionRole.BUGS, nonempty=True)
    if bugs is not None:
        output.append("2 Bugs")
        output.extend(_render_blocks(bugs, indent=3))

    return "\n".join(output).rstrip() + "\n"


def _is_atask(prologue: Prologue, mode: HlpMode) -> bool:
    if mode is not HlpMode.AUTO:
        return mode is HlpMode.ATASK
    module_type = _find_section(prologue, SectionRole.TYPE_OF_MODULE)
    if module_type is None:
        return False
    normalized = _section_text(module_type).casefold().replace("-", " ")
    return "a task" in normalized or "atask" in normalized


def _find_section(
    prologue: Prologue,
    role: SectionRole,
    *,
    nonempty: bool = False,
) -> Section | None:
    return next(
        (
            section
            for section in prologue.sections
            if section.role is role and (not nonempty or _section_has_content(section))
        ),
        None,
    )


def _section_has_content(section: Section) -> bool:
    return bool(section.blocks or section.subsections)


def _section_text(section: Section) -> str:
    return "\n".join(line.lstrip() for line in _render_section_content(section, indent=0))


def _render_section_content(section: Section, *, indent: int) -> list[str]:
    if section.subsections:
        return _render_subsections(
            section,
            header_indent=indent,
            body_indent=indent + 3,
        )
    return _render_blocks(section, indent=indent)


def _render_subsections(
    section: Section,
    *,
    header_indent: int,
    body_indent: int,
) -> list[str]:
    output: list[str] = []
    for subsection in section.subsections:
        if output:
            output.append("")
        output.append(f"{' ' * header_indent}{subsection.title}")
        output.extend(_render_blocks(subsection, indent=body_indent))
    return output


def _render_blocks(section: Section, *, indent: int) -> list[str]:
    output: list[str] = []
    prefix = " " * indent
    for index, block in enumerate(section.blocks):
        if index and output and output[-1] != "":
            output.append("")
        if isinstance(block, ParagraphBlock):
            for line in block.lines:
                if line.lstrip().startswith("-") and output and output[-1]:
                    output.append("")
                output.append(f"{prefix}{line}" if line else "")
        elif isinstance(block, LineBlock):
            output.extend(f"{prefix}{line}" if line else "" for line in block.lines)
        elif isinstance(block, ItemListBlock):
            for item_index, item in enumerate(block.items):
                if item_index:
                    output.append("")
                if not item.lines:
                    output.append(f"{prefix}-")
                    continue
                output.append(f"{prefix}- {item.lines[0]}")
                output.extend(f"{prefix}{line}" for line in item.lines[1:])
    return _trim_blank_lines(output)


def _trim_blank_lines(lines: list[str]) -> list[str]:
    first = 0
    last = len(lines)
    while first < last and not lines[first]:
        first += 1
    while last > first and not lines[last - 1]:
        last -= 1
    return lines[first:last]


def _help_key(value: str) -> str:
    current = value.strip().removesuffix(":").rstrip()
    while match := re.search(r"\([^()]*\)", current):
        current = f"{current[: match.start()]}{' ' * len(match.group())}{current[match.end() :]}"
    return current.rstrip().replace(" ", "_")
