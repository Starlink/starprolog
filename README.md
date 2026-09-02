# starprolog

[![CI](https://github.com/Starlink/starprolog/actions/workflows/ci.yaml/badge.svg)](https://github.com/Starlink/starprolog/actions/workflows/ci.yaml)

`starprolog` parses Starlink-style source-code prologues into a
renderer-independent document tree. The command-line interface provides
LaTeX and Starlink help-library renderers. The intermediate representation
can also be written as JSON for inspection, storage, and later rendering.

The implementation is independent of the legacy Starlink SST implementation
and does not require a Starlink software installation.

## Development status

The public interface is under active development. Parse one or more source
files into the JSON intermediate representation with:

```sh
starprolog parse source.f source.c -o prologues.json
```

Input format detection recognizes both modern STARLSE prologues and the old
ADAM/SSE Fortran and BDK-style C conventions formerly handled by `procvt`,
and the SLALIB banner convention described below.
Each prologue records its detected syntax in the intermediate representation.
Detection can be overridden with `--input-format starlse`,
`--input-format adamsse` or `--input-format slalib`.

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

Render source for the Starlink help-library compiler with:

```sh
starprolog hlp --mode library source.f source.c -o routines.hlp
```

The HLP renderer implements the topic structure and required-section checks
of SST `prohlp`. In auto mode it uses the same A-task detection as the LaTeX
renderer.

Both renderers can consume the serialized Pydantic intermediate
representation instead of reparsing source:

```sh
starprolog parse source.f -o prologues.json
starprolog latex --input-format json prologues.json -o routines.tex
starprolog hlp --input-format json prologues.json -o routines.hlp
```

Multiple JSON collections can be supplied and are rendered in input order.

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

## SLALIB-style prologues (experimental)

SLALIB and the applications derived from it use a third convention, which no
SST tool ever read.

Support for it is experimental. There is no original implementation to check
it against, unlike the other two formats, so it has been validated only
against the Starlink tree itself and against expectations written by hand.
Both the rules that recognize a heading and the shape of the resulting
document tree may still change, and neither is covered by any compatibility
guarantee.
A bare `*+` is followed by a rule of spaced hyphens, the routine name spelled
out letter by letter, and a second rule:

```fortran
      SUBROUTINE sla_DTP2S (XI, ETA, RAZ, DECZ, RA, DEC)
*+
*     - - - - - -
*      D T P 2 S
*     - - - - - -
*
*  Transform tangent plane coordinates into spherical
*
*  Given:
*     XI,ETA      dp   tangent plane rectangular coordinates
*-
```

That banner is what identifies the format.
It is present in all 193 SLALIB source files and in 313 prologues across the
whole Starlink tree, and none of them carries a `Name:` heading, so detection
never has to choose between this convention and the other two.

There are no `Name:` or `Purpose:` headings, so both are recovered from the
banner's surroundings: the name from the program-unit declaration above it,
and the purpose from the free text between the banner and the first heading.
An `Invocation:` section is derived from that same declaration, as a `CALL`
for a subroutine and an assignment for a function, following the forms
`SST_TRCVT` supplies when an invocation is missing.
A main program gets neither, since it is not invoked.
`Result:` becomes `Returned Value`; every other heading keeps its own name.

`Given:`, `Returned:` and `Given and returned:` merge into a single
`Arguments:` section. Their entries are columnar, `NAME  type  description`,
with the access mode carried by the heading rather than by the entry, so each
becomes a `NAME = type (Given)` subsection with the description as its body,
and the mode moves onto the entry. A line indented past its entry continues
that entry's description; a line returning to the heading column ends the
list. Of the 1037 argument entries in the Starlink tree, 23 do not follow the
columnar convention closely enough to be split, and are left as they were
written.

### Known gaps

**Help output is not available.** These prologues have no `Description:`
section, and `prohlp` treats one as mandatory, so `starprolog hlp` rejects
all 313 of them. Only the LaTeX renderer is useful for this format at
present, and it accepts 311.

**Some argument entries cannot be split.** The name and type are usually set
off from the description by a run of spaces, but 23 entries separate every
field with a single space, use a notation of their own such as `(input)`, or
give no type at all. These are kept verbatim rather than guessed at, and reach
the output as entries with no description.

**An entry naming several variables stays one row.** `XI,ETA  dp  tangent
plane rectangular coordinates` describes two arguments, and the intermediate
representation should hold one subsection for each. It currently holds one,
titled `XI,ETA = dp (Given)`. Splitting the name on its commas is
straightforward; the description covers both variables and cannot be divided,
so it has to be repeated on each. This affects 117 of the 1014 argument
entries, 113 of them naming two variables and four naming three. It is a
to-do, not a decision to keep the present shape.

**A qualifier on an argument heading loses its group.** `Given:  (all
B1950.0,FK4)` qualifies the list that follows it, but once the lists merge
there is no group left for it to qualify, so it is kept as an entry of its own
in the position where it appeared.

**Unlabelled prose is dropped.** The author, date and copyright lines, and
statements such as `The result is an estimate of the air mass`, are free text
at the same indentation as the headings. Each line is therefore recorded as a
topic of its own, and having no body the renderers drop it, exactly as
`prolat` drops any section with no content. Telling this prose from a heading
means matching its shape, which is why it has not been done.

**A purpose can be mistaken for a heading.** A purpose line that ends in a
colon and introduces an indented list is structurally indistinguishable from
a section heading, and is read as one. Two of the 313 prologues lose their
purpose this way.

**The banner name is never used.** The routine name always comes from the
declaration above the prologue, and nothing checks it against the name spelled
out in the banner. A prologue with no declaration above it has no name, and so
cannot be rendered at all.

## Compatibility with prolat and prohlp

The renderers reproduce `prolat` and `prohlp` output for the great majority of
the Starlink source tree.
Comparing every prologue in `applications`, `libraries` and `libext` that the
original tools accept, 98.5% of 13381 LaTeX renderings and 97.7% of 13376 help
topics are byte-identical.

Every remaining difference comes from one of the deliberate divergences below.
Each is a case where the original loses or mangles content, so `starprolog`
does not reproduce it.

### Quoted text does not gain a space

`SST_LAT` writes `\texttt{'}` and `\texttt{"}` into an eleven-character field
even though the replacement is ten characters long, so Fortran pads it with a
trailing blank.
The typeset result is `FrameSet' s` where the source reads `FrameSet's`.
Every neighbouring escape in the same routine uses its exact length, so this is
an off-by-one rather than a typographic choice, and `starprolog` emits
`\texttt{'}` with no trailing space.

### Sections after an empty one are not dropped

The loop in `SST_TRLAT` and `SST_TRHLP` that emits the remaining sections stops
at the first unrecognized section with no body, so every later section is
silently discarded.
A stray prologue line at the indentation of the section headings is enough to
trigger it, and real prologues lose their parameter and reference sections this
way.
`starprolog` emits all the sections it finds.

### Tabs count as the width they display

`SST_FSECT` compares raw character positions, so a tab counts as one column.
A tab-indented continuation line therefore looks shallower than its section
heading and is promoted to a heading of its own, which ends the section and
hides everything that follows.
`starprolog` expands tabs to the next multiple of eight before comparing
indentation.

### Comment characters need not be in column one

`SST_RDPRO` only accepts a comment character in the first column, so a prologue
line indented inside a C block comment is discarded.
`starprolog` accepts the indented form, which is also what makes prologues
inside indented C comments and Python docstrings readable.

### Spelling variants of section headings are accepted

`Return Value` is treated as `Returned Value`, and `License` as `Licence`.
The original tools match section headings exactly, so they render
`Return Value` as an ordinary topic rather than a returned value, and repeat
the licence boilerplate that `Licence` suppresses.
The intent of either spelling is unambiguous, so `starprolog` honours both.
Headings that merely resemble a known one are left alone: `Author` stays an
ordinary topic, because folding it into `Authors` would drop it from the
output rather than place it better.

### A prologue is never emitted twice

`getatt` accumulates each prologue in a hash keyed by routine name, but appends
rather than assigns, so a name that appears twice in the input is written out
twice.
`astprep` keeps one prologue per name.
This is the only difference between `astprep` and `getatt` output for the AST
sources, once the quoting bug above is allowed for.

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
