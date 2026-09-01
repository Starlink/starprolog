# starprolog

`starprolog` parses Starlink-style source-code prologues into a
renderer-independent document tree. The command-line interface will provide
LaTeX and Starlink help-library renderers; the first implementation milestone
provides JSON output for inspecting and testing the intermediate
representation.

The implementation is independent of the legacy Starlink SST implementation
and does not require a Starlink software installation.

## Development status

The public interface is under active development. The currently available
command parses one or more source files:

```sh
starprolog parse source.f source.c -o prologues.json
```

Use `--language c` or `--language fortran` to select language-specific lines
in AST-style public prologues. By default, both variants are retained.

## Development

Create the uv environment with the development dependencies and run the
checks with:

```sh
uv sync --python ~/pyenv/bin/python
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest
```

This project is distributed under the BSD 3-Clause License.
