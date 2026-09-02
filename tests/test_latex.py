from __future__ import annotations

import pytest

from starprolog import DocumentationMode, LatexOptions, escape_latex, parse_text, render_latex


def test_escape_latex_uses_sst_conventions() -> None:
    """Characters significant to LaTeX are converted safely."""
    assert escape_latex("A_B + C\\D & 5%") == r"A\_B $+$ C$\backslash$D \& 5\%"


def test_render_library_routine() -> None:
    """Library sections use the traditional SST routine macros."""
    collection = parse_text(
        """\
*+
*  Name:
*     DEMO_ONE
*  Purpose:
*     Demonstrate A_B rendering.
*  Invocation:
*     CALL DEMO_ONE( VALUE )
*  Description:
*     Render a routine.
*  Arguments:
*     VALUE = INTEGER (Given)
*        Value to render.
*  Notes:
*     - First note.
*     - Second note.
*  Bugs:
*     {note_any_bugs_here}
*  Algorithm:
*     Internal implementation detail.
*  Implementation Deficiencies:
*     Another internal implementation detail.
*-
"""
    )

    result = render_latex(collection)

    assert "\\sstroutine{" in result
    assert "DEMO\\_ONE" in result
    assert "Demonstrate A\\_B rendering" in result
    assert "\\sstinvocation{" in result
    assert "\\sstarguments{" in result
    assert "\\sstsubsection{" in result
    assert "\\sstitemlist{" in result
    assert "\\sstusage{" not in result
    assert "\\sstbugs{" not in result
    assert "Internal implementation detail" not in result


def test_auto_mode_detects_atask_and_complete_document() -> None:
    """A-task metadata selects usage and parameter output automatically."""
    collection = parse_text(
        """\
*+
*  Name:
*     TASK
*  Purpose:
*     Run a task.
*  Type of Module:
*     ADAM A-task
*  Usage:
*     TASK IN OUT
*  Description:
*     Do useful work.
*  ADAM Parameters:
*     IN = NDF (Read)
*        Input data.
*-
"""
    )

    result = render_latex(collection, options=LatexOptions(document=True))

    assert result.startswith(r"\documentclass")
    assert "\\sstusage{" in result
    assert "\\sstparameters{" in result
    assert "\\sstinvocation{" not in result
    assert result.endswith("\\end{document}\n")


def test_mode_can_override_inferred_atask() -> None:
    """An explicit library mode overrides Type of Module metadata."""
    collection = parse_text(
        """\
*+
*  Name:
*     TASK
*  Purpose:
*     Run a task.
*  Type of Module:
*     ADAM A-task
*  Invocation:
*     CALL TASK( STATUS )
*  Description:
*     Do useful work.
*-
"""
    )

    result = render_latex(collection, options=LatexOptions(mode=DocumentationMode.LIBRARY))

    assert "\\sstinvocation{" in result


def test_render_rejects_missing_required_section() -> None:
    """A useful source location is reported for incomplete prologues."""
    collection = parse_text("*+\n*  Name:\n*     EMPTY\n*-\n", source="empty.f")

    with pytest.raises(ValueError, match=r"empty\.f:1: missing required section\(s\): Purpose"):
        render_latex(collection)


def test_description_is_optional() -> None:
    """A short prologue without a description can still be rendered."""
    collection = parse_text("*+\n*  Name:\n*     SHORT\n*  Purpose:\n*     Be concise.\n*-\n")

    result = render_latex(collection)

    assert "SHORT" in result
    assert "\\sstdescription{" not in result
