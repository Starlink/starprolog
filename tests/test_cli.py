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
