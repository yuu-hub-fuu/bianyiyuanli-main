from __future__ import annotations

from dataclasses import dataclass, field
import copy

from nexa.frontend import ast
from .checker import GenericCallSite


@dataclass(slots=True)
class MonoCache:
    instances: dict[tuple[str, tuple[tuple[str, str], ...]], str] = field(default_factory=dict)


def monomorphize(module: ast.Module, callsites: list[GenericCallSite]) -> ast.Module:
    fn_map = {f.name: f for f in module.items if isinstance(f, ast.Function) and f.generic_params}
    if not fn_map:
        return module

    cache = MonoCache()
    new_items = list(module.items)

    def key_for(call: GenericCallSite) -> tuple[str, tuple[tuple[str, str], ...]]:
        return (call.callee, tuple(sorted((k, str(v)) for k, v in call.subst.items())))

    for call in callsites:
        if call.callee not in fn_map:
            continue
        key = key_for(call)
        if key in cache.instances:
            continue
        spec = call.callee + "__" + "__".join(v for _, v in key[1])
        cache.instances[key] = spec
        new_items.append(_clone_function(fn_map[call.callee], spec, dict(key[1])))

    def rewrite_expr(ex: ast.Expr) -> None:
        if isinstance(ex, ast.CallExpr) and isinstance(ex.callee, ast.NameExpr):
            name = ex.callee.name
            if name in fn_map:
                # choose instance by inferred argument types
                sub = tuple(sorted((gp, a.inferred_type or "i32") for gp, a in zip(fn_map[name].generic_params, ex.args, strict=False)))
                k = (name, sub)
                if k in cache.instances:
                    ex.callee.name = cache.instances[k]
            for a in ex.args:
                rewrite_expr(a)
        elif isinstance(ex, ast.UnaryExpr) and ex.rhs:
            rewrite_expr(ex.rhs)
        elif isinstance(ex, ast.BinaryExpr) and ex.lhs and ex.rhs:
            rewrite_expr(ex.lhs); rewrite_expr(ex.rhs)
        elif isinstance(ex, ast.SelectExpr):
            for c in ex.cases:
                if c.channel:
                    rewrite_expr(c.channel)
                if c.value:
                    rewrite_expr(c.value)

    def rewrite_stmt(st: ast.Stmt) -> None:
        if isinstance(st, ast.LetStmt) and st.value:
            rewrite_expr(st.value)
        elif isinstance(st, ast.AssignStmt):
            rewrite_expr(st.value)
        elif isinstance(st, ast.ExprStmt):
            rewrite_expr(st.expr)
        elif isinstance(st, ast.ReturnStmt) and st.value:
            rewrite_expr(st.value)
        elif isinstance(st, ast.IfStmt):
            rewrite_expr(st.cond); [rewrite_stmt(s) for s in st.then_block.stmts]
            if st.else_block:
                [rewrite_stmt(s) for s in st.else_block.stmts]
        elif isinstance(st, ast.WhileStmt):
            rewrite_expr(st.cond); [rewrite_stmt(s) for s in st.body.stmts]
        elif isinstance(st, ast.SpawnStmt):
            rewrite_expr(st.expr)
        elif isinstance(st, ast.Block):
            [rewrite_stmt(s) for s in st.stmts]

    for item in new_items:
        if isinstance(item, ast.Function):
            for st in item.body.stmts:
                rewrite_stmt(st)

    module.items = new_items
    return module


def _clone_function(fn: ast.Function, new_name: str, subst: dict[str, str]) -> ast.Function:
    cloned = ast.Function(
        fn.span,
        new_name,
        copy.deepcopy(fn.params),
        copy.deepcopy(fn.ret_type),
        copy.deepcopy(fn.body),
        [],
        {},
        False,
        fn.is_public,
        fn.owner_class,
        fn.visibility,
        fn.is_virtual,
        fn.is_override,
        fn.is_constructor,
        fn.is_destructor,
    )

    def apply_typeref(t: ast.TypeRef) -> ast.TypeRef:
        if t.name in subst:
            return ast.TypeRef(t.span, subst[t.name], [])
        return ast.TypeRef(t.span, t.name, [apply_typeref(p) for p in t.params])

    cloned.params = [ast.Param(p.span, p.name, apply_typeref(p.type_ref)) for p in cloned.params]
    cloned.ret_type = apply_typeref(cloned.ret_type)
    return cloned
