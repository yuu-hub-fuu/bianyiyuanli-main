from __future__ import annotations

from nexa.frontend import ast
from .hir import HIRFunction, HIRInstr, HIRKind, HIRModule
from .mir import BasicBlock, MIRFunction, MIRInstr, MIRModule


STD_MODULES = {"os", "fs", "io", "math", "str", "array", "collections", "time", "json", "net", "testing"}


class Lowerer:
    def __init__(self) -> None:
        self.temp_id = 0
        self.loop_stack: list[tuple[str, str]] = []
        self.lambda_id = 0
        self.extra_functions: list[HIRFunction] = []
        self.enum_variants: dict[str, str] = {}

    def lower_module(self, module: ast.Module) -> HIRModule:
        out = HIRModule()
        self.enum_variants = {
            variant.name: item.name
            for item in module.items
            if isinstance(item, ast.EnumDef)
            for variant in item.variants
        }
        for item in module.items:
            if isinstance(item, ast.Function) and not item.is_generic_template:
                out.functions.append(self._lower_fn(item))
        out.functions.extend(self.extra_functions)
        return out

    def _tmp(self) -> str:
        self.temp_id += 1
        return f"t{self.temp_id}"

    def _lower_fn(self, fn: ast.Function) -> HIRFunction:
        hf = HIRFunction(fn.name)
        for p in fn.params:
            hf.instrs.append(HIRInstr(HIRKind.PARAM, dst=p.name, ty=p.type_ref.name))
        for st in fn.body.stmts:
            self._lower_stmt(st, hf)
        if not hf.instrs or hf.instrs[-1].kind != HIRKind.RET:
            hf.instrs.append(HIRInstr(HIRKind.RET, args=["0"], ty="i32"))
        return hf

    def _lower_stmt(self, st: ast.Stmt, hf: HIRFunction) -> None:
        if isinstance(st, ast.LetStmt):
            if st.value:
                src = self._lower_expr(st.value, hf)
                ty = st.type_ref.name if st.type_ref else (st.value.inferred_type or "i32")
                hf.instrs.append(HIRInstr(HIRKind.MOVE, dst=st.name, args=[src], ty=ty))
        elif isinstance(st, ast.AssignStmt):
            src = self._lower_expr(st.value, hf)
            ty = st.value.inferred_type or "i32"
            if isinstance(st.target, ast.NameExpr):
                hf.instrs.append(HIRInstr(HIRKind.MOVE, dst=st.target.name, args=[src], ty=ty))
            elif isinstance(st.target, ast.IndexExpr) and st.target.target and st.target.index:
                arr = self._lower_expr(st.target.target, hf)
                idx = self._lower_expr(st.target.index, hf)
                hf.instrs.append(HIRInstr(HIRKind.ARRAY_SET, args=[arr, idx, src], ty=ty, span=(st.span.line, st.span.col)))
            elif isinstance(st.target, ast.FieldAccess) and st.target.target:
                target = self._lower_expr(st.target.target, hf)
                hf.instrs.append(HIRInstr(HIRKind.FIELD_SET, args=[target, st.target.field, src], ty=ty, span=(st.span.line, st.span.col)))
        elif isinstance(st, ast.ExprStmt):
            self._lower_expr(st.expr, hf)
        elif isinstance(st, ast.ReturnStmt):
            if st.value:
                src = self._lower_expr(st.value, hf)
                hf.instrs.append(HIRInstr(HIRKind.RET, args=[src], ty=st.value.inferred_type or "i32"))
            else:
                hf.instrs.append(HIRInstr(HIRKind.RET, ty="void"))
        elif isinstance(st, ast.IfStmt):
            c = self._lower_expr(st.cond, hf)
            l_then, l_else, l_end = self._tmp(), self._tmp(), self._tmp()
            hf.instrs.append(HIRInstr(HIRKind.BRANCH_TRUE, args=[c], target=l_then, ty="bool"))
            hf.instrs.append(HIRInstr(HIRKind.JUMP, target=l_else, ty="void"))
            hf.instrs.append(HIRInstr(HIRKind.LABEL, target=l_then, ty="void"))
            for s in st.then_block.stmts:
                self._lower_stmt(s, hf)
            hf.instrs.append(HIRInstr(HIRKind.JUMP, target=l_end, ty="void"))
            hf.instrs.append(HIRInstr(HIRKind.LABEL, target=l_else, ty="void"))
            if st.else_block:
                for s in st.else_block.stmts:
                    self._lower_stmt(s, hf)
            hf.instrs.append(HIRInstr(HIRKind.JUMP, target=l_end, ty="void"))
            hf.instrs.append(HIRInstr(HIRKind.LABEL, target=l_end, ty="void"))
        elif isinstance(st, ast.WhileStmt):
            l_head, l_body, l_end = self._tmp(), self._tmp(), self._tmp()
            hf.instrs.append(HIRInstr(HIRKind.LABEL, target=l_head, ty="void"))
            c = self._lower_expr(st.cond, hf)
            hf.instrs.append(HIRInstr(HIRKind.BRANCH_TRUE, args=[c], target=l_body, ty="bool"))
            hf.instrs.append(HIRInstr(HIRKind.JUMP, target=l_end, ty="void"))
            hf.instrs.append(HIRInstr(HIRKind.LABEL, target=l_body, ty="void"))
            self.loop_stack.append((l_head, l_end))
            for s in st.body.stmts:
                self._lower_stmt(s, hf)
            self.loop_stack.pop()
            hf.instrs.append(HIRInstr(HIRKind.JUMP, target=l_head, ty="void"))
            hf.instrs.append(HIRInstr(HIRKind.LABEL, target=l_end, ty="void"))
        elif isinstance(st, ast.ForStmt):
            if st.init:
                self._lower_stmt(st.init, hf)
            l_head, l_body, l_step, l_end = self._tmp(), self._tmp(), self._tmp(), self._tmp()
            hf.instrs.append(HIRInstr(HIRKind.LABEL, target=l_head, ty="void", span=(st.span.line, st.span.col)))
            if st.cond:
                c = self._lower_expr(st.cond, hf)
                hf.instrs.append(HIRInstr(HIRKind.BRANCH_TRUE, args=[c], target=l_body, ty="bool", span=(st.cond.span.line, st.cond.span.col)))
                hf.instrs.append(HIRInstr(HIRKind.JUMP, target=l_end, ty="void", span=(st.span.line, st.span.col)))
            else:
                hf.instrs.append(HIRInstr(HIRKind.JUMP, target=l_body, ty="void", span=(st.span.line, st.span.col)))
            hf.instrs.append(HIRInstr(HIRKind.LABEL, target=l_body, ty="void", span=(st.body.span.line, st.body.span.col)))
            self.loop_stack.append((l_step, l_end))
            for s in st.body.stmts:
                self._lower_stmt(s, hf)
            self.loop_stack.pop()
            hf.instrs.append(HIRInstr(HIRKind.JUMP, target=l_step, ty="void", span=(st.span.line, st.span.col)))
            hf.instrs.append(HIRInstr(HIRKind.LABEL, target=l_step, ty="void", span=(st.span.line, st.span.col)))
            if st.step:
                self._lower_stmt(st.step, hf)
            hf.instrs.append(HIRInstr(HIRKind.JUMP, target=l_head, ty="void", span=(st.span.line, st.span.col)))
            hf.instrs.append(HIRInstr(HIRKind.LABEL, target=l_end, ty="void", span=(st.span.line, st.span.col)))
        elif isinstance(st, ast.ForInStmt):
            self._lower_for_in(st, hf)
        elif isinstance(st, ast.BreakStmt):
            if self.loop_stack:
                hf.instrs.append(HIRInstr(HIRKind.JUMP, target=self.loop_stack[-1][1], ty="void", span=(st.span.line, st.span.col)))
        elif isinstance(st, ast.ContinueStmt):
            if self.loop_stack:
                hf.instrs.append(HIRInstr(HIRKind.JUMP, target=self.loop_stack[-1][0], ty="void", span=(st.span.line, st.span.col)))
        elif isinstance(st, ast.Block):
            for s in st.stmts:
                self._lower_stmt(s, hf)
        elif isinstance(st, ast.SpawnStmt):
            fn = self._lower_expr(st.expr, hf)
            hf.instrs.append(HIRInstr(HIRKind.SPAWN, args=[fn], ty="void"))

    def _lower_block_value(self, block: ast.Block, hf: HIRFunction, fallback: str) -> str:
        if not block.stmts:
            hf.instrs.append(HIRInstr(HIRKind.CONST, dst=fallback, args=["0"], ty="i32"))
            return fallback
        for st in block.stmts[:-1]:
            self._lower_stmt(st, hf)
        last = block.stmts[-1]
        if isinstance(last, ast.ExprStmt):
            return self._lower_expr(last.expr, hf)
        self._lower_stmt(last, hf)
        hf.instrs.append(HIRInstr(HIRKind.CONST, dst=fallback, args=["0"], ty="i32"))
        return fallback

    def _const_i32(self, hf: HIRFunction, value: int, span: tuple[int, int] = (0, 0)) -> str:
        t = self._tmp()
        hf.instrs.append(HIRInstr(HIRKind.CONST, dst=t, args=[str(value)], ty="i32", span=span))
        return t

    def _lower_for_in(self, st: ast.ForInStmt, hf: HIRFunction) -> None:
        span = (st.span.line, st.span.col)
        l_head, l_body, l_step, l_end = self._tmp(), self._tmp(), self._tmp(), self._tmp()
        if isinstance(st.iterable, ast.RangeExpr):
            start = self._lower_expr(st.iterable.start, hf) if st.iterable.start else self._const_i32(hf, 0, span)
            end = self._lower_expr(st.iterable.end, hf) if st.iterable.end else self._const_i32(hf, 0, span)
            hf.instrs.append(HIRInstr(HIRKind.MOVE, dst=st.name, args=[start], ty="i32", span=span))
            hf.instrs.append(HIRInstr(HIRKind.LABEL, target=l_head, ty="void", span=span))
            cond = self._tmp()
            hf.instrs.append(HIRInstr(HIRKind.BIN, dst=cond, args=[st.name, end], op="<=" if st.iterable.inclusive else "<", ty="bool", span=span))
            hf.instrs.append(HIRInstr(HIRKind.BRANCH_TRUE, args=[cond], target=l_body, ty="bool", span=span))
            hf.instrs.append(HIRInstr(HIRKind.JUMP, target=l_end, ty="void", span=span))
            hf.instrs.append(HIRInstr(HIRKind.LABEL, target=l_body, ty="void", span=span))
            self.loop_stack.append((l_step, l_end))
            for body_stmt in st.body.stmts:
                self._lower_stmt(body_stmt, hf)
            self.loop_stack.pop()
            hf.instrs.append(HIRInstr(HIRKind.JUMP, target=l_step, ty="void", span=span))
            hf.instrs.append(HIRInstr(HIRKind.LABEL, target=l_step, ty="void", span=span))
            one = self._const_i32(hf, 1, span)
            nxt = self._tmp()
            hf.instrs.append(HIRInstr(HIRKind.BIN, dst=nxt, args=[st.name, one], op="+", ty="i32", span=span))
            hf.instrs.append(HIRInstr(HIRKind.MOVE, dst=st.name, args=[nxt], ty="i32", span=span))
            hf.instrs.append(HIRInstr(HIRKind.JUMP, target=l_head, ty="void", span=span))
            hf.instrs.append(HIRInstr(HIRKind.LABEL, target=l_end, ty="void", span=span))
            return

        arr = self._lower_expr(st.iterable, hf)
        idx = self._const_i32(hf, 0, span)
        idx_name = self._tmp()
        hf.instrs.append(HIRInstr(HIRKind.MOVE, dst=idx_name, args=[idx], ty="i32", span=span))
        hf.instrs.append(HIRInstr(HIRKind.LABEL, target=l_head, ty="void", span=span))
        length = self._tmp()
        hf.instrs.append(HIRInstr(HIRKind.CALL, dst=length, op="array.len", args=[arr], ty="i32", span=span))
        cond = self._tmp()
        hf.instrs.append(HIRInstr(HIRKind.BIN, dst=cond, args=[idx_name, length], op="<", ty="bool", span=span))
        hf.instrs.append(HIRInstr(HIRKind.BRANCH_TRUE, args=[cond], target=l_body, ty="bool", span=span))
        hf.instrs.append(HIRInstr(HIRKind.JUMP, target=l_end, ty="void", span=span))
        hf.instrs.append(HIRInstr(HIRKind.LABEL, target=l_body, ty="void", span=span))
        hf.instrs.append(HIRInstr(HIRKind.ARRAY_GET, dst=st.name, args=[arr, idx_name], ty="i32", span=span))
        self.loop_stack.append((l_step, l_end))
        for body_stmt in st.body.stmts:
            self._lower_stmt(body_stmt, hf)
        self.loop_stack.pop()
        hf.instrs.append(HIRInstr(HIRKind.JUMP, target=l_step, ty="void", span=span))
        hf.instrs.append(HIRInstr(HIRKind.LABEL, target=l_step, ty="void", span=span))
        one = self._const_i32(hf, 1, span)
        nxt = self._tmp()
        hf.instrs.append(HIRInstr(HIRKind.BIN, dst=nxt, args=[idx_name, one], op="+", ty="i32", span=span))
        hf.instrs.append(HIRInstr(HIRKind.MOVE, dst=idx_name, args=[nxt], ty="i32", span=span))
        hf.instrs.append(HIRInstr(HIRKind.JUMP, target=l_head, ty="void", span=span))
        hf.instrs.append(HIRInstr(HIRKind.LABEL, target=l_end, ty="void", span=span))

    def _lower_select_expr(self, ex: ast.SelectExpr, hf: HIRFunction) -> str:
        """Runtime-backed select semantics.

        Lowering:
          br.ready ch, L_recv
          jmp L_default
        L_recv:
          v = recv(ch)
          res = <recv-body-value or v>
          jmp L_end
        L_default:
          res = <default-body-value or default-const>
        L_end:
        """
        res = self._tmp()
        recv_case = next((c for c in ex.cases if c.kind == "recv" and c.channel), None)
        default_case = next((c for c in ex.cases if c.kind == "default"), None)

        l_recv, l_default, l_end = self._tmp(), self._tmp(), self._tmp()
        if recv_case and recv_case.channel:
            ch = self._lower_expr(recv_case.channel, hf)
            hf.instrs.append(HIRInstr(HIRKind.BRANCH_READY, args=[ch], target=l_recv, ty="bool", span=(ex.span.line, ex.span.col)))
        hf.instrs.append(HIRInstr(HIRKind.JUMP, target=l_default, ty="void", span=(ex.span.line, ex.span.col)))

        hf.instrs.append(HIRInstr(HIRKind.LABEL, target=l_recv, ty="void", span=(ex.span.line, ex.span.col)))
        recv_val = self._tmp()
        if recv_case and recv_case.channel:
            ch = self._lower_expr(recv_case.channel, hf)
            hf.instrs.append(HIRInstr(HIRKind.CALL, dst=recv_val, args=[ch], op="recv", ty=ex.inferred_type or "i32", span=(ex.span.line, ex.span.col)))
        else:
            hf.instrs.append(HIRInstr(HIRKind.CONST, dst=recv_val, args=["0"], ty=ex.inferred_type or "i32", span=(ex.span.line, ex.span.col)))
        recv_out = self._lower_block_value(recv_case.body, hf, recv_val) if recv_case else recv_val
        hf.instrs.append(HIRInstr(HIRKind.MOVE, dst=res, args=[recv_out], ty=ex.inferred_type or "i32", span=(ex.span.line, ex.span.col)))
        hf.instrs.append(HIRInstr(HIRKind.JUMP, target=l_end, ty="void", span=(ex.span.line, ex.span.col)))

        hf.instrs.append(HIRInstr(HIRKind.LABEL, target=l_default, ty="void", span=(ex.span.line, ex.span.col)))
        default_val = self._tmp()
        hf.instrs.append(HIRInstr(HIRKind.CONST, dst=default_val, args=["0"], ty=ex.inferred_type or "i32", span=(ex.span.line, ex.span.col)))
        if default_case:
            d_out = self._lower_block_value(default_case.body, hf, default_val)
            hf.instrs.append(HIRInstr(HIRKind.MOVE, dst=res, args=[d_out], ty=ex.inferred_type or "i32", span=(ex.span.line, ex.span.col)))
        else:
            hf.instrs.append(HIRInstr(HIRKind.MOVE, dst=res, args=[default_val], ty=ex.inferred_type or "i32", span=(ex.span.line, ex.span.col)))

        hf.instrs.append(HIRInstr(HIRKind.LABEL, target=l_end, ty="void", span=(ex.span.line, ex.span.col)))

        for c in ex.cases:
            if c.kind == "send" and c.channel and c.value:
                ch = self._lower_expr(c.channel, hf)
                v = self._lower_expr(c.value, hf)
                hf.instrs.append(HIRInstr(HIRKind.CALL, args=[ch, v], op="send", ty="void", span=(ex.span.line, ex.span.col)))
        return res

    def _lower_match_expr(self, ex: ast.MatchExpr, hf: HIRFunction) -> str:
        value = self._lower_expr(ex.value, hf) if ex.value else self._const_i32(hf, 0, (ex.span.line, ex.span.col))
        tag = self._tmp()
        hf.instrs.append(HIRInstr(HIRKind.ENUM_TAG, dst=tag, args=[value], ty="str", span=(ex.span.line, ex.span.col)))
        result = self._tmp()
        end_label = self._tmp()
        next_label = self._tmp()
        for idx, arm in enumerate(ex.arms):
            body_label = self._tmp()
            after_cmp = self._tmp() if idx + 1 < len(ex.arms) else next_label
            tag_const = self._tmp()
            hf.instrs.append(HIRInstr(HIRKind.CONST, dst=tag_const, args=[arm.pattern.variant], ty="str", span=(arm.span.line, arm.span.col)))
            cond = self._tmp()
            hf.instrs.append(HIRInstr(HIRKind.BIN, dst=cond, args=[tag, tag_const], op="==", ty="bool", span=(arm.span.line, arm.span.col)))
            hf.instrs.append(HIRInstr(HIRKind.BRANCH_TRUE, args=[cond], target=body_label, ty="bool", span=(arm.span.line, arm.span.col)))
            hf.instrs.append(HIRInstr(HIRKind.JUMP, target=after_cmp, ty="void", span=(arm.span.line, arm.span.col)))
            hf.instrs.append(HIRInstr(HIRKind.LABEL, target=body_label, ty="void", span=(arm.span.line, arm.span.col)))
            if arm.pattern.binding:
                hf.instrs.append(HIRInstr(HIRKind.ENUM_GET, dst=arm.pattern.binding, args=[value, "0"], ty="i32", span=(arm.span.line, arm.span.col)))
            out = self._lower_block_value(arm.body, hf, result)
            hf.instrs.append(HIRInstr(HIRKind.MOVE, dst=result, args=[out], ty=ex.inferred_type or "i32", span=(arm.span.line, arm.span.col)))
            hf.instrs.append(HIRInstr(HIRKind.JUMP, target=end_label, ty="void", span=(arm.span.line, arm.span.col)))
            if idx + 1 < len(ex.arms):
                hf.instrs.append(HIRInstr(HIRKind.LABEL, target=after_cmp, ty="void", span=(arm.span.line, arm.span.col)))
        hf.instrs.append(HIRInstr(HIRKind.LABEL, target=next_label, ty="void", span=(ex.span.line, ex.span.col)))
        zero = self._const_i32(hf, 0, (ex.span.line, ex.span.col))
        hf.instrs.append(HIRInstr(HIRKind.MOVE, dst=result, args=[zero], ty=ex.inferred_type or "i32", span=(ex.span.line, ex.span.col)))
        hf.instrs.append(HIRInstr(HIRKind.LABEL, target=end_label, ty="void", span=(ex.span.line, ex.span.col)))
        return result

    def _lower_lambda_expr(self, ex: ast.LambdaExpr, hf: HIRFunction) -> str:
        self.lambda_id += 1
        name = f"__lambda_{self.lambda_id}"
        captures = list(ex.captures or self._free_names_lambda(ex))
        lf = HIRFunction(name)
        for cap in captures:
            lf.instrs.append(HIRInstr(HIRKind.PARAM, dst=cap, ty="i32", span=(ex.span.line, ex.span.col)))
        for param in ex.params:
            ty = param.type_ref.name if param.type_ref else "i32"
            lf.instrs.append(HIRInstr(HIRKind.PARAM, dst=param.name, ty=ty, span=(param.span.line, param.span.col)))
        if isinstance(ex.body, ast.Block):
            for st in ex.body.stmts:
                self._lower_stmt(st, lf)
        elif isinstance(ex.body, ast.Expr):
            out = self._lower_expr(ex.body, lf)
            lf.instrs.append(HIRInstr(HIRKind.RET, args=[out], ty=ex.body.inferred_type or "i32", span=(ex.body.span.line, ex.body.span.col)))
        if not lf.instrs or lf.instrs[-1].kind != HIRKind.RET:
            lf.instrs.append(HIRInstr(HIRKind.RET, args=["0"], ty="i32", span=(ex.span.line, ex.span.col)))
        self.extra_functions.append(lf)
        t = self._tmp()
        hf.instrs.append(HIRInstr(HIRKind.CLOSURE, dst=t, args=captures, op=name, ty=ex.inferred_type or "Fn", span=(ex.span.line, ex.span.col)))
        return t

    def _free_names_lambda(self, ex: ast.LambdaExpr) -> list[str]:
        bound = {p.name for p in ex.params}
        names: set[str] = set()

        def expr_names(node: ast.Expr | None) -> None:
            if node is None:
                return
            if isinstance(node, ast.NameExpr) and node.name not in bound and node.name not in self.enum_variants:
                names.add(node.name)
            elif isinstance(node, ast.BinaryExpr):
                expr_names(node.lhs); expr_names(node.rhs)
            elif isinstance(node, ast.UnaryExpr):
                expr_names(node.rhs)
            elif isinstance(node, ast.CallExpr):
                expr_names(node.callee)
                for arg in node.args:
                    expr_names(arg)
            elif isinstance(node, ast.ArrayLit):
                for item in node.elements:
                    expr_names(item)
            elif isinstance(node, ast.IndexExpr):
                expr_names(node.target); expr_names(node.index)
            elif isinstance(node, ast.SliceExpr):
                expr_names(node.target); expr_names(node.start); expr_names(node.end)
            elif isinstance(node, ast.FieldAccess):
                expr_names(node.target)
            elif isinstance(node, ast.InterpolatedString):
                for part in node.parts:
                    if isinstance(part, ast.Expr):
                        expr_names(part)
            elif isinstance(node, ast.LambdaExpr):
                return

        def stmt_names(stmt: ast.Stmt) -> None:
            if isinstance(stmt, ast.LetStmt):
                if stmt.value:
                    expr_names(stmt.value)
                bound.add(stmt.name)
            elif isinstance(stmt, ast.AssignStmt):
                expr_names(stmt.target); expr_names(stmt.value)
            elif isinstance(stmt, ast.ExprStmt):
                expr_names(stmt.expr)
            elif isinstance(stmt, ast.ReturnStmt):
                expr_names(stmt.value)
            elif isinstance(stmt, ast.Block):
                for s in stmt.stmts:
                    stmt_names(s)

        if isinstance(ex.body, ast.Block):
            for stmt in ex.body.stmts:
                stmt_names(stmt)
        elif isinstance(ex.body, ast.Expr):
            expr_names(ex.body)
        return sorted(names)

    def _lower_expr(self, ex: ast.Expr, hf: HIRFunction) -> str:
        if isinstance(ex, ast.IntLit):
            t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.CONST, dst=t, args=[str(ex.value)], ty="i32", span=(ex.span.line, ex.span.col))); return t
        if isinstance(ex, ast.FloatLit):
            t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.CONST, dst=t, args=[repr(ex.value)], ty="f64", span=(ex.span.line, ex.span.col))); return t
        if isinstance(ex, ast.BoolLit):
            t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.CONST, dst=t, args=["1" if ex.value else "0"], ty="bool", span=(ex.span.line, ex.span.col))); return t
        if isinstance(ex, ast.StrLit):
            t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.CONST, dst=t, args=[ex.value], ty="str", span=(ex.span.line, ex.span.col))); return t
        if isinstance(ex, ast.InterpolatedString):
            parts: list[str] = []
            for part in ex.parts:
                if isinstance(part, str):
                    t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.CONST, dst=t, args=[part], ty="str", span=(ex.span.line, ex.span.col))); parts.append(t)
                else:
                    src = self._lower_expr(part, hf)
                    t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.TO_STR, dst=t, args=[src], ty="str", span=(part.span.line, part.span.col))); parts.append(t)
            if not parts:
                t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.CONST, dst=t, args=[""], ty="str", span=(ex.span.line, ex.span.col))); return t
            out = parts[0]
            for part in parts[1:]:
                t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.BIN, dst=t, args=[out, part], op="+", ty="str", span=(ex.span.line, ex.span.col))); out = t
            return out
        if isinstance(ex, ast.NameExpr):
            if ex.name in self.enum_variants:
                t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.ENUM_NEW, dst=t, args=[ex.name], ty=ex.inferred_type or self.enum_variants[ex.name], span=(ex.span.line, ex.span.col))); return t
            return ex.name
        if isinstance(ex, ast.ArrayLit):
            elems = [self._lower_expr(e, hf) for e in ex.elements]
            t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.ARRAY_NEW, dst=t, args=elems, ty=ex.inferred_type or "Array", span=(ex.span.line, ex.span.col))); return t
        if isinstance(ex, ast.IndexExpr) and ex.target and ex.index:
            arr = self._lower_expr(ex.target, hf); idx = self._lower_expr(ex.index, hf)
            t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.ARRAY_GET, dst=t, args=[arr, idx], ty=ex.inferred_type or "i32", span=(ex.span.line, ex.span.col))); return t
        if isinstance(ex, ast.SliceExpr) and ex.target:
            arr = self._lower_expr(ex.target, hf)
            start = self._lower_expr(ex.start, hf) if ex.start else self._const_i32(hf, 0, (ex.span.line, ex.span.col))
            end = self._lower_expr(ex.end, hf) if ex.end else ""
            t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.ARRAY_SLICE, dst=t, args=[arr, start, end], ty=ex.inferred_type or "Array", span=(ex.span.line, ex.span.col))); return t
        if isinstance(ex, ast.RangeExpr):
            start = self._lower_expr(ex.start, hf) if ex.start else self._const_i32(hf, 0, (ex.span.line, ex.span.col))
            end = self._lower_expr(ex.end, hf) if ex.end else self._const_i32(hf, 0, (ex.span.line, ex.span.col))
            t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.RANGE_NEW, dst=t, args=[start, end, "1" if ex.inclusive else "0"], ty="Range", span=(ex.span.line, ex.span.col))); return t
        if isinstance(ex, ast.DictLit):
            args: list[str] = []
            for key, value in ex.entries:
                args.extend([self._lower_expr(key, hf), self._lower_expr(value, hf)])
            t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.DICT_NEW, dst=t, args=args, ty=ex.inferred_type or "Dict", span=(ex.span.line, ex.span.col))); return t
        if isinstance(ex, ast.StructLit):
            args: list[str] = [ex.name]
            for field, value in ex.fields.items():
                args.extend([field, self._lower_expr(value, hf)])
            t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.STRUCT_NEW, dst=t, args=args, ty=ex.name, span=(ex.span.line, ex.span.col))); return t
        if isinstance(ex, ast.FieldAccess) and ex.target:
            target = self._lower_expr(ex.target, hf)
            t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.FIELD_GET, dst=t, args=[target, ex.field], ty=ex.inferred_type or "i32", span=(ex.span.line, ex.span.col))); return t
        if isinstance(ex, ast.BlockExpr) and ex.block:
            t = self._tmp()
            zero = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.CONST, dst=zero, args=["0"], ty=ex.inferred_type or "i32", span=(ex.span.line, ex.span.col)))
            out = self._lower_block_value(ex.block, hf, zero)
            hf.instrs.append(HIRInstr(HIRKind.MOVE, dst=t, args=[out], ty=ex.inferred_type or "i32", span=(ex.span.line, ex.span.col)))
            return t
        if isinstance(ex, ast.SelectExpr):
            return self._lower_select_expr(ex, hf)
        if isinstance(ex, ast.MatchExpr):
            return self._lower_match_expr(ex, hf)
        if isinstance(ex, ast.LambdaExpr):
            return self._lower_lambda_expr(ex, hf)
        if isinstance(ex, ast.UnaryExpr) and ex.rhs:
            r = self._lower_expr(ex.rhs, hf)
            t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.UNARY, dst=t, args=[r], op=ex.op, ty=ex.inferred_type or "i32", span=(ex.span.line, ex.span.col))); return t
        if isinstance(ex, ast.BinaryExpr) and ex.lhs and ex.rhs:
            l = self._lower_expr(ex.lhs, hf); r = self._lower_expr(ex.rhs, hf)
            t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.BIN, dst=t, args=[l, r], op=ex.op, ty=ex.inferred_type or "i32", span=(ex.span.line, ex.span.col))); return t
        if isinstance(ex, ast.CallExpr) and (
            isinstance(ex.callee, ast.NameExpr)
            or (isinstance(ex.callee, ast.FieldAccess) and isinstance(ex.callee.target, ast.NameExpr))
        ):
            if isinstance(ex.callee, ast.NameExpr):
                callee = ex.callee.name
            else:
                module = ex.callee.target.name
                callee = f"{module}.{ex.callee.field}" if module in STD_MODULES else ex.callee.field
            if callee in self.enum_variants:
                args = [callee] + [self._lower_expr(a, hf) for a in ex.args]
                t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.ENUM_NEW, dst=t, args=args, ty=ex.inferred_type or self.enum_variants[callee], span=(ex.span.line, ex.span.col))); return t
            args = [self._lower_expr(a, hf) for a in ex.args]
            for a in args:
                hf.instrs.append(HIRInstr(HIRKind.ARG, args=[a], ty="void"))
            t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.CALL, dst=t, op=callee, args=[], ty=ex.inferred_type or "i32", span=(ex.span.line, ex.span.col))); return t
        if isinstance(ex, ast.CallExpr) and ex.callee:
            callee = self._lower_expr(ex.callee, hf)
            args = [self._lower_expr(a, hf) for a in ex.args]
            t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.CALL_VALUE, dst=t, args=[callee] + args, ty=ex.inferred_type or "i32", span=(ex.span.line, ex.span.col))); return t
        t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.CONST, dst=t, args=["0"], ty="i32", span=(ex.span.line, ex.span.col))); return t


def hir_to_mir(hir: HIRModule) -> MIRModule:
    out = MIRModule()
    for fn in hir.functions:
        mf = MIRFunction(fn.name)
        current = BasicBlock("entry")
        mf.blocks[current.label] = current
        mf.order.append(current.label)

        def ensure_block(name: str) -> BasicBlock:
            if name not in mf.blocks:
                mf.blocks[name] = BasicBlock(name)
                mf.order.append(name)
            return mf.blocks[name]

        for h in fn.instrs:
            if h.kind == HIRKind.LABEL and h.target:
                current = ensure_block(h.target)
                continue

            args = list(h.args)
            mi = MIRInstr(kind=h.kind, op=h.op, args=args, dst=h.dst, target=h.target, ty=h.ty)
            current.instrs.append(mi)

            if h.kind in {HIRKind.BRANCH_TRUE, HIRKind.BRANCH_READY} and h.target:
                tblock = ensure_block(h.target)
                current.succs.add(h.target); tblock.preds.add(current.label)
                fall = ensure_block(f"fall_{len(mf.order)}")
                current.succs.add(fall.label); fall.preds.add(current.label)
                current = fall
            elif h.kind == HIRKind.JUMP and h.target:
                tblock = ensure_block(h.target)
                current.succs.add(h.target); tblock.preds.add(current.label)
                current = ensure_block(f"after_jmp_{len(mf.order)}")
            elif h.kind == HIRKind.RET:
                current = ensure_block(f"after_ret_{len(mf.order)}")

        # prune empty synthetic blocks without predecessors
        for name in list(mf.blocks.keys()):
            b = mf.blocks[name]
            if not b.instrs and not b.preds and name not in {"entry"}:
                del mf.blocks[name]
                if name in mf.order:
                    mf.order.remove(name)
        out.functions.append(mf)
    return out
