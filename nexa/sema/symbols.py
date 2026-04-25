from __future__ import annotations

from dataclasses import dataclass

from .types import Type


@dataclass(slots=True)
class Symbol:
    name: str
    category: str
    ty: Type
    scope_id: int
    slot: int | None = None


class ScopeStack:
    def __init__(self) -> None:
        self.scopes: list[dict[str, Symbol]] = [{}]
        self.history: list[Symbol] = []

    def push(self) -> None:
        self.scopes.append({})

    def pop(self) -> None:
        self.scopes.pop()

    def declare(self, sym: Symbol) -> bool:
        cur = self.scopes[-1]
        if sym.name in cur:
            return False
        cur[sym.name] = sym
        self.history.append(sym)
        return True

    def lookup(self, name: str) -> Symbol | None:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    @property
    def scope_id(self) -> int:
        return len(self.scopes) - 1

    def dump_rows(self) -> list[tuple[str, str, str, int, int | None]]:
        return [(s.name, s.category, str(s.ty), s.scope_id, s.slot) for s in self.history]
