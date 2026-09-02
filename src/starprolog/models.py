from __future__ import annotations

__all__ = (
    "Block",
    "CollectionMetadata",
    "Diagnostic",
    "DiagnosticSeverity",
    "InputLanguage",
    "ItemListBlock",
    "LineBlock",
    "ListItem",
    "ParagraphBlock",
    "Prologue",
    "PrologueCollection",
    "PrologueKind",
    "PrologueMarker",
    "Section",
    "SectionRole",
    "SourceSpan",
)

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FrozenModel(BaseModel):
    """Base class for immutable intermediate-representation models."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class InputLanguage(StrEnum):
    """Language-specific source lines selected while reading."""

    ALL = "all"
    C = "c"
    FORTRAN = "fortran"


class DiagnosticSeverity(StrEnum):
    """Severity assigned to a parser diagnostic."""

    WARNING = "warning"
    ERROR = "error"


class PrologueKind(StrEnum):
    """Known meaning of a Starlink prologue delimiter."""

    STANDARD = "standard"
    PUBLIC = "public"
    ATTRIBUTE = "attribute"
    CLASS = "class"
    TAGGED = "tagged"


class SectionRole(StrEnum):
    """Canonical semantic role assigned to a known section heading."""

    ADAM_PARAMETERS = "adam_parameters"
    ALGORITHM = "algorithm"
    APPLICABILITY = "applicability"
    ARGUMENTS = "arguments"
    AUTHORS = "authors"
    BUGS = "bugs"
    CLASS_MEMBERSHIP = "class_membership"
    CONSTRUCTOR_FUNCTION = "constructor_function"
    COPYRIGHT = "copyright"
    DESCRIPTION = "description"
    EXAMPLES = "examples"
    HISTORY = "history"
    IMPLEMENTATION_STATUS = "implementation_status"
    IMPLEMENTATION_DEFICIENCIES = "implementation_deficiencies"
    INVOCATION = "invocation"
    LANGUAGE = "language"
    LICENCE = "licence"
    NAME = "name"
    NOTES = "notes"
    PARAMETERS = "parameters"
    PURPOSE = "purpose"
    RETURNED_VALUE = "returned_value"
    SYNOPSIS = "synopsis"
    TYPE = "type"
    TYPE_OF_MODULE = "type_of_module"
    USAGE = "usage"


class SourceSpan(FrozenModel):
    """Inclusive line range in an input source."""

    path: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_line_order(self) -> SourceSpan:
        """Ensure the end of the span does not precede its start."""
        if self.end_line < self.start_line:
            raise ValueError("end_line must not precede start_line")
        return self


class Diagnostic(FrozenModel):
    """Warning or error associated with source parsing."""

    severity: DiagnosticSeverity
    code: str
    message: str
    source: SourceSpan | None = None


class PrologueMarker(FrozenModel):
    """Delimiter metadata retained from a Starlink prologue."""

    comment_character: str = Field(min_length=1, max_length=1)
    tag: str = ""
    delimiter_width: int = Field(ge=1, le=2)
    kind: PrologueKind


class ParagraphBlock(FrozenModel):
    """Ordinary paragraph whose source wrapping is retained."""

    type: Literal["paragraph"] = "paragraph"
    lines: tuple[str, ...]
    source: SourceSpan


class LineBlock(FrozenModel):
    """Text for which line breaks and relative indentation are significant."""

    type: Literal["line_block"] = "line_block"
    lines: tuple[str, ...]
    source: SourceSpan


class ListItem(FrozenModel):
    """A single hyphen-led list item."""

    lines: tuple[str, ...]
    source: SourceSpan


class ItemListBlock(FrozenModel):
    """A sequence of hyphen-led items."""

    type: Literal["item_list"] = "item_list"
    items: tuple[ListItem, ...]
    source: SourceSpan


Block = Annotated[ParagraphBlock | LineBlock | ItemListBlock, Field(discriminator="type")]


class Section(FrozenModel):
    """A named prologue section with blocks and optional child sections."""

    title: str
    role: SectionRole | None = None
    source: SourceSpan
    blocks: tuple[Block, ...] = ()
    subsections: tuple[Section, ...] = ()


class Prologue(FrozenModel):
    """One parsed source-code prologue."""

    name: str | None = None
    marker: PrologueMarker
    source: SourceSpan
    sections: tuple[Section, ...]


class CollectionMetadata(FrozenModel):
    """Reader settings recorded with a collection of prologues."""

    language: InputLanguage
    source_count: int = Field(ge=0)


class PrologueCollection(FrozenModel):
    """Versioned, renderer-independent collection of parsed prologues."""

    schema_version: Literal[1] = 1
    reader: Literal["starlink"] = "starlink"
    metadata: CollectionMetadata
    prologues: tuple[Prologue, ...]
    diagnostics: tuple[Diagnostic, ...] = ()
