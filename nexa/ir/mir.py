from __future__ import annotations

from dataclasses import dataclass, field

from nexa.ir.hir import HIRKind


@dataclass(slots=True)
class MIRInstr:
    kind: HIRKind
    op: str | None
    args: list[str]
    dst: str | None = None
    target: str | None = None
    ty: str = "void"


@dataclass(slots=True)
class BasicBlock:
    label: str
    instrs: list[MIRInstr] = field(default_factory=list)
    preds: set[str] = field(default_factory=set)
    succs: set[str] = field(default_factory=set)


@dataclass(slots=True)
class MIRFunction:
    name: str
    blocks: dict[str, BasicBlock] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MIRModule:
    functions: list[MIRFunction] = field(default_factory=list)
