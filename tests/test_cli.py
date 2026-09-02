from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from starprolog.cli import main


def test_parse_command_writes_json(tmp_path: Path) -> None:
    """The parse command writes the complete model as JSON."""
    runner = CliRunner()
    source = tmp_path / "source.f"
    source.write_text(
        "*+\n*  Name:\n*     DEMO\n*  Purpose:\n*     Test CLI.\n*-\n",
        encoding="utf-8",
    )

    result = runner.invoke(main, ["parse", str(source)])

    assert result.exit_code == 0, result.output
    model = json.loads(result.output)
    assert model["schema_version"] == 1
    assert model["prologues"][0]["name"] == "DEMO"


def test_main_help_lists_parse_command() -> None:
    """The top-level help advertises the parse subcommand."""
    result = CliRunner().invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "astprep" in result.output
    assert "parse" in result.output
    assert "latex" in result.output


def test_latex_command_writes_fragment(tmp_path: Path) -> None:
    """The latex command renders source prologues directly."""
    runner = CliRunner()
    source = tmp_path / "source.f"
    source.write_text(
        "*+\n*  Name:\n*     DEMO\n*  Purpose:\n*     Test output.\n"
        "*  Invocation:\n*     CALL DEMO\n*  Description:\n*     Exercise CLI.\n*-\n",
        encoding="utf-8",
    )

    result = runner.invoke(main, ["latex", str(source)])

    assert result.exit_code == 0, result.output
    assert result.output.startswith("\\sstroutine{")
    assert "\\sstinvocation{" in result.output


def test_latex_command_auto_detects_old_adamsse_input(tmp_path: Path) -> None:
    """The LaTeX command renders an auto-detected legacy prologue."""
    runner = CliRunner()
    source = tmp_path / "old.f"
    source.write_text(
        "*+ OLD_DEMO - Test legacy input\n"
        "*    Description :\n"
        "*     Exercise automatic input detection.\n"
        "*    Type Definitions :\n",
        encoding="utf-8",
    )

    result = runner.invoke(main, ["latex", str(source)])

    assert result.exit_code == 0, result.output
    assert "OLD\\_DEMO" in result.output
    assert "automatic input detection" in result.output


def test_astprep_command_writes_latex_and_labels(tmp_path: Path) -> None:
    """The AST extension writes transformed LaTeX and escaped labels."""
    runner = CliRunner()
    source = tmp_path / "source.c"
    labels = tmp_path / "labels.txt"
    source.write_text(
        "/*\n*++\n*  Name:\nc     ast_Test\nf     AST_TEST\n"
        "*  Purpose:\n*     Test AST prep.\n*  Synopsis:\n"
        "c     void ast_Test( void )\nf     CALL AST_TEST( STATUS )\n"
        "*  Description:\n*     Exercise CLI.\n*--\n*/\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        main,
        ["astprep", "--labels", str(labels), str(source)],
    )

    assert result.exit_code == 0, result.output
    assert "\\sstsynopsis{" in result.output
    assert labels.read_text(encoding="utf-8") == "ast\\_Test\n"
