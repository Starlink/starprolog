from __future__ import annotations

__all__ = (
    "LatexOptions",
    "escape_latex",
    "render_latex",
    "render_prologue_latex",
)

from collections.abc import Sequence

from .models import (
    DocumentationMode,
    FrozenModel,
    Prologue,
    PrologueCollection,
    Section,
    SectionRole,
)


class LatexOptions(FrozenModel):
    """Options controlling LaTeX rendering."""

    mode: DocumentationMode = DocumentationMode.AUTO
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
\newcommand{\sstapplicability}[1]{\item[Applicability:]\begin{description}#1\end{description}}
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
    SectionRole.ALGORITHM,
    SectionRole.NAME,
    SectionRole.PURPOSE,
    SectionRole.LANGUAGE,
    SectionRole.TYPE_OF_MODULE,
    SectionRole.SYNOPSIS,
    SectionRole.AUTHORS,
    SectionRole.HISTORY,
    SectionRole.IMPLEMENTATION_DEFICIENCIES,
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
    purpose = prologue.find_section(SectionRole.PURPOSE, nonempty=True)
    description = prologue.find_section(SectionRole.DESCRIPTION, nonempty=True)
    missing = [label for label, value in (("Name", name), ("Purpose", purpose)) if value is None]
    if missing:
        location = f"{prologue.source.path}:{prologue.source.start_line}"
        raise ValueError(f"{location}: missing required section(s): {', '.join(missing)}")

    assert name is not None
    assert purpose is not None
    atask = prologue.resolve_mode(selected.mode) is DocumentationMode.ATASK
    body: list[str] = []
    if description is not None:
        body.extend(_render_wrapped_section("sstdescription", description))

    usage_role = SectionRole.USAGE if atask else SectionRole.INVOCATION
    usage_macro = "sstusage" if atask else "sstinvocation"
    usage = prologue.find_section(usage_role, nonempty=True)
    if usage is not None:
        body.extend(_render_wrapped_section(usage_macro, usage))

    parameter_role = SectionRole.ADAM_PARAMETERS if atask else SectionRole.ARGUMENTS
    parameter_macro = "sstparameters" if atask else "sstarguments"
    parameters = prologue.find_section(parameter_role, nonempty=True)
    if parameters is not None:
        body.extend(_render_wrapped_section(parameter_macro, parameters, subsections=True))

    applicability = prologue.find_section(SectionRole.APPLICABILITY, nonempty=True)
    if applicability is not None:
        body.extend(_render_wrapped_section("sstapplicability", applicability, subsections=True))

    if not atask:
        returned = prologue.find_section(SectionRole.RETURNED_VALUE, nonempty=True)
        if returned is not None:
            body.extend(_render_wrapped_section("sstreturnedvalue", returned, subsections=True))

    examples = prologue.find_section(SectionRole.EXAMPLES, nonempty=True)
    if examples is not None:
        body.extend(_render_wrapped_section("sstexamples", examples, subsections=True, examples=True))

    notes = prologue.find_section(SectionRole.NOTES, nonempty=True)
    if notes is not None:
        body.extend(_render_wrapped_section("sstnotes", notes))

    for section in prologue.sections:
        if section.role in _EXCLUDED_ROLES or section.role in _SPECIAL_ROLES:
            continue
        if not section.has_content:
            continue
        body.extend(_render_diy_section(section, subsections=bool(section.subsections)))

    implementation = prologue.find_section(
        SectionRole.IMPLEMENTATION_STATUS,
        nonempty=True,
    )
    if implementation is not None:
        body.extend(_render_wrapped_section("sstimplementationstatus", implementation))

    bugs = prologue.find_section(SectionRole.BUGS, nonempty=True)
    if bugs is not None:
        body.extend(_render_wrapped_section("sstbugs", bugs))

    lines = [r"\sstroutine{", f"   {escape_latex(name)}", "}{"]
    lines.extend(_render_paragraph_mode(_purpose_lines(purpose), indent=3))
    lines.append("}{")
    lines.extend(body)
    lines.append("}")
    return "\n".join(lines) + "\n"


def _purpose_lines(purpose: Section) -> list[str]:
    """Return the purpose body with the trailing full stop removed.

    Parameters
    ----------
    purpose
        The prologue's purpose section.

    Returns
    -------
    lines : `list` [`str`]
        Body lines with any full stop dropped from the last of them, the way
        ``SST_TRLAT`` shortens the section before writing it.
    """
    lines = purpose.body_lines()
    for index in reversed(range(len(lines))):
        if lines[index].strip():
            lines[index] = lines[index].rstrip().removesuffix(".")
            break
    return lines


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
    return _render_paragraph_mode(section.body_lines(), indent=indent)


def _render_paragraph_mode(body: Sequence[str], *, indent: int) -> list[str]:
    """Write body lines in paragraph mode, as ``SST_LATP`` does.

    Parameters
    ----------
    body
        Section body lines, indented relative to the body.
    indent
        Base level of indentation for the output.

    Returns
    -------
    lines : `list` [`str`]
        LaTeX source lines for the section body.
    """
    output: list[str] = []
    current = indent
    items = False
    previous_blank = True
    preserve = False
    marker_indent = 0

    for line in body:
        if not line.strip():
            if preserve:
                output.append(f"{' ' * current}\\newline")
            elif not previous_blank:
                output.append("")
                previous_blank = True
            continue

        column = len(line) - len(line.lstrip(" "))
        text = line.strip()
        use = True

        if text == "---":
            preserve = not preserve
            marker_indent = column
            output.append(f"{' ' * current}\\newline")
            if preserve:
                output.append(f"{' ' * current}\\newline")
            use = False
        elif text.startswith("-"):
            if not items:
                items = True
                output.append(f"{' ' * current}\\sstitemlist{{")
                previous_blank = False
                current += 3
            if not previous_blank:
                output.append("")
            output.append(f"{' ' * current}\\sstitem")
            column += 1
            text = line[column:].strip()
        elif previous_blank and items:
            items = False
            current -= 3
            output.append(f"{' ' * current}}}")

        if use and text:
            spaces = column - marker_indent
            if preserve and spaces > 0:
                output.append(f"{' ' * current}\\hspace*{{{spaces / 2:g} em}}")
            output.append(f"{' ' * (current + column)}{escape_latex(text)}")
            if preserve:
                output.append(f"{' ' * current}\\newline")
        previous_blank = False

    if items:
        output.append(f"{' ' * (current - 3)}}}")
    return output
