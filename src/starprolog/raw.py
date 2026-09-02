from __future__ import annotations

__all__ = ("LocatedLine", "RawPrologue")

from pydantic import Field

from .models import FrozenModel, PrologueMarker, PrologueSyntax, SourceSpan


class LocatedLine(FrozenModel):
    """Normalized source line and its original line number."""

    number: int = Field(ge=1)
    text: str


class RawPrologue(FrozenModel):
    """Extracted prologue before structural section parsing."""

    marker: PrologueMarker
    syntax: PrologueSyntax = PrologueSyntax.STARLSE
    source: SourceSpan
    lines: tuple[LocatedLine, ...]
