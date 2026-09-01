from __future__ import annotations

import pytest
from pydantic import ValidationError

from starprolog import PrologueCollection, SourceSpan, parse_text


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
