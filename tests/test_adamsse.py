from __future__ import annotations

from starprolog import (
    InputFormat,
    ParagraphBlock,
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


def test_legacy_c_body_indentation_is_preserved() -> None:
    """Old C prologue bodies keep the nesting implied by their indentation."""
    collection = parse_text(
        """\
/*+ ems_annul - Annul the current error context */
void ems_annul(int *status)
/* Description :
      Annul the contents of the current error context.
   Parameters :
      status = int * (Given and Returned)
         The global status.
*/
{
}
""",
        source="ems_annul.c",
    )

    arguments = collection.prologues[0].sections[3]
    assert arguments.role is SectionRole.ARGUMENTS
    assert [sub.title for sub in arguments.subsections] == ["status = int * (Given and Returned)"]
    body = arguments.subsections[0].blocks[0]
    assert isinstance(body, ParagraphBlock)
    assert body.lines == ("The global status.",)


def test_endhistory_terminates_the_legacy_prologue() -> None:
    """SST_RDAD1 stops reading the prologue at an endhistory line."""
    collection = parse_text(
        """\
*+ SUMMED - Sum the pixels
*    Description :
*     Sum the pixels.
*    History :
*     1-SEP-1990: Original version. (ABC)
*    endhistory
*
*  Loop over the pixels.
      DO 1 I = 1, 10
*  Accumulate the sum.
1     CONTINUE
      END
""",
        source="summed.f",
    )

    assert not collection.diagnostics
    history = collection.prologues[0].sections[-1]
    assert history.role is SectionRole.HISTORY
    assert [sub.title for sub in history.subsections] == ["1-SEP-1990: Original version. (ABC)"]


def test_result_section_becomes_returned_value() -> None:
    """SST_TRCVT renames the old Result section to Returned Value."""
    collection = parse_text(
        """\
*+ SLA_EPB - Convert an MJD to a Besselian epoch
*    Description :
*     Convert an MJD to a Besselian epoch.
*    Result :
*     SLA_EPB = DOUBLE PRECISION
*        The Besselian epoch.
*-
""",
        source="sla_epb.f",
    )

    section = collection.prologues[0].sections[-1]
    assert section.title == "Returned Value"
    assert section.role is SectionRole.RETURNED_VALUE
    assert [sub.title for sub in section.subsections] == ["SLA_EPB = DOUBLE PRECISION"]


def test_old_adam_placeholders_are_blanked() -> None:
    """SST_ZAPAP blanks unfilled old-ADAM placeholders wherever they appear."""
    collection = parse_text(
        """\
*+ TEMPLATE - Demonstrate placeholders
*    Invocation :
*     CALL name[(argument_list)]
*    Authors :
*     author (institution::username)
*    History :
*     date:  changes (institution::username)
*-
""",
        source="template.f",
    )

    prologue = collection.prologues[0]
    assert [section.title for section in prologue.sections] == [
        "Name",
        "Purpose",
        "Invocation",
        "Authors",
        "History",
    ]
    assert not any(section.has_content for section in prologue.sections[2:])


def test_shallow_legacy_body_indentation_is_not_clamped() -> None:
    """Legacy body lines keep their own column instead of a fixed minimum."""
    collection = parse_text(
        """\
*+ SHALLOW - Demonstrate shallow indentation
*    Parameters :
*  VALUE = INTEGER (Given)
*   The value.
*-
""",
        source="shallow.f",
    )

    arguments = collection.prologues[0].sections[-1]
    assert [sub.title for sub in arguments.subsections] == ["VALUE = INTEGER (Given)"]
    body = arguments.subsections[0].blocks[0]
    assert isinstance(body, ParagraphBlock)
    assert body.lines == ("The value.",)
