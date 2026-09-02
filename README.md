# starprolog

`starprolog` parses Starlink-style source-code prologues into a
renderer-independent document tree. The command-line interface will provide
LaTeX and Starlink help-library renderers. The intermediate representation
can also be written as JSON for inspection and use by other tools.

The implementation is independent of the legacy Starlink SST implementation
and does not require a Starlink software installation.

## Development status

The public interface is under active development. Parse one or more source
files into the JSON intermediate representation with:

```sh
starprolog parse source.f source.c -o prologues.json
```

Input format detection recognizes both modern STARLSE prologues and the old
ADAM/SSE Fortran and BDK-style C conventions formerly handled by `procvt`.
Each prologue records its detected syntax in the intermediate representation.
Detection can be overridden with `--input-format starlse` or
`--input-format adamsse`.

Use `--language c` or `--language fortran` to select language-specific lines
in AST-style public prologues. By default, both variants are retained.

Render a fragment using the traditional Starlink SST LaTeX macros with:

```sh
starprolog latex source.f source.c -o routines.tex
```

Legacy prologues are parsed directly into the common document tree and can be
rendered without first rewriting the source into modern prologue syntax.
Use `--document` to include portable definitions of the SST macros and emit a
complete LaTeX document. `--mode auto` distinguishes ADAM A-tasks from library
routines using each prologue's `Type of Module` section; it can be overridden
with `--mode atask` or `--mode library`.

The explicitly AST-specific `astprep` command replaces the documentation
preprocessing performed by AST's historical `getatt` Perl script. For example:

```sh
starprolog astprep --kind class --language fortran \
    --labels getatt.labels ast/src/*.c -o f_classes.tex
```

It sorts and selects AST tagged prologues, applies the language-specific
section transformations, and can emit either drop-in LaTeX or its Pydantic
model with `--format json`. `--unix-script` selects the hash-comment command
prologues formerly requested with `getatt -u`. This is an AST extension, not a
general Starlink prologue convention. POD is not supported.

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
