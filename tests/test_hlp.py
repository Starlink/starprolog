from __future__ import annotations

import pytest

from starprolog import DocumentationMode, HlpOptions, parse_text, render_hlp


def test_render_library_help() -> None:
    """Library sections become level-1 and level-2 help topics."""
    collection = parse_text(
        """\
*+
*  Name:
*     DEMO_ONE
*  Purpose:
*     Demonstrate help rendering.
*  Invocation:
*     CALL DEMO_ONE( VALUE )
*  Description:
*     Render a routine.
*  Arguments:
*     VALUE = INTEGER (Given)
*        Value to render.
*  Returned Value:
*     DEMO_ONE = INTEGER
*        Result of the calculation.
*  Thread Safety:
*     The routine is thread safe.
*  Authors:
*     TJ: Tim Jenness
*  History:
*     1-SEP-2026 (TJ):
*        Original version.
*-
"""
    )

    result = render_hlp(collection)

    assert (
        result
        == """\
1 DEMO_ONE
Demonstrate help rendering.

CALL DEMO_ONE( VALUE )

Description:

   Render a routine.
2 Arguments
VALUE = INTEGER (Given)
   Value to render.
2 Returned_Value
DEMO_ONE = INTEGER
   Result of the calculation.
2 Thread_Safety
   The routine is thread safe.
2 Authors
TJ: Tim Jenness
2 History
 1-SEP-2026 (TJ):
    Original version.
"""
    )


def test_render_atask_help() -> None:
    """A-task parameters become level-3 topics with valid help keys."""
    collection = parse_text(
        """\
*+
*  Name:
*     fi(nd)me
*  Purpose:
*     Exercise A-task output.
*  Type of Module:
*     ADAM A-task
*  Usage:
*     findme in
*  Description:
*     Find a value.
*  ADAM Parameters:
*     IN( 2 ) = NDF (Read)
*        Input NDF.
*-
"""
    )

    result = render_hlp(collection)

    assert result.startswith("1 FINDME\n")
    assert "Usage:\n\n   findme in" in result
    assert "2 Parameters\n" in result
    assert "3 IN\nIN( 2 ) = NDF (Read)\n   Input NDF." in result


def test_mode_can_override_inferred_library() -> None:
    """An explicit A-task mode does not require an Invocation section."""
    collection = parse_text(
        """\
*+
*  Name:
*     TASK
*  Purpose:
*     Run a task.
*  Description:
*     Do useful work.
*-
"""
    )

    result = render_hlp(collection, options=HlpOptions(mode=DocumentationMode.ATASK))

    assert result.startswith("1 TASK\n")


def test_render_rejects_missing_required_sections() -> None:
    """The historical prohlp requirements are reported with a location."""
    collection = parse_text(
        "*+\n*  Name:\n*     EMPTY\n*  Purpose:\n*     Empty.\n*-\n",
        source="empty.f",
    )

    with pytest.raises(
        ValueError,
        match=r"empty\.f:1: missing required section\(s\): Description, Invocation",
    ):
        render_hlp(collection)


def test_paragraph_mode_matches_sst_putp() -> None:
    """Mixed body content renders exactly as SST_PUTP writes it."""
    result = render_hlp(
        parse_text(
            """\
*+
*  Name:
*     MIX
*  Purpose:
*     Exercise paragraphs, items and blocks.
*  Invocation:
*     CALL MIX( STATUS )
*  Description:
*     First paragraph at base.
*
*        Second paragraph indented three.
*
*     - First item
*       continued here
*         and deeper here.
*     - Second item.
*
*     Text after the list.
*     ---
*        Inside the block.
*     ---
*     Text after the block.
*-
"""
        )
    )

    assert (
        "\n".join(
            (
                "   First paragraph at base.",
                "",
                "      Second paragraph indented three.",
                "",
                "   - First item",
                "     continued here",
                "       and deeper here.",
                "",
                "   - Second item.",
                "",
                "   Text after the list.",
                "",
                "   ---",
                "      Inside the block.",
                "",
                "   ---",
                "   Text after the block.",
            )
        )
        in result
    )


def test_diy_sections_always_use_paragraph_mode() -> None:
    """SST_TRHLP writes every remaining section with SST_PUTP, not a list."""
    result = render_hlp(
        parse_text(
            """\
*+
*  Name:
*     CASE
*  Purpose:
*     Check the parameter-section heuristic.
*  Invocation:
*     CALL CASE( STATUS )
*  Description:
*     Body text.
*  Environment Parameters:
*     OTHER = INTEGER (Given)
*        Another value.
*-
"""
        )
    )

    assert (
        "\n".join(
            (
                "2 Environment_Parameters",
                "   OTHER = INTEGER (Given)",
                "      Another value.",
            )
        )
        in result
    )


def test_flattened_subsection_bodies_keep_their_source_offset() -> None:
    """SST_PUTP writes raw lines, so a body keeps its own indent."""
    result = render_hlp(
        parse_text(
            """\
*+
*  Name:
*     ARC2D
*  Purpose:
*     Check subsection offsets.
*  Invocation:
*     CALL ARC2D( STATUS )
*  Description:
*     Body text.
*  Parameters:
*    IMAGE = FILE (Read)
*        Name of image for input
*          This should be a file containing an arc spectrum.
*-
"""
        )
    )

    assert (
        "\n".join(
            (
                "2 Parameters",
                "   IMAGE = FILE (Read)",
                "       Name of image for input",
                "         This should be a file containing an arc spectrum.",
            )
        )
        in result
    )


def test_flattened_subsection_titles_keep_their_own_column() -> None:
    """A subsection deeper than its body keeps that extra indentation."""
    result = render_hlp(
        parse_text(
            """\
*+
* Name:
*    CHANGED
* Purpose:
*    Check subsection columns.
* Invocation:
*    CALL CHANGED( STATUS )
* Description:
*    Body text.
* Parameters:
*    IMAGE = FILE (Read)
*        Name of image for input
*
*   T.N.Wilkins, Cambridge, 18-MAY-1990
*-
"""
        )
    )

    assert (
        "\n".join(
            (
                "2 Parameters",
                "    IMAGE = FILE (Read)",
                "        Name of image for input",
                "",
                "   T.N.Wilkins, Cambridge, 18-MAY-1990",
            )
        )
        in result
    )
