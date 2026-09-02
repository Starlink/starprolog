from __future__ import annotations

__all__ = (
    "HlpOptions",
    "render_hlp",
    "render_prologue_hlp",
)

import re

from .models import (
    DocumentationMode,
    FrozenModel,
    Prologue,
    PrologueCollection,
    Section,
    SectionRole,
)


class HlpOptions(FrozenModel):
    """Options controlling Starlink help-library rendering."""

    mode: DocumentationMode = DocumentationMode.AUTO


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
    atask = prologue.resolve_mode(selected.mode) is DocumentationMode.ATASK
    purpose = prologue.find_section(SectionRole.PURPOSE, nonempty=True)
    description = prologue.find_section(SectionRole.DESCRIPTION, nonempty=True)
    invocation = None
    if not atask:
        invocation = prologue.find_section(SectionRole.INVOCATION, nonempty=True)

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
        usage = prologue.find_section(SectionRole.USAGE, nonempty=True)
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
        parameters = prologue.find_section(SectionRole.ADAM_PARAMETERS, nonempty=True)
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
        arguments = prologue.find_section(SectionRole.ARGUMENTS, nonempty=True)
        if arguments is not None:
            output.append("2 Arguments")
            output.extend(_render_subsections(arguments, header_indent=0, body_indent=3))

        returned = prologue.find_section(SectionRole.RETURNED_VALUE, nonempty=True)
        if returned is not None:
            output.append("2 Returned_Value")
            output.extend(_render_subsections(returned, header_indent=0, body_indent=3))

    examples = prologue.find_section(SectionRole.EXAMPLES, nonempty=True)
    if examples is not None:
        output.append("2 Examples")
        output.extend(_render_subsections(examples, header_indent=0, body_indent=3))

    notes = prologue.find_section(SectionRole.NOTES, nonempty=True)
    if notes is not None:
        output.append("2 Notes")
        output.extend(_render_blocks(notes, indent=0))

    for section in prologue.sections:
        if section.role in _EXCLUDED_ROLES or not section.has_content:
            continue
        output.append(f"2 {_help_key(section.title)}")
        output.extend(_render_blocks(section, indent=3))

    authors = prologue.find_section(SectionRole.AUTHORS, nonempty=True)
    if authors is not None:
        output.append("2 Authors")
        output.extend(_render_subsections(authors, header_indent=0, body_indent=3))

    history = prologue.find_section(SectionRole.HISTORY, nonempty=True)
    if history is not None:
        output.append("2 History")
        output.extend(_render_subsections(history, header_indent=1, body_indent=4))

    implementation = prologue.find_section(
        SectionRole.IMPLEMENTATION_STATUS,
        nonempty=True,
    )
    if implementation is not None:
        output.append("2 Implementation_Status")
        output.extend(_render_blocks(implementation, indent=3))

    bugs = prologue.find_section(SectionRole.BUGS, nonempty=True)
    if bugs is not None:
        output.append("2 Bugs")
        output.extend(_render_blocks(bugs, indent=3))

    return "\n".join(output).rstrip() + "\n"


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
    """Write a section body in paragraph mode, as ``SST_PUTP`` does.

    Parameters
    ----------
    section
        Section whose body is to be rendered.
    indent
        Base level of indentation for the output.

    Returns
    -------
    lines : `list` [`str`]
        Help-library lines for the section body.
    """
    output: list[str] = []
    previous_blank = True
    for line in section.body_lines():
        if not line.strip():
            if not previous_blank:
                output.append("")
                previous_blank = True
            continue
        text = line.strip()
        # A hyphen starts an item, which is separated from whatever precedes
        # it. The preserved-block "---" markers count as items here too.
        if text.startswith("-") and not previous_blank:
            output.append("")
        column = len(line) - len(line.lstrip(" "))
        output.append(f"{' ' * (indent + column)}{text}")
        previous_blank = False
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
