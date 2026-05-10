from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class HIRKind(Enum):
    PARAM = auto()
    CONST = auto()
    MOVE = auto()
    UNARY = auto()
    BIN = auto()
    ARG = auto()
    CALL = auto()
    RET = auto()
    LABEL = auto()
    JUMP = auto()
    BRANCH_TRUE = auto()
    BRANCH_READY = auto()
    SPAWN = auto()
    SELECT = auto()
    STRUCT_NEW = auto()
    FIELD_GET = auto()
    FIELD_SET = auto()


@dataclass(slots=True)
class HIRInstr:
    kind: HIRKind
    dst: str | None = None
    args: list[str] = field(default_factory=list)
    ty: str = "void"
    op: str | None = None
    target: str | None = None
    span: tuple[int, int] = (0, 0)

    def quad(self) -> tuple[str, str | None, str | None, str | None]:
        a1 = self.args[0] if len(self.args) > 0 else None
        a2 = self.args[1] if len(self.args) > 1 else None
        head = self.kind.name.lower()
        if self.op:
            head = f"{head}:{self.op}"
        if self.target:
            head = f"{head}->{self.target}"
        return (head, a1, a2, self.dst)


@dataclass(slots=True)
class HIRFunction:
    name: str
    instrs: list[HIRInstr] = field(default_factory=list)


@dataclass(slots=True)
class HIRModule:
    functions: list[HIRFunction] = field(default_factory=list)
