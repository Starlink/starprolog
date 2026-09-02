from __future__ import annotations

__all__ = (
    "AstEntityKind",
    "AstPrepOptions",
    "AstPrepResult",
    "escape_ast_label",
    "prepare_ast",
    "render_ast_latex",
)

from enum import StrEnum
from typing import Literal

from pydantic import model_validator

from .latex import LatexOptions, render_latex
from .models import (
    Block,
    CollectionMetadata,
    Diagnostic,
    DiagnosticSeverity,
    DocumentationMode,
    FrozenModel,
    InputLanguage,
    ParagraphBlock,
    Prologue,
    PrologueCollection,
    PrologueKind,
    Section,
    SectionRole,
)


class AstEntityKind(StrEnum):
    """AST documentation entity selected from tagged prologues."""

    ROUTINE = "routine"
    ATTRIBUTE = "attribute"
    CLASS = "class"


class AstPrepOptions(FrozenModel):
    """Options controlling the AST-specific preprocessing extension."""

    kind: AstEntityKind = AstEntityKind.ROUTINE
    language: InputLanguage = InputLanguage.C
    unix_script: bool = False

    @model_validator(mode="after")
    def validate_options(self) -> AstPrepOptions:
        """Reject option combinations that have no getatt equivalent."""
        if self.language is InputLanguage.ALL:
            raise ValueError("AST preprocessing requires C or Fortran language selection")
        if self.unix_script and self.kind is not AstEntityKind.ROUTINE:
            raise ValueError("Unix-script preprocessing only supports routine prologues")
        return self


class AstPrepResult(FrozenModel):
    """AST-preprocessed prologues and their escaped documentation labels."""

    extension: Literal["ast"] = "ast"
    options: AstPrepOptions
    collection: PrologueCollection
    labels: tuple[str, ...]


_MARKER_KINDS = {
    AstEntityKind.ROUTINE: PrologueKind.PUBLIC,
    AstEntityKind.ATTRIBUTE: PrologueKind.ATTRIBUTE,
    AstEntityKind.CLASS: PrologueKind.CLASS,
}

_REMOVED_ROLES = {
    SectionRole.TYPE,
    SectionRole.CLASS_MEMBERSHIP,
    SectionRole.COPYRIGHT,
}


def prepare_ast(collection: PrologueCollection, *, options: AstPrepOptions) -> AstPrepResult:
    """Apply the AST ``getatt`` transformations to parsed prologues.

    Parameters
    ----------
    collection
        Prologues parsed with the language selected in ``options``.
    options
        AST entity, language, and source-comment selection.

    Returns
    -------
    result : `AstPrepResult`
        Sorted, transformed prologues and escaped labels.
    """
    if collection.metadata.language is not options.language:
        raise ValueError("collection language does not match the AST preprocessing language")

    expected_marker = _MARKER_KINDS[options.kind]
    if options.unix_script:
        expected_comments = {"#"}
    else:
        language_comment = "c" if options.language is InputLanguage.C else "f"
        expected_comments = {"*", language_comment}
    by_name: dict[str, Prologue] = {}
    diagnostics = list(collection.diagnostics)

    for prologue in collection.prologues:
        if prologue.marker.kind is not expected_marker:
            continue
        if prologue.marker.delimiter_width != 2:
            continue
        if prologue.marker.comment_character not in expected_comments:
            continue
        if prologue.name is None:
            diagnostics.append(
                Diagnostic(
                    severity=DiagnosticSeverity.WARNING,
                    code="ast-missing-name",
                    message="AST documentation prologue has no usable Name section.",
                    source=prologue.source,
                )
            )
            continue
        by_name[prologue.name] = _transform_prologue(prologue, options)

    prologues = tuple(by_name[name] for name in sorted(by_name))
    prepared_collection = PrologueCollection(
        metadata=CollectionMetadata(
            language=options.language,
            input_format=collection.metadata.input_format,
            source_count=collection.metadata.source_count,
        ),
        prologues=prologues,
        diagnostics=tuple(diagnostics),
    )
    return AstPrepResult(
        options=options,
        collection=prepared_collection,
        labels=tuple(escape_ast_label(name) for name in sorted(by_name)),
    )


def escape_ast_label(name: str) -> str:
    """Escape an AST entity name using the historical label conventions.

    Parameters
    ----------
    name
        Unescaped AST entity name.

    Returns
    -------
    label : `str`
        Name suitable for the AST global label files.
    """
    return name.replace("_", r"\_").replace(">", "$>$").replace("<", "$<$")


def render_ast_latex(result: AstPrepResult) -> str:
    """Render an AST-preprocessed result as a ``getatt`` LaTeX fragment.

    Parameters
    ----------
    result
        Prepared AST prologues and mode metadata.

    Returns
    -------
    latex : `str`
        Starlink-compatible LaTeX replacing ``getatt`` output.
    """
    latex = render_latex(
        result.collection,
        options=LatexOptions(mode=DocumentationMode.LIBRARY),
    )
    if result.options.unix_script:
        return latex
    if result.options.kind is AstEntityKind.ROUTINE:
        if result.options.language is InputLanguage.C:
            return latex.replace(r"\sstinvocation{", r"\sstsynopsis{").replace(
                r"\sstarguments{", r"\sstparameters{"
            )
        return latex
    if result.options.kind is AstEntityKind.ATTRIBUTE:
        return latex.replace(r"\sstinvocation{", r"\sstattributetype{")
    return latex.replace(r"\sstinvocation{", r"\sstconstructor{")


def _transform_prologue(prologue: Prologue, options: AstPrepOptions) -> Prologue:
    sections: list[Section] = []
    for section in prologue.sections:
        if section.role in _REMOVED_ROLES:
            continue
        transformed = section
        if not options.unix_script:
            transformed = _transform_section(section, options)
        sections.append(transformed)
    return Prologue(
        name=prologue.name,
        syntax=prologue.syntax,
        marker=prologue.marker,
        source=prologue.source,
        sections=tuple(sections),
    )


def _transform_section(section: Section, options: AstPrepOptions) -> Section:
    title = section.title
    role = section.role
    blocks = section.blocks

    if options.kind in {AstEntityKind.ROUTINE, AstEntityKind.ATTRIBUTE}:
        if role is SectionRole.SYNOPSIS:
            title = "Invocation"
            role = SectionRole.INVOCATION
            if options.kind is AstEntityKind.ROUTINE and options.language is InputLanguage.C:
                filtered_blocks: list[Block] = []
                for block in blocks:
                    filtered = _remove_c_includes(block)
                    if filtered is not None:
                        filtered_blocks.append(filtered)
                blocks = tuple(filtered_blocks)
    if options.kind is AstEntityKind.ROUTINE and role is SectionRole.PARAMETERS:
        title = "Arguments"
        role = SectionRole.ARGUMENTS
    elif options.kind is AstEntityKind.CLASS and role is SectionRole.CONSTRUCTOR_FUNCTION:
        title = "Invocation"
        role = SectionRole.INVOCATION

    return Section(
        title=title,
        role=role,
        source=section.source,
        blocks=blocks,
        subsections=section.subsections,
    )


def _remove_c_includes(block: Block) -> Block | None:
    if not isinstance(block, ParagraphBlock):
        return block
    lines = tuple(line for line in block.lines if not line.lstrip().startswith("#include"))
    if not lines:
        return None
    return ParagraphBlock(lines=lines, source=block.source)
