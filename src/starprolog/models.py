from __future__ import annotations

__all__ = (
    "Block",
    "CollectionMetadata",
    "Diagnostic",
    "DiagnosticSeverity",
    "DocumentationMode",
    "InputFormat",
    "InputLanguage",
    "ItemListBlock",
    "LineBlock",
    "ListItem",
    "ParagraphBlock",
    "Prologue",
    "PrologueCollection",
    "PrologueKind",
    "PrologueMarker",
    "PrologueSyntax",
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


class InputFormat(StrEnum):
    """Source-prologue or serialized IR format selected for input."""

    AUTO = "auto"
    STARLSE = "starlse"
    ADAMSSE = "adamsse"
    JSON = "json"


class PrologueSyntax(StrEnum):
    """Concrete source syntax detected for one prologue."""

    STARLSE = "starlse"
    ADAMSSE_FORTRAN = "adamsse-fortran"
    ADAMSSE_C = "adamsse-c"


class DiagnosticSeverity(StrEnum):
    """Severity assigned to a parser diagnostic."""

    WARNING = "warning"
    ERROR = "error"


class DocumentationMode(StrEnum):
    """Kind of Starlink documentation represented by a prologue."""

    AUTO = "auto"
    ATASK = "atask"
    LIBRARY = "library"


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
    marker_indent: int = Field(default=0, ge=0)
    """Indentation of the opening ``---`` marker, relative to the section body.

    Renderers measure preserved indentation from the marker rather than from
    the block content, so a uniformly indented block keeps its indentation.
    """

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

    @property
    def has_content(self) -> bool:
        """Whether this section contains blocks or subsections.

        Returns
        -------
        has_content : `bool`
            `True` when the section contains parsed content.
        """
        return bool(self.blocks or self.subsections)

    def plain_text(self) -> str:
        """Flatten the section content into unescaped plain text.

        Returns
        -------
        text : `str`
            Source-wrapped text with blank lines between paragraph blocks.
        """
        lines: list[str] = []
        for block in self.blocks:
            if isinstance(block, ParagraphBlock):
                if lines:
                    lines.append("")
                lines.extend(block.lines)
            elif isinstance(block, ItemListBlock):
                for item in block.items:
                    lines.extend(item.lines)
            elif isinstance(block, LineBlock):
                lines.extend(block.lines)
        for subsection in self.subsections:
            if lines:
                lines.append("")
            lines.append(subsection.title)
            text = subsection.plain_text()
            if text:
                lines.extend(text.splitlines())
        return "\n".join(lines)


class Prologue(FrozenModel):
    """One parsed source-code prologue."""

    name: str | None = None
    syntax: PrologueSyntax = PrologueSyntax.STARLSE
    marker: PrologueMarker
    source: SourceSpan
    sections: tuple[Section, ...]

    def find_section(
        self,
        role: SectionRole,
        *,
        nonempty: bool = False,
    ) -> Section | None:
        """Find the first section with a given semantic role.

        Parameters
        ----------
        role
            Semantic role to locate.
        nonempty
            If `True`, ignore sections without blocks or subsections.

        Returns
        -------
        section : `Section` or `None`
            Matching section, or `None` if no suitable section exists.
        """
        return next(
            (
                section
                for section in self.sections
                if section.role is role and (not nonempty or section.has_content)
            ),
            None,
        )

    @property
    def inferred_mode(self) -> DocumentationMode:
        """Infer whether this is an A-task or library prologue.

        Returns
        -------
        mode : `DocumentationMode`
            Inferred documentation mode. Prologues not explicitly identified
            as A-tasks are treated as library routines.
        """
        module_type = self.find_section(SectionRole.TYPE_OF_MODULE)
        if module_type is None:
            return DocumentationMode.LIBRARY
        normalized = module_type.plain_text().casefold().replace("-", " ")
        if "a task" in normalized or "atask" in normalized:
            return DocumentationMode.ATASK
        return DocumentationMode.LIBRARY

    def resolve_mode(
        self,
        requested: DocumentationMode = DocumentationMode.AUTO,
    ) -> DocumentationMode:
        """Resolve an explicit or automatic documentation mode.

        Parameters
        ----------
        requested
            Requested mode. `DocumentationMode.AUTO` selects the mode inferred
            from the prologue.

        Returns
        -------
        mode : `DocumentationMode`
            Effective A-task or library mode.
        """
        if requested is DocumentationMode.AUTO:
            return self.inferred_mode
        return requested


class CollectionMetadata(FrozenModel):
    """Reader settings recorded with a collection of prologues."""

    language: InputLanguage
    input_format: InputFormat = InputFormat.AUTO
    source_count: int = Field(ge=0)


class PrologueCollection(FrozenModel):
    """Versioned, renderer-independent collection of parsed prologues."""

    schema_version: Literal[1] = 1
    reader: Literal["starlink"] = "starlink"
    metadata: CollectionMetadata
    prologues: tuple[Prologue, ...]
    diagnostics: tuple[Diagnostic, ...] = ()
