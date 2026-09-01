from __future__ import annotations

__all__ = (
    "LatexMode",
    "LatexOptions",
    "escape_latex",
    "render_latex",
    "render_prologue_latex",
)

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


class LatexMode(StrEnum):
    """Kind of Starlink documentation being rendered."""

    AUTO = "auto"
    ATASK = "atask"
    LIBRARY = "library"


class LatexOptions(FrozenModel):
    """Options controlling LaTeX rendering."""

    mode: LatexMode = LatexMode.AUTO
    document: bool = False
    page_breaks: bool = False


_DOCUMENT_PREAMBLE = r"""\documentclass[11pt]{article}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0.6em}

\newlength{\sstbannerlength}
\newlength{\sstcaptionlength}
\newcommand{\sstroutine}[3]{%
  \par\goodbreak\hrule\medskip
  \settowidth{\sstbannerlength}{\Large\bfseries #1}%
  \setlength{\sstcaptionlength}{\linewidth}%
  \addtolength{\sstcaptionlength}{-2\sstbannerlength}%
  \noindent\parbox[t]{\sstbannerlength}{\Large\bfseries #1}%
  \parbox[t]{\sstcaptionlength}{\centering\Large #2}%
  \parbox[t]{\sstbannerlength}{\raggedleft\Large\bfseries #1}%
  \begin{description}#3\end{description}%
}
\newcommand{\sstdescription}[1]{\item[Description:] #1}
\newcommand{\sstusage}[1]{\item[Usage:] \texttt{#1}}
\newcommand{\sstinvocation}[1]{\item[Invocation:] \texttt{#1}}
\newcommand{\sstarguments}[1]{\item[Arguments:]\begin{description}#1\end{description}}
\newcommand{\sstreturnedvalue}[1]{\item[Returned Value:]\begin{description}#1\end{description}}
\newcommand{\sstparameters}[1]{\item[Parameters:]\begin{description}#1\end{description}}
\newcommand{\sstexamples}[1]{\item[Examples:]\begin{description}#1\end{description}}
\newcommand{\sstsubsection}[2]{\item[#1] #2}
\newcommand{\sstexamplesubsection}[2]{\item[\texttt{#1}] #2}
\newcommand{\sstnotes}[1]{\item[Notes:] #1}
\newcommand{\sstdiytopic}[2]{\item[#1:] #2}
\newcommand{\sstdiylist}[2]{\item[#1:]\begin{description}#2\end{description}}
\newcommand{\sstimplementationstatus}[1]{\item[Implementation Status:] #1}
\newcommand{\sstbugs}[1]{\item[Bugs:] #1}
\newcommand{\sstitemlist}[1]{\begin{itemize}#1\end{itemize}}
\newcommand{\sstitem}{\item}

\begin{document}
"""

_DOCUMENT_END = "\\end{document}\n"

_EXCLUDED_ROLES = {
    SectionRole.NAME,
    SectionRole.PURPOSE,
    SectionRole.LANGUAGE,
    SectionRole.TYPE_OF_MODULE,
    SectionRole.SYNOPSIS,
    SectionRole.AUTHORS,
    SectionRole.HISTORY,
    SectionRole.LICENCE,
    SectionRole.COPYRIGHT,
}

_SPECIAL_ROLES = {
    SectionRole.DESCRIPTION,
    SectionRole.USAGE,
    SectionRole.INVOCATION,
    SectionRole.ADAM_PARAMETERS,
    SectionRole.ARGUMENTS,
    SectionRole.APPLICABILITY,
    SectionRole.RETURNED_VALUE,
    SectionRole.EXAMPLES,
    SectionRole.NOTES,
    SectionRole.IMPLEMENTATION_STATUS,
    SectionRole.BUGS,
}


def escape_latex(value: str) -> str:
    """Escape source text using the traditional SST LaTeX conventions.

    Parameters
    ----------
    value
        Plain source-prologue text.

    Returns
    -------
    escaped : `str`
        Text safe for inclusion in ordinary LaTeX macro arguments.
    """
    replacements = {
        "\\": r"$\backslash$",
        "{": r"\{",
        "}": r"\}",
        "$": r"\$",
        "%": r"\%",
        "#": r"\#",
        "&": r"\&",
        "_": r"\_",
        "+": "$+$",
        "*": "$*$",
        "|": "$|$",
        "<": "$<$",
        ">": "$>$",
        "'": r"\texttt{'}",
        '"': r'\texttt{"}',
        "^": r"$\wedge$",
        "~": r"$\sim$",
    }
    return "".join(replacements.get(character, character) for character in value)


def render_latex(
    collection: PrologueCollection,
    *,
    options: LatexOptions | None = None,
) -> str:
    """Render a collection as Starlink-compatible LaTeX.

    Parameters
    ----------
    collection
        Parsed prologues to render.
    options
        LaTeX rendering options.

    Returns
    -------
    latex : `str`
        A LaTeX fragment or complete document.
    """
    selected = options or LatexOptions()
    output: list[str] = []
    if selected.document:
        output.append(_DOCUMENT_PREAMBLE.rstrip())

    for index, prologue in enumerate(collection.prologues):
        if selected.page_breaks and index:
            output.append(r"\newpage")
        output.append(render_prologue_latex(prologue, options=selected).rstrip())

    if selected.document:
        output.append(_DOCUMENT_END.rstrip())
    return "\n".join(output) + ("\n" if output else "")


def render_prologue_latex(
    prologue: Prologue,
    *,
    options: LatexOptions | None = None,
) -> str:
    """Render one prologue using the traditional SST macro vocabulary.

    Parameters
    ----------
    prologue
        Prologue to render.
    options
        LaTeX rendering options.

    Returns
    -------
    latex : `str`
        Starlink-compatible LaTeX fragment.

    Raises
    ------
    ValueError
        Raised when the required name or purpose is absent.
    """
    selected = options or LatexOptions()
    name = prologue.name
    purpose = _find_section(prologue, SectionRole.PURPOSE, nonempty=True)
    description = _find_section(prologue, SectionRole.DESCRIPTION, nonempty=True)
    missing = [label for label, value in (("Name", name), ("Purpose", purpose)) if value is None]
    if missing:
        location = f"{prologue.source.path}:{prologue.source.start_line}"
        raise ValueError(f"{location}: missing required section(s): {', '.join(missing)}")

    assert name is not None
    assert purpose is not None
    atask = _is_atask(prologue, selected.mode)
    body: list[str] = []
    if description is not None:
        body.extend(_render_wrapped_section("sstdescription", description))

    usage_role = SectionRole.USAGE if atask else SectionRole.INVOCATION
    usage_macro = "sstusage" if atask else "sstinvocation"
    usage = _find_section(prologue, usage_role, nonempty=True)
    if usage is not None:
        body.extend(_render_wrapped_section(usage_macro, usage))

    parameter_role = SectionRole.ADAM_PARAMETERS if atask else SectionRole.ARGUMENTS
    parameter_macro = "sstparameters" if atask else "sstarguments"
    parameters = _find_section(prologue, parameter_role, nonempty=True)
    if parameters is not None:
        body.extend(_render_wrapped_section(parameter_macro, parameters, subsections=True))

    if atask:
        applicability = _find_section(prologue, SectionRole.APPLICABILITY, nonempty=True)
        if applicability is not None:
            body.extend(_render_diy_section(applicability, subsections=True))
    else:
        returned = _find_section(prologue, SectionRole.RETURNED_VALUE, nonempty=True)
        if returned is not None:
            body.extend(_render_wrapped_section("sstreturnedvalue", returned, subsections=True))

    examples = _find_section(prologue, SectionRole.EXAMPLES, nonempty=True)
    if examples is not None:
        body.extend(_render_wrapped_section("sstexamples", examples, subsections=True, examples=True))

    notes = _find_section(prologue, SectionRole.NOTES, nonempty=True)
    if notes is not None:
        body.extend(_render_wrapped_section("sstnotes", notes))

    for section in prologue.sections:
        if section.role in _EXCLUDED_ROLES or section.role in _SPECIAL_ROLES:
            continue
        if not _section_has_content(section):
            continue
        body.extend(_render_diy_section(section, subsections=bool(section.subsections)))

    implementation = _find_section(prologue, SectionRole.IMPLEMENTATION_STATUS, nonempty=True)
    if implementation is not None:
        body.extend(_render_wrapped_section("sstimplementationstatus", implementation))

    bugs = _find_section(prologue, SectionRole.BUGS, nonempty=True)
    if bugs is not None:
        body.extend(_render_wrapped_section("sstbugs", bugs))

    purpose_text = _section_text(purpose).rstrip()
    if purpose_text.endswith("."):
        purpose_text = purpose_text[:-1]
    lines = [r"\sstroutine{", f"   {escape_latex(name)}", "}{"]
    lines.extend(f"   {escape_latex(line)}" if line else "" for line in purpose_text.splitlines())
    lines.append("}{")
    lines.extend(body)
    lines.append("}")
    return "\n".join(lines) + "\n"


def _is_atask(prologue: Prologue, mode: LatexMode) -> bool:
    if mode is not LatexMode.AUTO:
        return mode is LatexMode.ATASK
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
    lines: list[str] = []
    for block in section.blocks:
        if isinstance(block, ParagraphBlock):
            if lines:
                lines.append("")
            lines.extend(block.lines)
        elif isinstance(block, ItemListBlock):
            for item in block.items:
                lines.extend(item.lines)
        elif isinstance(block, LineBlock):
            lines.extend(block.lines)
    return "\n".join(lines)


def _render_wrapped_section(
    macro: str,
    section: Section,
    *,
    subsections: bool = False,
    examples: bool = False,
) -> list[str]:
    lines = [f"   \\{macro}{{"]
    if subsections:
        lines.extend(_render_subsections(section, indent=6, examples=examples))
    else:
        lines.extend(_render_blocks(section, indent=6))
    lines.append("   }")
    return lines


def _render_diy_section(section: Section, *, subsections: bool) -> list[str]:
    macro = "sstdiylist" if subsections else "sstdiytopic"
    lines = [f"   \\{macro}{{", f"      {escape_latex(section.title)}", "   }{"]
    if subsections:
        lines.extend(_render_subsections(section, indent=6))
    else:
        lines.extend(_render_blocks(section, indent=6))
    lines.append("   }")
    return lines


def _render_subsections(section: Section, *, indent: int, examples: bool = False) -> list[str]:
    lines: list[str] = []
    macro = "sstexamplesubsection" if examples else "sstsubsection"
    for subsection in section.subsections:
        prefix = " " * indent
        lines.extend(
            (
                f"{prefix}\\{macro}{{",
                f"{prefix}   {escape_latex(subsection.title)}",
                f"{prefix}}}{{",
            )
        )
        lines.extend(_render_blocks(subsection, indent=indent + 3))
        lines.append(f"{prefix}}}")
    return lines


def _render_blocks(section: Section, *, indent: int) -> list[str]:
    output: list[str] = []
    prefix = " " * indent
    for index, block in enumerate(section.blocks):
        if index:
            output.append("")
        if isinstance(block, ParagraphBlock):
            output.extend(f"{prefix}{escape_latex(line)}" for line in block.lines)
        elif isinstance(block, ItemListBlock):
            output.append(f"{prefix}\\sstitemlist{{")
            for item in block.items:
                output.append(f"{prefix}   \\sstitem")
                output.extend(f"{prefix}      {escape_latex(line)}" for line in item.lines)
            output.append(f"{prefix}}}")
        elif isinstance(block, LineBlock):
            output.extend(_render_line_block(block, indent=indent))
    return output


def _render_line_block(block: LineBlock, *, indent: int) -> list[str]:
    prefix = " " * indent
    output = [f"{prefix}\\newline", f"{prefix}\\newline"]
    for line in block.lines:
        leading = len(line) - len(line.lstrip(" "))
        content = escape_latex(line[leading:])
        spacing = f"\\hspace*{{{leading / 2:g}em}}" if leading else ""
        output.append(f"{prefix}{spacing}{content}")
        output.append(f"{prefix}\\newline")
    return output
