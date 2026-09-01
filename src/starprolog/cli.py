from __future__ import annotations

__all__ = ("main",)

from pathlib import Path
from typing import TextIO

import click

from .latex import LatexMode, LatexOptions, render_latex
from .models import InputLanguage
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
def parse_command(inputs: tuple[Path, ...], language: str, output: TextIO, compact: bool) -> None:
    """Parse INPUTS and write the renderer-independent JSON model."""
    collection = parse_paths(inputs, language=InputLanguage(language.casefold()))
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
    language: str,
    mode: str,
    document: bool,
    page_breaks: bool,
    output: TextIO,
) -> None:
    """Render prologues from INPUTS as Starlink-compatible LaTeX."""
    collection = parse_paths(inputs, language=InputLanguage(language.casefold()))
    options = LatexOptions(
        mode=LatexMode(mode.casefold()),
        document=document,
        page_breaks=page_breaks,
    )
    try:
        output.write(render_latex(collection, options=options))
    except ValueError as error:
        raise click.ClickException(str(error)) from error
