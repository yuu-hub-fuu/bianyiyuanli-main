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
class InterpolatedString(Expr):
    parts: list[str | Expr] = field(default_factory=list)


@dataclass(slots=True)
class NameExpr(Expr):
    name: str = ""


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
class LambdaParam(Node):
    name: str
    type_ref: TypeRef | None = None


@dataclass(slots=True)
class LambdaExpr(Expr):
    params: list[LambdaParam] = field(default_factory=list)
    body: Expr | Block | None = None
    captures: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ArrayLit(Expr):
    elements: list[Expr] = field(default_factory=list)


@dataclass(slots=True)
class DictLit(Expr):
    entries: list[tuple[Expr, Expr]] = field(default_factory=list)


@dataclass(slots=True)
class RangeExpr(Expr):
    start: Expr | None = None
    end: Expr | None = None
    inclusive: bool = False


@dataclass(slots=True)
class IndexExpr(Expr):
    target: Expr | None = None
    index: Expr | None = None


@dataclass(slots=True)
class SliceExpr(Expr):
    target: Expr | None = None
    start: Expr | None = None
    end: Expr | None = None
    inclusive: bool = False


@dataclass(slots=True)
class FieldAccess(Expr):
    target: Expr | None = None
    field: str = ""


@dataclass(slots=True)
class StructLit(Expr):
    name: str = ""
    fields: dict[str, Expr] = field(default_factory=dict)


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
class Pattern(Node):
    variant: str
    binding: str | None = None


@dataclass(slots=True)
class MatchArm(Node):
    pattern: Pattern
    body: Block


@dataclass(slots=True)
class MatchExpr(Expr):
    value: Expr | None = None
    arms: list[MatchArm] = field(default_factory=list)


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
class ForStmt(Stmt):
    init: Stmt | None
    cond: Expr | None
    step: Stmt | None
    body: Block


@dataclass(slots=True)
class ForInStmt(Stmt):
    name: str
    iterable: Expr
    body: Block


@dataclass(slots=True)
class BreakStmt(Stmt):
    pass


@dataclass(slots=True)
class ContinueStmt(Stmt):
    pass


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
class EnumVariant(Node):
    name: str
    payload: TypeRef | None = None


@dataclass(slots=True)
class EnumDef(Node):
    name: str
    variants: list[EnumVariant]
    generic_params: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ImportDecl(Node):
    path: str
    alias: str | None = None


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
