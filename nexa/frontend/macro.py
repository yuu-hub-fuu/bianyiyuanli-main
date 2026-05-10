from __future__ import annotations

from dataclasses import dataclass

from . import ast
from .diagnostics import DiagnosticBag


@dataclass(slots=True)
class MacroEnv:
    macros: dict[str, ast.Macro]


class MacroExpander:
    def __init__(self, diagnostics: DiagnosticBag, max_depth: int = 32) -> None:
        self.diag = diagnostics
        self.max_depth = max_depth
        self.gensym_counter = 0

    def collect(self, module: ast.Module) -> MacroEnv:
        return MacroEnv({m.name: m for m in module.items if isinstance(m, ast.Macro)})

    def expand_module(self, module: ast.Module) -> ast.Module:
        env = self.collect(module)
        items = [i for i in module.items if not isinstance(i, ast.Macro)]
        for item in items:
            if isinstance(item, ast.Function):
                item.body = self._expand_block(item.body, env, 0)
        module.items = items
        return module

    def _expand_block(self, block: ast.Block, env: MacroEnv, depth: int) -> ast.Block:
        out: list[ast.Stmt] = []
        for stmt in block.stmts:
            out.extend(self._expand_stmt(stmt, env, depth))
        block.stmts = out
        return block

    def _expand_stmt(self, stmt: ast.Stmt, env: MacroEnv, depth: int) -> list[ast.Stmt]:
        if depth > self.max_depth:
            self.diag.error(stmt.span, "宏展开超过最大深度", fixits=[f"减少宏递归层次(<={self.max_depth})"])
            return [stmt]

        if isinstance(stmt, ast.ExprStmt) and isinstance(stmt.expr, ast.CallExpr) and isinstance(stmt.expr.callee, ast.NameExpr):
            name = stmt.expr.callee.name
            if name in env.macros:
                return self._expand_macro_call(stmt.expr, env, depth + 1)

        if isinstance(stmt, ast.IfStmt):
            stmt.then_block = self._expand_block(stmt.then_block, env, depth)
            if stmt.else_block:
                stmt.else_block = self._expand_block(stmt.else_block, env, depth)
        elif isinstance(stmt, ast.WhileStmt):
            stmt.body = self._expand_block(stmt.body, env, depth)
        elif isinstance(stmt, ast.Block):
            stmt = self._expand_block(stmt, env, depth)
        return [stmt]

    def _expand_macro_call(self, call: ast.CallExpr, env: MacroEnv, depth: int) -> list[ast.Stmt]:
        assert isinstance(call.callee, ast.NameExpr)
        macro = env.macros[call.callee.name]
        if len(call.args) != len(macro.params):
            self.diag.error(call.span, f"宏 {macro.name} 参数数量不匹配")
            return [ast.ExprStmt(call.span, call)]

        bind = dict(zip(macro.params, call.args, strict=True))
        cloned = self._clone_block(macro.body, bind)
        self._gensym_stmt(cloned, macro.name, [{}])
        return self._expand_block(cloned, env, depth).stmts

    def _gensym_stmt(self, stmt: ast.Stmt, macro_name: str, scopes: list[dict[str, str]]) -> None:
        def resolve(name: str) -> str:
            for m in reversed(scopes):
                if name in m:
                    return m[name]
            return name

        def rename_expr(expr: ast.Expr) -> None:
            if isinstance(expr, ast.NameExpr):
                expr.name = resolve(expr.name)
            elif isinstance(expr, ast.UnaryExpr) and expr.rhs:
                rename_expr(expr.rhs)
            elif isinstance(expr, ast.BinaryExpr) and expr.lhs and expr.rhs:
                rename_expr(expr.lhs); rename_expr(expr.rhs)
            elif isinstance(expr, ast.CallExpr):
                if expr.callee:
                    rename_expr(expr.callee)
                for a in expr.args:
                    rename_expr(a)
            elif isinstance(expr, ast.StructLit):
                for f in expr.fields:
                    rename_expr(f.value)
            elif isinstance(expr, ast.FieldAccess):
                if expr.base:
                    rename_expr(expr.base)
            elif isinstance(expr, ast.SelectExpr):
                for c in expr.cases:
                    if c.channel:
                        rename_expr(c.channel)
                    if c.value:
                        rename_expr(c.value)
            elif isinstance(expr, ast.BlockExpr) and expr.block:
                self._gensym_stmt(expr.block, macro_name, scopes)

        if isinstance(stmt, ast.Block):
            scopes.append({})
            for s in stmt.stmts:
                self._gensym_stmt(s, macro_name, scopes)
            scopes.pop()
            return

        if isinstance(stmt, ast.LetStmt):
            if stmt.value:
                rename_expr(stmt.value)
            self.gensym_counter += 1
            new = f"__macro_{macro_name}_{self.gensym_counter}_{stmt.name}"
            scopes[-1][stmt.name] = new
            stmt.name = new
            return

        if isinstance(stmt, ast.AssignStmt):
            if isinstance(stmt.target, ast.NameExpr):
                stmt.target.name = resolve(stmt.target.name)
            else:
                rename_expr(stmt.target)
            rename_expr(stmt.value)
        elif isinstance(stmt, ast.ExprStmt):
            rename_expr(stmt.expr)
        elif isinstance(stmt, ast.ReturnStmt) and stmt.value:
            rename_expr(stmt.value)
        elif isinstance(stmt, ast.IfStmt):
            rename_expr(stmt.cond)
            self._gensym_stmt(stmt.then_block, macro_name, scopes)
            if stmt.else_block:
                self._gensym_stmt(stmt.else_block, macro_name, scopes)
        elif isinstance(stmt, ast.WhileStmt):
            rename_expr(stmt.cond)
            self._gensym_stmt(stmt.body, macro_name, scopes)

    def _clone_expr(self, expr: ast.Expr, bind: dict[str, ast.Expr]) -> ast.Expr:
        if isinstance(expr, ast.NameExpr) and expr.name in bind:
            return bind[expr.name]
        if isinstance(expr, ast.UnaryExpr) and expr.rhs:
            return ast.UnaryExpr(expr.span, expr.inferred_type, expr.op, self._clone_expr(expr.rhs, bind))
        if isinstance(expr, ast.BinaryExpr) and expr.lhs and expr.rhs:
            return ast.BinaryExpr(expr.span, expr.inferred_type, expr.op, self._clone_expr(expr.lhs, bind), self._clone_expr(expr.rhs, bind))
        if isinstance(expr, ast.CallExpr) and expr.callee:
            return ast.CallExpr(expr.span, expr.inferred_type, self._clone_expr(expr.callee, bind), [self._clone_expr(a, bind) for a in expr.args])
        if isinstance(expr, ast.StructLit):
            return ast.StructLit(expr.span, expr.inferred_type, expr.name, [ast.FieldInit(f.span, f.name, self._clone_expr(f.value, bind)) for f in expr.fields])
        if isinstance(expr, ast.FieldAccess):
            return ast.FieldAccess(expr.span, expr.inferred_type, self._clone_expr(expr.base, bind) if expr.base else None, expr.field)
        if isinstance(expr, ast.SelectExpr):
            cases = [ast.SelectCase(c.span, c.kind, self._clone_expr(c.channel, bind) if c.channel else None,
                                    self._clone_expr(c.value, bind) if c.value else None,
                                    self._clone_block(c.body, bind)) for c in expr.cases]
            return ast.SelectExpr(expr.span, expr.inferred_type, cases)
        if isinstance(expr, ast.BlockExpr) and expr.block:
            return ast.BlockExpr(expr.span, expr.inferred_type, self._clone_block(expr.block, bind))
        return expr

    def _clone_stmt(self, stmt: ast.Stmt, bind: dict[str, ast.Expr]) -> ast.Stmt:
        if isinstance(stmt, ast.LetStmt):
            return ast.LetStmt(stmt.span, stmt.name, stmt.type_ref, self._clone_expr(stmt.value, bind) if stmt.value else None)
        if isinstance(stmt, ast.AssignStmt):
            return ast.AssignStmt(stmt.span, self._clone_expr(stmt.target, bind), self._clone_expr(stmt.value, bind))
        if isinstance(stmt, ast.ExprStmt):
            ex = self._clone_expr(stmt.expr, bind)
            if isinstance(ex, ast.BlockExpr) and ex.block:
                return ex.block
            return ast.ExprStmt(stmt.span, ex)
        if isinstance(stmt, ast.ReturnStmt):
            return ast.ReturnStmt(stmt.span, self._clone_expr(stmt.value, bind) if stmt.value else None)
        if isinstance(stmt, ast.IfStmt):
            return ast.IfStmt(stmt.span, self._clone_expr(stmt.cond, bind), self._clone_block(stmt.then_block, bind), self._clone_block(stmt.else_block, bind) if stmt.else_block else None)
        if isinstance(stmt, ast.WhileStmt):
            return ast.WhileStmt(stmt.span, self._clone_expr(stmt.cond, bind), self._clone_block(stmt.body, bind))
        if isinstance(stmt, ast.SpawnStmt):
            return ast.SpawnStmt(stmt.span, self._clone_expr(stmt.expr, bind))
        if isinstance(stmt, ast.Block):
            return self._clone_block(stmt, bind)
        return stmt

    def _clone_block(self, block: ast.Block, bind: dict[str, ast.Expr]) -> ast.Block:
        return ast.Block(block.span, [self._clone_stmt(s, bind) for s in block.stmts])
