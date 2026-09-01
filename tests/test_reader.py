from __future__ import annotations

from starprolog import (
    InputLanguage,
    ItemListBlock,
    LineBlock,
    ParagraphBlock,
    PrologueKind,
    SectionRole,
    parse_text,
)


def test_fortran_prologue_sections_and_subsections() -> None:
    """Fortran sections, subsections, lists, and placeholders are parsed."""
    source = """\
      SUBROUTINE DEMO( STATUS )
*+
*  Name:
*     DEMO

*  Purpose:
*     Demonstrate parsing.

*  Arguments:
*     STATUS = INTEGER (Given and Returned)
*        The global status.

*  Notes:
*     - First item.
*     - Second item continuing
*       on another line.

*  Authors:
*     AA: An Author
*     {enter_new_authors_here}
*-
      END
"""
    collection = parse_text(source, source="demo.f")

    assert not collection.diagnostics
    assert len(collection.prologues) == 1
    prologue = collection.prologues[0]
    assert prologue.name == "DEMO"
    assert prologue.marker.kind is PrologueKind.STANDARD
    assert [section.role for section in prologue.sections[:3]] == [
        SectionRole.NAME,
        SectionRole.PURPOSE,
        SectionRole.ARGUMENTS,
    ]
    arguments = prologue.sections[2]
    assert len(arguments.subsections) == 1
    assert arguments.subsections[0].title == "STATUS = INTEGER (Given and Returned)"
    assert isinstance(arguments.subsections[0].blocks[0], ParagraphBlock)
    notes = prologue.sections[3]
    assert isinstance(notes.blocks[0], ItemListBlock)
    assert notes.blocks[0].items[1].lines == ("Second item continuing", "on another line.")
    authors = prologue.sections[4]
    assert len(authors.subsections) == 1


def test_c_block_comment_can_end_implicitly() -> None:
    """A C block terminator can close a prologue without a star-minus line."""
    source = """\
/*
 *+
 *  Name:
 *     demo
 *  Purpose:
 *     Parse an indented C comment.
 */
int demo(void) { return 0; }
"""
    collection = parse_text(source, source="demo.c")

    assert not collection.diagnostics
    assert collection.prologues[0].name == "demo"
    assert collection.prologues[0].source.end_line == 7


def test_hash_prologue_in_extensionless_perl_source() -> None:
    """Hash comments are parsed without relying on a file extension."""
    source = """\
#+
# Name:
#    _DO_THING_
#
# Purpose:
#    Do a thing.
#
# Arguments:
#    NUMBER = INTEGER (Given)
#       Number of things.
#-
my $number = 1;
"""
    collection = parse_text(source, source="_DO_THING_")

    assert collection.prologues[0].name == "_DO_THING_"
    assert collection.prologues[0].marker.comment_character == "#"
    assert collection.prologues[0].sections[2].subsections[0].title.startswith("NUMBER")


def test_ast_public_prologue_selects_c_lines() -> None:
    """AST public markers and C-specific lines are retained in the model."""
    source = """\
/*
*++
*  Name:
c     astDemo
f     AST_DEMO
*  Synopsis:
c     int astDemo( int value )
f     RESULT = AST_DEMO( VALUE, STATUS )
*  Description:
*     A common description.
*--
*/
"""
    collection = parse_text(source, language=InputLanguage.C)

    prologue = collection.prologues[0]
    assert prologue.marker.kind is PrologueKind.PUBLIC
    assert prologue.name == "astDemo"
    assert prologue.sections[1].role is SectionRole.SYNOPSIS
    synopsis = prologue.sections[1].blocks[0]
    assert isinstance(synopsis, ParagraphBlock)
    assert synopsis.lines == ("int astDemo( int value )",)


def test_python_string_container_and_preserved_lines() -> None:
    """Triple-quoted prologues and preserved-line blocks are recognized."""
    source = """'''
*+
*  Name:
*     SCRIPT
*  Purpose:
*     Run a script.
*  Description:
*     Configuration follows.
*     ---
*        key = value
*          indented = true
*     ---
'''
print("done")
"""
    collection = parse_text(source, source="script.py")

    assert not collection.diagnostics
    description = collection.prologues[0].sections[2]
    assert isinstance(description.blocks[0], ParagraphBlock)
    assert isinstance(description.blocks[1], LineBlock)
    assert description.blocks[1].lines == ("key = value", "  indented = true")


def test_eof_terminated_prologue_is_retained_with_warning() -> None:
    """Legacy EOF termination retains content and emits a diagnostic."""
    source = """\
*+
*  Name:
*     UNFINISHED
*  Purpose:
*     Reach end of file.
"""
    collection = parse_text(source)

    assert collection.prologues[0].name == "UNFINISHED"
    assert [diagnostic.code for diagnostic in collection.diagnostics] == ["unterminated-prologue"]


def test_decorative_plus_ruler_is_not_a_prologue() -> None:
    """Decorative rulers with more than two signs are ignored."""
    collection = parse_text("*++++++++++++++++++++\n* text\n*--------------------\n")

    assert not collection.prologues
