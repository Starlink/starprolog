from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from starprolog import (
    DocumentationMode,
    InputFormat,
    PrologueCollection,
    SectionRole,
    SourceSpan,
    parse_paths,
    parse_text,
)


def test_collection_json_round_trip() -> None:
    """A dumped collection validates back into an equal model."""
    source = """\
*+
*  Name:
*     EXAMPLE
*  Purpose:
*     Exercise JSON.
*-
"""
    collection = parse_text(source)

    restored = PrologueCollection.model_validate_json(collection.model_dump_json())

    assert restored == collection
    assert restored.schema_version == 1


def test_source_span_rejects_reversed_lines() -> None:
    """Source spans must have monotonically increasing lines."""
    with pytest.raises(ValidationError, match="end_line must not precede"):
        SourceSpan(path="source.f", start_line=3, end_line=2)


def test_multiple_json_collections_are_combined(tmp_path: Path) -> None:
    """Serialized collections are loaded and combined in input order."""
    first = parse_text("*+\n*  Name:\n*     FIRST\n*  Purpose:\n*     First.\n*-\n")
    second = parse_text("*+\n*  Name:\n*     SECOND\n*  Purpose:\n*     Second.\n*-\n")
    paths = (tmp_path / "first.json", tmp_path / "second.json")
    paths[0].write_text(first.model_dump_json(), encoding="utf-8")
    paths[1].write_text(second.model_dump_json(), encoding="utf-8")

    combined = parse_paths(paths, input_format=InputFormat.JSON)

    assert [prologue.name for prologue in combined.prologues] == ["FIRST", "SECOND"]
    assert combined.metadata.input_format is InputFormat.JSON
    assert combined.metadata.source_count == 2


def test_ir_section_navigation_and_mode_inference() -> None:
    """Shared document semantics are available directly from the IR."""
    collection = parse_text(
        "*+\n*  Name:\n*     TASK\n*  Purpose:\n*     First line.\n"
        "*\n*     Second paragraph.\n*  Type of Module:\n*     ADAM A-task\n"
        "*  Bugs:\n*     {note_any_bugs_here}\n*-\n"
    )
    prologue = collection.prologues[0]

    purpose = prologue.find_section(SectionRole.PURPOSE, nonempty=True)
    assert purpose is not None
    assert purpose.has_content
    assert purpose.plain_text() == "First line.\n\nSecond paragraph."
    assert prologue.find_section(SectionRole.BUGS) is not None
    assert prologue.find_section(SectionRole.BUGS, nonempty=True) is None
    assert prologue.inferred_mode is DocumentationMode.ATASK
    assert prologue.resolve_mode() is DocumentationMode.ATASK
    assert prologue.resolve_mode(DocumentationMode.LIBRARY) is DocumentationMode.LIBRARY
