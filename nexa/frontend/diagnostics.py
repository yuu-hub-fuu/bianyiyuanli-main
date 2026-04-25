from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .tokens import Span


class Level(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    NOTE = "note"


@dataclass(slots=True)
class Diagnostic:
    level: Level
    span: Span
    message: str
    notes: list[str] = field(default_factory=list)
    fixits: list[str] = field(default_factory=list)


class DiagnosticBag:
    def __init__(self) -> None:
        self.items: list[Diagnostic] = []

    def add(self, level: Level, span: Span, message: str, notes: list[str] | None = None, fixits: list[str] | None = None) -> None:
        self.items.append(Diagnostic(level, span, message, notes or [], fixits or []))

    def error(self, span: Span, message: str, *notes: str, fixits: list[str] | None = None) -> None:
        self.add(Level.ERROR, span, message, list(notes), fixits)

    def warn(self, span: Span, message: str, *notes: str, fixits: list[str] | None = None) -> None:
        self.add(Level.WARNING, span, message, list(notes), fixits)

    def has_errors(self) -> bool:
        return any(d.level == Level.ERROR for d in self.items)
