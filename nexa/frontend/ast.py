from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .tokens import Span


@dataclass(slots=True)
class Node:
    span: Span


@dataclass(slots=True)
class TypeRef(Node):
    name: str
    params: list[TypeRef] = field(default_factory=list)


@dataclass(slots=True)
class Expr(Node):
    inferred_type: str | None = None


@dataclass(slots=True)
class IntLit(Expr):
    value: int = 0


@dataclass(slots=True)
class FloatLit(Expr):
    value: float = 0.0


@dataclass(slots=True)
class BoolLit(Expr):
    value: bool = False


@dataclass(slots=True)
class StrLit(Expr):
    value: str = ""


@dataclass(slots=True)
class NameExpr(Expr):
    name: str = ""


@dataclass(slots=True)
class FieldInit(Node):
    name: str
    value: Expr


@dataclass(slots=True)
class StructLit(Expr):
    name: str = ""
    fields: list[FieldInit] = field(default_factory=list)


@dataclass(slots=True)
class FieldAccess(Expr):
    base: Expr | None = None
    field: str = ""


@dataclass(slots=True)
class ArrayLit(Expr):
    items: list[Expr] = field(default_factory=list)


@dataclass(slots=True)
class IndexExpr(Expr):
    base: Expr | None = None
    index: Expr | None = None


@dataclass(slots=True)
class UnaryExpr(Expr):
    op: str = ""
    rhs: Expr | None = None


@dataclass(slots=True)
class BinaryExpr(Expr):
    op: str = ""
    lhs: Expr | None = None
    rhs: Expr | None = None


@dataclass(slots=True)
class CallExpr(Expr):
    callee: Expr | None = None
    args: list[Expr] = field(default_factory=list)


@dataclass(slots=True)
class SelectCase(Node):
    kind: str  # recv/send/default
    channel: Expr | None
    value: Expr | None
    body: Block


@dataclass(slots=True)
class SelectExpr(Expr):
    cases: list[SelectCase] = field(default_factory=list)


@dataclass(slots=True)
class BlockExpr(Expr):
    block: Block | None = None


@dataclass(slots=True)
class Stmt(Node):
    pass


@dataclass(slots=True)
class LetStmt(Stmt):
    name: str
    type_ref: TypeRef | None
    value: Expr | None


@dataclass(slots=True)
class AssignStmt(Stmt):
    target: Expr
    value: Expr


@dataclass(slots=True)
class ExprStmt(Stmt):
    expr: Expr


@dataclass(slots=True)
class ReturnStmt(Stmt):
    value: Expr | None


@dataclass(slots=True)
class IfStmt(Stmt):
    cond: Expr
    then_block: Block
    else_block: Block | None


@dataclass(slots=True)
class WhileStmt(Stmt):
    cond: Expr
    body: Block


@dataclass(slots=True)
class SpawnStmt(Stmt):
    expr: Expr


@dataclass(slots=True)
class Block(Stmt):
    stmts: list[Stmt]


@dataclass(slots=True)
class Param(Node):
    name: str
    type_ref: TypeRef


@dataclass(slots=True)
class Field(Node):
    name: str
    type_ref: TypeRef


@dataclass(slots=True)
class StructDef(Node):
    name: str
    fields: list[Field]


@dataclass(slots=True)
class Function(Node):
    name: str
    params: list[Param]
    ret_type: TypeRef
    body: Block
    generic_params: list[str] = field(default_factory=list)
    generic_bounds: dict[str, list[str]] = field(default_factory=dict)
    is_generic_template: bool = False


@dataclass(slots=True)
class Macro(Node):
    name: str
    params: list[str]
    body: Block


@dataclass(slots=True)
class Module(Node):
    items: list[Any]
