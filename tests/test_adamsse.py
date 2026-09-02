from __future__ import annotations

from starprolog import (
    InputFormat,
    PrologueSyntax,
    SectionRole,
    parse_text,
    render_latex,
)


def test_old_fortran_prologue_uses_shared_ir_and_renderer() -> None:
    """An old ADAM/SSE Fortran prologue renders through the shared IR."""
    collection = parse_text(
        """\
*+ LEGACY - Demonstrate the historical input syntax
      SUBROUTINE LEGACY( VALUE, STATUS )
*    Description :
*     This routine demonstrates direct legacy parsing.
*    Method :
*     Apply the requested operation.
*    Deficiencies :
*     <description of any deficiencies>
*    History :
*     1-SEP-1990: Original version. (ABC)
*    Type Definitions :
      IMPLICIT NONE
*-
""",
        source="legacy.f",
    )

    assert not collection.diagnostics
    assert len(collection.prologues) == 1
    prologue = collection.prologues[0]
    assert prologue.name == "LEGACY"
    assert prologue.syntax is PrologueSyntax.ADAMSSE_FORTRAN
    assert [section.role for section in prologue.sections] == [
        SectionRole.NAME,
        SectionRole.PURPOSE,
        SectionRole.TYPE_OF_MODULE,
        SectionRole.DESCRIPTION,
        SectionRole.ALGORITHM,
        SectionRole.IMPLEMENTATION_DEFICIENCIES,
        SectionRole.HISTORY,
    ]
    latex = render_latex(collection)
    assert "Demonstrate the historical input syntax" in latex
    assert "direct legacy parsing" in latex


def test_old_c_prologue_uses_shared_ir_and_renderer() -> None:
    """A BDK-style C prologue contributes ordinary IR sections."""
    collection = parse_text(
        """\
/*+ legacy_c - demonstrate old C comments */
void legacy_c(int value)
/* Description :
      Return after examining the supplied value.
   Method :
      Inspect the value directly.
   Author :
      An Author
*/
{
}
""",
        source="legacy.c",
    )

    assert not collection.diagnostics
    prologue = collection.prologues[0]
    assert prologue.name == "legacy_c"
    assert prologue.syntax is PrologueSyntax.ADAMSSE_C
    assert [section.role for section in prologue.sections] == [
        SectionRole.NAME,
        SectionRole.PURPOSE,
        SectionRole.DESCRIPTION,
        SectionRole.ALGORITHM,
        SectionRole.AUTHORS,
    ]
    assert "examining the supplied value" in render_latex(collection)


def test_auto_detection_prefers_overlapping_starlse_prologue() -> None:
    """A stale old banner does not duplicate an embedded modern prologue."""
    collection = parse_text(
        """\
*+ STALE - An obsolete banner
*+
*  Name:
*     CURRENT
*  Purpose:
*     Use the current prologue.
*-
*    Type Definitions :
      IMPLICIT NONE
""",
        source="mixed.f",
    )

    assert not collection.diagnostics
    assert [prologue.name for prologue in collection.prologues] == ["CURRENT"]
    assert collection.prologues[0].syntax is PrologueSyntax.STARLSE


def test_input_format_can_disable_legacy_detection() -> None:
    """Explicit STARLSE mode ignores old ADAM/SSE prologues."""
    collection = parse_text(
        "*+ LEGACY - Ignore this old prologue\n*    Type Definitions :\n",
        input_format=InputFormat.STARLSE,
    )

    assert not collection.prologues
