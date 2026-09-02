from __future__ import annotations

__all__ = ("main",)

from pathlib import Path
from typing import TextIO

import click

from .astprep import AstEntityKind, AstPrepOptions, prepare_ast, render_ast_latex
from .latex import LatexMode, LatexOptions, render_latex
from .models import InputFormat, InputLanguage
from .reader import parse_paths


@click.group(name="starprolog", context_settings={"help_option_names": ["-h", "--help"]})
def main() -> None:
    """Parse and render Starlink-style source-code prologues."""


@main.command(name="parse")
@click.argument(
    "inputs",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--input-format",
    type=click.Choice([input_format.value for input_format in InputFormat], case_sensitive=False),
    default=InputFormat.AUTO.value,
    show_default=True,
    help="Detect STARLSE and old ADAM/SSE prologues, or select one format.",
)
@click.option(
    "--language",
    type=click.Choice([language.value for language in InputLanguage], case_sensitive=False),
    default=InputLanguage.ALL.value,
    show_default=True,
    help="Select language-specific lines in AST-style public prologues.",
)
@click.option(
    "-o",
    "--output",
    type=click.File(mode="w", encoding="utf-8", lazy=True),
    default="-",
    show_default="standard output",
    help="Write the Pydantic intermediate representation as JSON.",
)
@click.option("--compact", is_flag=True, help="Write JSON without indentation.")
def parse_command(
    inputs: tuple[Path, ...],
    input_format: str,
    language: str,
    output: TextIO,
    compact: bool,
) -> None:
    """Parse INPUTS and write the renderer-independent JSON model."""
    collection = parse_paths(
        inputs,
        language=InputLanguage(language.casefold()),
        input_format=InputFormat(input_format.casefold()),
    )
    indent = None if compact else 2
    output.write(collection.model_dump_json(indent=indent))
    output.write("\n")


@main.command(name="latex")
@click.argument(
    "inputs",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--input-format",
    type=click.Choice([input_format.value for input_format in InputFormat], case_sensitive=False),
    default=InputFormat.AUTO.value,
    show_default=True,
    help="Detect STARLSE and old ADAM/SSE prologues, or select one format.",
)
@click.option(
    "--language",
    type=click.Choice([language.value for language in InputLanguage], case_sensitive=False),
    default=InputLanguage.ALL.value,
    show_default=True,
    help="Select language-specific lines in AST-style public prologues.",
)
@click.option(
    "--mode",
    type=click.Choice([mode.value for mode in LatexMode], case_sensitive=False),
    default=LatexMode.AUTO.value,
    show_default=True,
    help="Render an A-task, a library routine, or infer the mode from each prologue.",
)
@click.option(
    "--document/--fragment",
    default=False,
    show_default=True,
    help="Write a complete standalone document or a Starlink macro fragment.",
)
@click.option(
    "--page-breaks/--no-page-breaks",
    default=False,
    show_default=True,
    help="Start every prologue after the first on a new page.",
)
@click.option(
    "-o",
    "--output",
    type=click.File(mode="w", encoding="utf-8", lazy=True),
    default="-",
    show_default="standard output",
    help="Write the rendered LaTeX to this file.",
)
def latex_command(
    inputs: tuple[Path, ...],
    input_format: str,
    language: str,
    mode: str,
    document: bool,
    page_breaks: bool,
    output: TextIO,
) -> None:
    """Render prologues from INPUTS as Starlink-compatible LaTeX."""
    collection = parse_paths(
        inputs,
        language=InputLanguage(language.casefold()),
        input_format=InputFormat(input_format.casefold()),
    )
    options = LatexOptions(
        mode=LatexMode(mode.casefold()),
        document=document,
        page_breaks=page_breaks,
    )
    try:
        output.write(render_latex(collection, options=options))
    except ValueError as error:
        raise click.ClickException(str(error)) from error


@main.command(name="astprep")
@click.argument(
    "inputs",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--kind",
    type=click.Choice([kind.value for kind in AstEntityKind], case_sensitive=False),
    default=AstEntityKind.ROUTINE.value,
    show_default=True,
    help="Select AST routine, attribute, or class prologues.",
)
@click.option(
    "--language",
    type=click.Choice([InputLanguage.C.value, InputLanguage.FORTRAN.value], case_sensitive=False),
    default=InputLanguage.C.value,
    show_default=True,
    help="Select C or Fortran lines from the AST prologues.",
)
@click.option(
    "--unix-script",
    is_flag=True,
    help="Select hash-comment command prologues, corresponding to getatt -u.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["latex", "json"], case_sensitive=False),
    default="latex",
    show_default=True,
    help="Write drop-in getatt LaTeX or the AST-preprocessed Pydantic model.",
)
@click.option(
    "--labels",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Write escaped AST entity names in getatt.labels format.",
)
@click.option(
    "-o",
    "--output",
    type=click.File(mode="w", encoding="utf-8", lazy=True),
    default="-",
    show_default="standard output",
    help="Write the prepared output to this file.",
)
def astprep_command(
    inputs: tuple[Path, ...],
    kind: str,
    language: str,
    unix_script: bool,
    output_format: str,
    labels: Path | None,
    output: TextIO,
) -> None:
    """Prepare AST documentation prologues from INPUTS."""
    options = AstPrepOptions(
        kind=AstEntityKind(kind.casefold()),
        language=InputLanguage(language.casefold()),
        unix_script=unix_script,
    )
    collection = parse_paths(
        inputs,
        language=options.language,
        input_format=InputFormat.STARLSE,
    )
    prepared = prepare_ast(collection, options=options)
    if labels is not None:
        label_text = "".join(f"{label}\n" for label in prepared.labels)
        labels.write_text(label_text, encoding="utf-8")
    if output_format.casefold() == "json":
        output.write(prepared.model_dump_json(indent=2))
        output.write("\n")
    else:
        output.write(render_ast_latex(prepared))
