from __future__ import annotations

from nexa.frontend import ast
from .hir import HIRFunction, HIRInstr, HIRKind, HIRModule
from .mir import BasicBlock, MIRFunction, MIRInstr, MIRModule


class Lowerer:
    def __init__(self) -> None:
        self.temp_id = 0

    def lower_module(self, module: ast.Module) -> HIRModule:
        out = HIRModule()
        for item in module.items:
            if isinstance(item, ast.StructDef):
                out.struct_layouts[item.name] = [f.name for f in item.fields]
        for item in module.items:
            if isinstance(item, ast.Function) and not item.is_generic_template:
                out.functions.append(self._lower_fn(item))
        return out

    @staticmethod
    def _strip_generics(ty: str | None) -> str:
        if not ty:
            return ""
        return ty.split("[", 1)[0]

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
            elif isinstance(st.target, ast.FieldAccess) and st.target.base:
                base = self._lower_expr(st.target.base, hf)
                struct_ty = self._strip_generics(st.target.base.inferred_type)
                op = f"{struct_ty}.{st.target.field}" if struct_ty else st.target.field
                hf.instrs.append(HIRInstr(HIRKind.FIELD_SET, args=[base, src], op=op, ty=ty, span=(st.span.line, st.span.col)))
            elif isinstance(st.target, ast.IndexExpr) and st.target.base and st.target.index:
                base = self._lower_expr(st.target.base, hf)
                index = self._lower_expr(st.target.index, hf)
                hf.instrs.append(HIRInstr(HIRKind.ARRAY_SET, args=[base, index, src], ty=ty, span=(st.span.line, st.span.col)))
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
            for s in st.body.stmts:
                self._lower_stmt(s, hf)
            hf.instrs.append(HIRInstr(HIRKind.JUMP, target=l_head, ty="void"))
            hf.instrs.append(HIRInstr(HIRKind.LABEL, target=l_end, ty="void"))
        elif isinstance(st, ast.Block):
            for s in st.stmts:
                self._lower_stmt(s, hf)
        elif isinstance(st, ast.SpawnStmt):
            fn = self._lower_expr(st.expr, hf)
            hf.instrs.append(HIRInstr(HIRKind.SPAWN, args=[fn], ty="void"))

    def _lower_block_value(self, block: ast.Block, hf: HIRFunction, fallback: str) -> str:
        if not block.stmts:
            return fallback
        for st in block.stmts[:-1]:
            self._lower_stmt(st, hf)
        last = block.stmts[-1]
        if isinstance(last, ast.ExprStmt):
            return self._lower_expr(last.expr, hf)
        self._lower_stmt(last, hf)
        return fallback

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

    def _lower_expr(self, ex: ast.Expr, hf: HIRFunction) -> str:
        if isinstance(ex, ast.IntLit):
            t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.CONST, dst=t, args=[str(ex.value)], ty="i32", span=(ex.span.line, ex.span.col))); return t
        if isinstance(ex, ast.FloatLit):
            t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.CONST, dst=t, args=[repr(ex.value)], ty="f64", span=(ex.span.line, ex.span.col))); return t
        if isinstance(ex, ast.BoolLit):
            t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.CONST, dst=t, args=["1" if ex.value else "0"], ty="bool", span=(ex.span.line, ex.span.col))); return t
        if isinstance(ex, ast.StrLit):
            t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.CONST, dst=t, args=[ex.value], ty="str", span=(ex.span.line, ex.span.col))); return t
        if isinstance(ex, ast.NameExpr):
            return ex.name
        if isinstance(ex, ast.StructLit):
            args: list[str] = []
            for field in ex.fields:
                value = self._lower_expr(field.value, hf)
                args.extend([field.name, value])
            t = self._tmp()
            hf.instrs.append(HIRInstr(HIRKind.STRUCT_NEW, dst=t, args=args, op=ex.name, ty=ex.inferred_type or ex.name, span=(ex.span.line, ex.span.col)))
            return t
        if isinstance(ex, ast.FieldAccess) and ex.base:
            base = self._lower_expr(ex.base, hf)
            t = self._tmp()
            struct_ty = self._strip_generics(ex.base.inferred_type)
            op = f"{struct_ty}.{ex.field}" if struct_ty else ex.field
            hf.instrs.append(HIRInstr(HIRKind.FIELD_GET, dst=t, args=[base], op=op, ty=ex.inferred_type or "i32", span=(ex.span.line, ex.span.col)))
            return t
        if isinstance(ex, ast.ArrayLit):
            args = [self._lower_expr(item, hf) for item in ex.items]
            t = self._tmp()
            hf.instrs.append(HIRInstr(HIRKind.ARRAY_NEW, dst=t, args=args, ty=ex.inferred_type or "Array[i32]", span=(ex.span.line, ex.span.col)))
            return t
        if isinstance(ex, ast.IndexExpr) and ex.base and ex.index:
            base = self._lower_expr(ex.base, hf)
            index = self._lower_expr(ex.index, hf)
            t = self._tmp()
            hf.instrs.append(HIRInstr(HIRKind.ARRAY_GET, dst=t, args=[base, index], ty=ex.inferred_type or "i32", span=(ex.span.line, ex.span.col)))
            return t
        if isinstance(ex, ast.BlockExpr) and ex.block:
            t = self._tmp()
            zero = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.CONST, dst=zero, args=["0"], ty=ex.inferred_type or "i32", span=(ex.span.line, ex.span.col)))
            out = self._lower_block_value(ex.block, hf, zero)
            hf.instrs.append(HIRInstr(HIRKind.MOVE, dst=t, args=[out], ty=ex.inferred_type or "i32", span=(ex.span.line, ex.span.col)))
            return t
        if isinstance(ex, ast.SelectExpr):
            return self._lower_select_expr(ex, hf)
        if isinstance(ex, ast.UnaryExpr) and ex.rhs:
            r = self._lower_expr(ex.rhs, hf)
            t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.UNARY, dst=t, args=[r], op=ex.op, ty=ex.inferred_type or "i32", span=(ex.span.line, ex.span.col))); return t
        if isinstance(ex, ast.BinaryExpr) and ex.lhs and ex.rhs:
            l = self._lower_expr(ex.lhs, hf); r = self._lower_expr(ex.rhs, hf)
            t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.BIN, dst=t, args=[l, r], op=ex.op, ty=ex.inferred_type or "i32", span=(ex.span.line, ex.span.col))); return t
        if isinstance(ex, ast.CallExpr) and isinstance(ex.callee, ast.NameExpr):
            args = [self._lower_expr(a, hf) for a in ex.args]
            for a in args:
                hf.instrs.append(HIRInstr(HIRKind.ARG, args=[a], ty="void"))
            t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.CALL, dst=t, op=ex.callee.name, args=[], ty=ex.inferred_type or "i32", span=(ex.span.line, ex.span.col))); return t
        t = self._tmp(); hf.instrs.append(HIRInstr(HIRKind.CONST, dst=t, args=["0"], ty="i32", span=(ex.span.line, ex.span.col))); return t


def hir_to_mir(hir: HIRModule) -> MIRModule:
    out = MIRModule()
    out.struct_layouts = dict(hir.struct_layouts)
    out.string_pool = list(hir.string_pool)
    for fn in hir.functions:
        mf = MIRFunction(fn.name)
        current = BasicBlock("entry")
        mf.blocks[current.label] = current
        mf.order.append(current.label)

        def ensure_block(name: str) -> BasicBlock:
            if name not in mf.blocks:
                mf.blocks[name] = BasicBlock(name)
            return mf.blocks[name]

        def appear_in_order(name: str) -> None:
            if name not in mf.order:
                mf.order.append(name)

        for h in fn.instrs:
            if h.kind == HIRKind.LABEL and h.target:
                current = ensure_block(h.target)
                appear_in_order(h.target)
                continue

            args = list(h.args)
            mi = MIRInstr(kind=h.kind, op=h.op, args=args, dst=h.dst, target=h.target, ty=h.ty)
            current.instrs.append(mi)

            if h.kind in {HIRKind.BRANCH_TRUE, HIRKind.BRANCH_READY} and h.target:
                tblock = ensure_block(h.target)
                current.succs.add(h.target); tblock.preds.add(current.label)
                fall_name = f"fall_{len(mf.order)}"
                fall = ensure_block(fall_name)
                appear_in_order(fall_name)
                current.succs.add(fall.label); fall.preds.add(current.label)
                current = fall
            elif h.kind == HIRKind.JUMP and h.target:
                tblock = ensure_block(h.target)
                current.succs.add(h.target); tblock.preds.add(current.label)
                next_name = f"after_jmp_{len(mf.order)}"
                current = ensure_block(next_name)
                appear_in_order(next_name)
            elif h.kind == HIRKind.RET:
                next_name = f"after_ret_{len(mf.order)}"
                current = ensure_block(next_name)
                appear_in_order(next_name)

        # prune empty synthetic blocks without predecessors
        for name in list(mf.blocks.keys()):
            b = mf.blocks[name]
            if not b.instrs and not b.preds and name not in {"entry"}:
                del mf.blocks[name]
                if name in mf.order:
                    mf.order.remove(name)
        out.functions.append(mf)
    return out
