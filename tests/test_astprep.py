from __future__ import annotations

from starprolog import (
    AstEntityKind,
    AstPrepOptions,
    AstPrepResult,
    InputLanguage,
    ParagraphBlock,
    SectionRole,
    parse_text,
    prepare_ast,
    render_ast_latex,
)


def test_prepare_c_routines_sorts_rewrites_and_labels() -> None:
    """C routine preprocessing reproduces the getatt transformations."""
    collection = parse_text(
        _routine("astZulu", "AST_ZULU") + _routine("astAlpha", "AST_ALPHA"),
        language=InputLanguage.C,
    )
    options = AstPrepOptions(language=InputLanguage.C)

    result = prepare_ast(collection, options=options)

    assert [prologue.name for prologue in result.collection.prologues] == ["astAlpha", "astZulu"]
    assert result.labels == ("astAlpha", "astZulu")
    synopsis = result.collection.prologues[0].sections[2]
    assert synopsis.role is SectionRole.INVOCATION
    assert synopsis.title == "Invocation"
    assert isinstance(synopsis.blocks[0], ParagraphBlock)
    assert synopsis.blocks[0].lines == ("void astAlpha( int value )",)
    assert all(section.role is not SectionRole.TYPE for section in result.collection.prologues[0].sections)
    latex = render_ast_latex(result)
    assert "\\sstsynopsis{" in latex
    assert "\\sstparameters{" in latex
    assert "#include" not in latex


def test_prepare_fortran_attribute_and_json_round_trip() -> None:
    """Attribute preprocessing emits its special type macro and JSON model."""
    collection = parse_text(
        """\
/*
*att++
*  Name:
c     Ident
f     IDENT
*  Purpose:
*     Identify an object.
*  Synopsis:
c     Integer.
f     INTEGER
*  Description:
*     An identifying value.
*  Applicability:
*     Object
*        All objects.
*att--
*/
""",
        language=InputLanguage.FORTRAN,
    )
    options = AstPrepOptions(kind=AstEntityKind.ATTRIBUTE, language=InputLanguage.FORTRAN)

    result = prepare_ast(collection, options=options)
    restored = AstPrepResult.model_validate_json(result.model_dump_json())

    assert restored == result
    assert result.labels == ("IDENT",)
    latex = render_ast_latex(result)
    assert "\\sstattributetype{" in latex
    assert "\\sstapplicability{" in latex


def test_fortran_routines_keep_general_sst_macros() -> None:
    """Fortran mode retains the invocation and arguments macro names."""
    collection = parse_text(
        _routine("astAlpha", "AST_ALPHA"),
        language=InputLanguage.FORTRAN,
    )
    options = AstPrepOptions(language=InputLanguage.FORTRAN)

    latex = render_ast_latex(prepare_ast(collection, options=options))

    assert "\\sstinvocation{" in latex
    assert "\\sstarguments{" in latex
    assert "\\sstsynopsis{" not in latex


def test_prepare_class_constructor() -> None:
    """Class constructor sections use the AST constructor macro."""
    collection = parse_text(
        """\
/*
*class++
*  Name:
*     Circle
*  Purpose:
*     Represent a circle.
*  Constructor Function:
*     astCircle
*  Description:
*     A circular region.
*  Class Membership:
*     Region.
*class--
*/
""",
        language=InputLanguage.C,
    )
    options = AstPrepOptions(kind=AstEntityKind.CLASS)

    result = prepare_ast(collection, options=options)

    assert "\\sstconstructor{" in render_ast_latex(result)
    assert "Class Membership" not in render_ast_latex(result)


def test_unix_script_selects_hash_prologues_without_rewriting() -> None:
    """Select hash markers and retain Invocation sections in Unix mode."""
    collection = parse_text(
        """\
#++
#  Name:
#     ast_link
#  Purpose:
#     Link an AST program.
#  Invocation:
#     ast_link program
#  Description:
#     Run the linker.
#--
""",
        language=InputLanguage.C,
    )
    options = AstPrepOptions(language=InputLanguage.C, unix_script=True)

    result = prepare_ast(collection, options=options)
    latex = render_ast_latex(result)

    assert result.labels == (r"ast\_link",)
    assert "\\sstinvocation{" in latex
    assert "\\sstsynopsis{" not in latex


def _routine(c_name: str, fortran_name: str) -> str:
    return f"""\
/*
*++
*  Name:
c     {c_name}
f     {fortran_name}
*  Purpose:
*     Exercise AST preprocessing.
*  Synopsis:
c     #include "ast.h"
c     void {c_name}( int value )
f     CALL {fortran_name}( VALUE, STATUS )
*  Description:
*     A public routine.
*  Parameters:
c     value
f     VALUE = INTEGER (Given)
*        A value.
*  Type:
*     Public.
*  Copyright:
*     Copyright text.
*--
*/
"""
