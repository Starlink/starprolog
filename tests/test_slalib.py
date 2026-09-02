from __future__ import annotations

from starprolog import (
    InputFormat,
    ParagraphBlock,
    PrologueSyntax,
    SectionRole,
    parse_text,
    render_latex,
)

_DTP2S = """\
      SUBROUTINE sla_DTP2S (XI, ETA, RAZ, DECZ, RA, DEC)
*+
*     - - - - - -
*      D T P 2 S
*     - - - - - -
*
*  Transform tangent plane coordinates into spherical
*  (double precision)
*
*  Given:
*     XI,ETA      dp   tangent plane rectangular coordinates
*     RAZ,DECZ    dp   spherical coordinates of tangent point
*
*  Returned:
*     RA,DEC      dp   spherical coordinates (0-2pi,+/-pi/2)
*
*  Called:        sla_DRANRM
*-
"""


def test_slalib_prologue_is_detected_and_named() -> None:
    """The spaced-dash banner selects the SLALIB reader."""
    collection = parse_text(_DTP2S, source="dtp2s.f")

    prologue = collection.prologues[0]
    assert not collection.diagnostics
    assert prologue.syntax is PrologueSyntax.SLALIB
    assert prologue.name == "sla_DTP2S"
    purpose = prologue.find_section(SectionRole.PURPOSE)
    assert purpose is not None
    assert purpose.plain_text() == ("Transform tangent plane coordinates into spherical\n(double precision)")
    assert [section.title for section in prologue.sections] == [
        "Name",
        "Purpose",
        "Invocation",
        "Arguments",
        "Called",
    ]


def test_slalib_invocation_is_derived_from_the_declaration() -> None:
    """A subroutine declaration, continuation lines and all, gives the call."""
    collection = parse_text(
        """\
      SUBROUTINE sla_PLANTE (DATE, ELONG, PHI, JFORM, EPOCH,
     :                       ORBINC, ANODE, PERIH, AORQ, E,
     :                       AORL, DM, RA, DEC, R, JSTAT)
*+
*     - - - - - - -
*      P L A N T E
*     - - - - - - -
*
*  Topocentric apparent place of a solar system object.
*-
""",
        source="plante.f",
    )

    invocation = collection.prologues[0].find_section(SectionRole.INVOCATION)
    assert invocation is not None
    assert invocation.plain_text() == (
        "CALL sla_PLANTE (DATE, ELONG, PHI, JFORM, EPOCH, ORBINC, ANODE,"
        " PERIH, AORQ, E, AORL, DM, RA, DEC, R, JSTAT)"
    )


def test_slalib_function_invocation_uses_the_result_form() -> None:
    """A function declaration gives an assignment rather than a call."""
    collection = parse_text(
        """\
      DOUBLE PRECISION FUNCTION sla_EPB (DATE)
*+
*     - - - -
*      E P B
*     - - - -
*
*  Conversion of Modified Julian Date to Besselian Epoch
*
*  Result:  TAI-UTC in seconds
*-
""",
        source="epb.f",
    )

    prologue = collection.prologues[0]
    invocation = prologue.find_section(SectionRole.INVOCATION)
    assert invocation is not None
    assert invocation.plain_text() == "RESULT = sla_EPB (DATE)"
    returned = prologue.find_section(SectionRole.RETURNED_VALUE)
    assert returned is not None
    assert returned.title == "Returned Value"
    assert returned.plain_text() == "TAI-UTC in seconds"


def test_slalib_prologue_can_be_closed_by_a_second_marker() -> None:
    """Some Wallace prologues open and close with the same delimiter."""
    collection = parse_text(
        """\
      SUBROUTINE EQEP (E,J)
*+
*     - - - - -
*      E Q E P
*     - - - - -
*
*  Validate equinox or epoch
*
*  Given:
*     E     d     equinox or epoch
*
*+

      IMPLICIT NONE
""",
        source="eqep.f",
    )

    assert not collection.diagnostics
    prologue = collection.prologues[0]
    assert prologue.name == "EQEP"
    assert "+" not in [section.title for section in prologue.sections]
    assert prologue.source.end_line == 12


def test_slalib_prologues_render_as_latex() -> None:
    """A detected prologue supplies the name and purpose the renderer needs."""
    result = render_latex(parse_text(_DTP2S, source="dtp2s.f"))

    assert "   sla\\_DTP2S" in result
    assert "\\sstinvocation{" in result
    assert "\\sstarguments{" in result


def test_starlse_format_ignores_slalib_prologues() -> None:
    """An explicit format selection suppresses SLALIB detection."""
    collection = parse_text(_DTP2S, source="dtp2s.f", input_format=InputFormat.STARLSE)

    prologue = collection.prologues[0]
    assert prologue.syntax is PrologueSyntax.STARLSE
    assert prologue.name is None
    first = prologue.sections[0].blocks[0]
    assert isinstance(first, ParagraphBlock)


def test_purpose_text_containing_a_colon_is_not_a_heading() -> None:
    """Only a trailing colon, or a one-word label, introduces a section."""
    collection = parse_text(
        """\
      SUBROUTINE sla_DE2H (HA, DEC, PHI, AZ, EL)
*+
*     - - - - -
*      D E 2 H
*     - - - - -
*
*  Equatorial to horizon coordinates:  HA,Dec to Az,El
*
*  (double precision)
*
*  Called:  sla_DRANRM
*-
""",
        source="de2h.f",
    )

    prologue = collection.prologues[0]
    purpose = prologue.find_section(SectionRole.PURPOSE)
    assert purpose is not None
    assert purpose.plain_text() == (
        "Equatorial to horizon coordinates:  HA,Dec to Az,El\n\n(double precision)"
    )
    called = prologue.sections[-1]
    assert called.title == "Called"
    assert called.plain_text() == "sla_DRANRM"


def test_program_unit_has_a_name_but_no_invocation() -> None:
    """A main program is not called, so no invocation is supplied."""
    collection = parse_text(
        """\
      PROGRAM ASTROM
*+
*  - - - - - - -
*   A S T R O M
*  - - - - - - -
*
*  This module is a front-end.
*-
""",
        source="astrom.f",
    )

    prologue = collection.prologues[0]
    assert prologue.name == "ASTROM"
    assert prologue.find_section(SectionRole.INVOCATION) is None


def test_purpose_prose_ending_in_a_colon_is_not_a_heading() -> None:
    """A heading is followed by a blank line or by more-indented content."""
    collection = parse_text(
        """\
      SUBROUTINE sla_S2TP (RA, DEC, RAZ, DECZ, XI, ETA, J)
*+
*     - - - - -
*      S 2 T P
*     - - - - -
*
*  Projection of spherical coordinates onto tangent plane:
*  "gnomonic" projection - "standard coordinates"
*  (single precision)
*
*  Given:
*     RA,DEC      real  spherical coordinates of point to be projected
*-
""",
        source="s2tp.f",
    )

    prologue = collection.prologues[0]
    purpose = prologue.find_section(SectionRole.PURPOSE)
    assert purpose is not None
    assert purpose.plain_text().splitlines()[0] == ("Projection of spherical coordinates onto tangent plane:")
    assert [section.title for section in prologue.sections] == [
        "Name",
        "Purpose",
        "Invocation",
        "Arguments",
    ]


def test_purpose_prose_with_a_one_word_label_is_not_a_heading() -> None:
    """A label whose continuation sits at the same column is still prose."""
    collection = parse_text(
        """\
      SUBROUTINE sla_NUTC (DATE, DPSI, DEPS, EPS0)
*+
*     - - - - -
*      N U T C
*     - - - - -
*
*  Nutation:  longitude & obliquity components and mean obliquity,
*  using the Shirai & Fukushima (2001) theory.
*
*  Given:
*     DATE        d    TDB as Modified Julian Date
*-
""",
        source="nutc.f",
    )

    prologue = collection.prologues[0]
    purpose = prologue.find_section(SectionRole.PURPOSE)
    assert purpose is not None
    assert purpose.plain_text() == (
        "Nutation:  longitude & obliquity components and mean obliquity,\n"
        "using the Shirai & Fukushima (2001) theory."
    )
    assert [section.title for section in prologue.sections] == [
        "Name",
        "Purpose",
        "Invocation",
        "Arguments",
    ]


def test_unlabelled_trailing_lines_do_not_join_the_previous_section() -> None:
    """Author and copyright lines sit at heading level and stay separate."""
    collection = parse_text(
        _DTP2S.replace(
            "*  Called:        sla_DRANRM\n*-\n",
            "*  Called:        sla_DRANRM\n"
            "*\n"
            "*  P.T.Wallace   Starlink   24 July 1995\n"
            "*\n"
            "*  Copyright (C) 1995 Rutherford Appleton Laboratory\n"
            "*-\n",
        ),
        source="dtp2s.f",
    )

    prologue = collection.prologues[0]
    called = next(s for s in prologue.sections if s.title == "Called")
    assert called.plain_text() == "sla_DRANRM"
    assert [section.title for section in prologue.sections[-2:]] == [
        "P.T.Wallace   Starlink   24 July 1995",
        "Copyright (C) 1995 Rutherford Appleton Laboratory",
    ]


def test_argument_sections_become_one_arguments_section() -> None:
    """Given and Returned merge into Arguments, each entry given its mode."""
    collection = parse_text(_DTP2S, source="dtp2s.f")

    prologue = collection.prologues[0]
    arguments = prologue.find_section(SectionRole.ARGUMENTS)
    assert arguments is not None
    assert [subsection.title for subsection in arguments.subsections] == [
        "XI,ETA = dp (Given)",
        "RAZ,DECZ = dp (Given)",
        "RA,DEC = dp (Returned)",
    ]
    assert arguments.subsections[0].plain_text() == ("tangent plane rectangular coordinates")
    assert [section.title for section in prologue.sections] == [
        "Name",
        "Purpose",
        "Invocation",
        "Arguments",
        "Called",
    ]


def test_given_and_returned_entries_keep_their_access_mode() -> None:
    """The third heading spelling supplies the combined access mode."""
    collection = parse_text(
        """\
      SUBROUTINE sla_COMBN (NSEL, NCAND, LIST, J)
*+
*     - - - - - -
*      C O M B N
*     - - - - - -
*
*  Generate the next combination.
*
*  Given and returned:
*     LIST     i(NSEL)  latest combination, LIST(1)=0 to initialize
*
*  Returned:
*     J        i        status: -1 = illegal NSEL or NCAND
*-
""",
        source="combn.f",
    )

    arguments = collection.prologues[0].find_section(SectionRole.ARGUMENTS)
    assert arguments is not None
    assert [subsection.title for subsection in arguments.subsections] == [
        "LIST = i(NSEL) (Given and Returned)",
        "J = i (Returned)",
    ]


def test_argument_description_continuation_lines_are_kept() -> None:
    """A line indented past its entry continues that entry's description."""
    collection = parse_text(
        """\
      SUBROUTINE sla_NUT (DATE, RMATN)
*+
*     - - - -
*      N U T
*     - - - -
*
*  Form the matrix of nutation.
*
*  Given:
*     DATE        d    TDB (loosely ET) as Modified Julian Date
*                                            (JD-2400000.5)
*-
""",
        source="nut.f",
    )

    arguments = collection.prologues[0].find_section(SectionRole.ARGUMENTS)
    assert arguments is not None
    assert arguments.subsections[0].title == "DATE = d (Given)"
    assert arguments.subsections[0].plain_text() == (
        "TDB (loosely ET) as Modified Julian Date\n(JD-2400000.5)"
    )


def test_argument_name_and_type_may_share_a_single_space() -> None:
    """Only the description is reliably set off by a run of spaces."""
    collection = parse_text(
        """\
      SUBROUTINE sla_AOPPA (ELONGM, PHI)
*+
*     - - - - - -
*      A O P P A
*     - - - - - -
*
*  Precompute apparent to observed place parameters.
*
*  Given:
*     ELONGM d      mean longitude of the observer (radians, east +ve)
*     AOPRMS d(14)  star-independent parameters
*-
""",
        source="aoppa.f",
    )

    arguments = collection.prologues[0].find_section(SectionRole.ARGUMENTS)
    assert arguments is not None
    assert [subsection.title for subsection in arguments.subsections] == [
        "ELONGM = d (Given)",
        "AOPRMS = d(14) (Given)",
    ]


def test_argument_lines_that_are_not_entries_are_kept_verbatim() -> None:
    """Prose and qualifiers inside an argument list are not rewritten."""
    collection = parse_text(
        """\
      SUBROUTINE sla_FK425 (R1950, D1950)
*+
*     - - - - - -
*      F K 4 2 5
*     - - - - - -
*
*  Convert B1950.0 FK4 to J2000.0 FK5.
*
*  Given:  (all B1950.0,FK4)
*     R1950,D1950     dp    B1950.0,FK4 RA,Dec
*     NVEC takes the following values:
*-
""",
        source="fk425.f",
    )

    arguments = collection.prologues[0].find_section(SectionRole.ARGUMENTS)
    assert arguments is not None
    assert [subsection.title for subsection in arguments.subsections] == [
        "(all B1950.0,FK4)",
        "R1950,D1950 = dp (Given)",
        "NVEC takes the following values:",
    ]


def test_slalib_arguments_render_with_the_arguments_macro() -> None:
    """The merged section reaches the renderer as a genuine argument list."""
    result = render_latex(parse_text(_DTP2S, source="dtp2s.f"))

    assert "   \\sstarguments{" in result
    assert "         XI,ETA = dp (Given)" in result


def test_text_at_heading_level_ends_the_argument_list() -> None:
    """Only lines indented past the heading belong to the argument list."""
    collection = parse_text(
        """\
      DOUBLE PRECISION FUNCTION sla_AIRMAS (ZD)
*+
*     - - - - - - -
*      A I R M A S
*     - - - - - - -
*
*  Air mass at given zenith distance (double precision)
*
*  Given:
*     ZD     d     Observed zenith distance (radians)
*
*  The result is an estimate of the air mass, in units of that
*  at the zenith.
*-
""",
        source="airmas.f",
    )

    prologue = collection.prologues[0]
    arguments = prologue.find_section(SectionRole.ARGUMENTS)
    assert arguments is not None
    assert [subsection.title for subsection in arguments.subsections] == ["ZD = d (Given)"]
    assert "The result is an estimate of the air mass, in units of that" in [
        section.title for section in prologue.sections
    ]
