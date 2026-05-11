from __future__ import annotations

from dataclasses import dataclass, field

from nexa.frontend import ast
from nexa.frontend.diagnostics import DiagnosticBag
from .symbols import ScopeStack, Symbol
from .types import BOOL, BUILTINS, F64, I32, STR, Type, VOID, array, channel, is_type_var, type_var


@dataclass(slots=True)
class FuncSig:
    params: list[Type]
    ret: Type
    generic_params: list[str] = field(default_factory=list)
    generic_bounds: dict[str, list[str]] = field(default_factory=dict)


@dataclass(slots=True)
class GenericCallSite:
    callee: str
    subst: dict[str, Type]
    span: object


@dataclass(slots=True)
class SemanticResult:
    module: ast.Module
    symbols: ScopeStack
    functions: dict[str, FuncSig]
    generic_calls: list[GenericCallSite]
    structs: dict[str, dict[str, Type]]


class Checker:
    def __init__(self, diagnostics: DiagnosticBag | None = None, mode: str = "full") -> None:
        self.diag = diagnostics or DiagnosticBag()
        self.scopes = ScopeStack()
        self.mode = mode
        self.generic_calls: list[GenericCallSite] = []
        self.structs: dict[str, dict[str, Type]] = {}
        self.functions: dict[str, FuncSig] = {
            "print": FuncSig([I32], VOID),
            "panic": FuncSig([STR], VOID),
            "read_i32": FuncSig([], I32),
            "read_f64": FuncSig([], F64),
            "chan": FuncSig([I32], channel(I32)),
            "send": FuncSig([channel(I32), I32], VOID),
            "recv": FuncSig([channel(I32)], I32),
        }

    def analyze(self, module: ast.Module) -> SemanticResult:
        for item in module.items:
            if isinstance(item, ast.StructDef):
                st = Type(item.name)
                self.structs[item.name] = {f.name: self._resolve_type(f.type_ref) for f in item.fields}
                self.scopes.declare(Symbol(item.name, "struct", st, self.scopes.scope_id))
            if isinstance(item, ast.Function):
                ptys = [self._resolve_type(p.type_ref, item.generic_params) for p in item.params]
                rty = self._resolve_type(item.ret_type, item.generic_params)
                self.functions[item.name] = FuncSig(ptys, rty, item.generic_params, item.generic_bounds)
                self.scopes.declare(Symbol(item.name, "fn", Type("fn"), self.scopes.scope_id))
        for item in module.items:
            if isinstance(item, ast.Function):
                self._check_function(item)
        return SemanticResult(module, self.scopes, self.functions, self.generic_calls, self.structs)

    def _check_function(self, fn: ast.Function) -> None:
        self.scopes.push()
        for p in fn.params:
            ty = self._resolve_type(p.type_ref, fn.generic_params)
            ok = self.scopes.declare(Symbol(p.name, "param", ty, self.scopes.scope_id))
            if not ok:
                self.diag.error(p.span, f"重复参数名: {p.name}")
        expected = self._resolve_type(fn.ret_type, fn.generic_params)
        self._check_block(fn.body, expected, fn)
        self.scopes.pop()

    def _check_block(self, block: ast.Block, ret_ty: Type, owner_fn: ast.Function) -> None:
        self.scopes.push()
        for stmt in block.stmts:
            self._check_stmt(stmt, ret_ty, owner_fn)
        self.scopes.pop()

    def _check_stmt(self, stmt: ast.Stmt, ret_ty: Type, owner_fn: ast.Function) -> None:
        if isinstance(stmt, ast.LetStmt):
            val_ty = self._check_expr(stmt.value, owner_fn) if stmt.value else None
            ann = self._resolve_type(stmt.type_ref, owner_fn.generic_params) if stmt.type_ref else val_ty
            if ann is None:
                self.diag.error(stmt.span, f"变量 {stmt.name} 缺少类型信息", fixits=[f"是否想声明 let {stmt.name}: i32 = ...;"])
                ann = I32
            if val_ty is not None and ann != val_ty:
                self.diag.error(stmt.span, f"类型不匹配: {ann} <- {val_ty}", fixits=[f"将变量类型改为 {val_ty} 或调整右值表达式"])
            if not self.scopes.declare(Symbol(stmt.name, "var", ann, self.scopes.scope_id)):
                self.diag.error(stmt.span, f"重复声明: {stmt.name}")
        elif isinstance(stmt, ast.AssignStmt):
            lhs_ty = self._check_assign_target(stmt.target, owner_fn)
            rhs = self._check_expr(stmt.value, owner_fn)
            if rhs != lhs_ty:
                self.diag.error(stmt.span, f"赋值类型不匹配: {lhs_ty} <- {rhs}")
        elif isinstance(stmt, ast.ExprStmt):
            self._check_expr(stmt.expr, owner_fn)
        elif isinstance(stmt, ast.ReturnStmt):
            got = VOID if stmt.value is None else self._check_expr(stmt.value, owner_fn)
            if got != ret_ty:
                self.diag.error(stmt.span, f"返回类型不匹配: 期望 {ret_ty}, 实际 {got}")
        elif isinstance(stmt, ast.IfStmt):
            cty = self._check_expr(stmt.cond, owner_fn)
            if cty != BOOL:
                self.diag.error(stmt.cond.span, f"if 条件必须是 bool，实际 {cty}", fixits=["将条件改为比较表达式（如 a > b）"])
            self._check_block(stmt.then_block, ret_ty, owner_fn)
            if stmt.else_block:
                self._check_block(stmt.else_block, ret_ty, owner_fn)
        elif isinstance(stmt, ast.WhileStmt):
            cty = self._check_expr(stmt.cond, owner_fn)
            if cty != BOOL:
                self.diag.error(stmt.cond.span, "while 条件必须是 bool")
            self._check_block(stmt.body, ret_ty, owner_fn)
        elif isinstance(stmt, ast.Block):
            self._check_block(stmt, ret_ty, owner_fn)
        elif isinstance(stmt, ast.SpawnStmt):
            self._check_expr(stmt.expr, owner_fn)

    def _check_expr(self, expr: ast.Expr | None, owner_fn: ast.Function) -> Type:
        if expr is None:
            return VOID
        if isinstance(expr, ast.IntLit):
            expr.inferred_type = str(I32)
            return I32
        if isinstance(expr, ast.FloatLit):
            expr.inferred_type = str(F64)
            return F64
        if isinstance(expr, ast.BoolLit):
            expr.inferred_type = str(BOOL)
            return BOOL
        if isinstance(expr, ast.StrLit):
            expr.inferred_type = str(STR)
            return STR
        if isinstance(expr, ast.NameExpr):
            sym = self.scopes.lookup(expr.name)
            if sym is None:
                self.diag.error(expr.span, f"未声明标识符: {expr.name}", fixits=[f"是否想声明 let {expr.name}: i32 = ...;"])
                expr.inferred_type = str(I32)
                return I32
            expr.inferred_type = str(sym.ty)
            return sym.ty
        if isinstance(expr, ast.StructLit):
            return self._check_struct_lit(expr, owner_fn)
        if isinstance(expr, ast.FieldAccess) and expr.base:
            return self._check_field_access(expr, owner_fn)
        if isinstance(expr, ast.ArrayLit):
            return self._check_array_lit(expr, owner_fn)
        if isinstance(expr, ast.IndexExpr):
            return self._check_index(expr, owner_fn)
        if isinstance(expr, ast.BlockExpr) and expr.block:
            self.scopes.push()
            last_ty = VOID
            stmts = expr.block.stmts
            for st in stmts[:-1]:
                self._check_stmt(st, VOID, owner_fn)
            if stmts:
                tail = stmts[-1]
                if isinstance(tail, ast.ExprStmt):
                    last_ty = self._check_expr(tail.expr, owner_fn)
                else:
                    self._check_stmt(tail, VOID, owner_fn)
            self.scopes.pop()
            expr.inferred_type = str(last_ty)
            return last_ty
        if isinstance(expr, ast.SelectExpr):
            return self._check_select(expr, owner_fn)
        if isinstance(expr, ast.UnaryExpr):
            rhs = self._check_expr(expr.rhs, owner_fn)
            if expr.op == "!":
                if rhs != BOOL:
                    self.diag.error(expr.span, "! 运算需要 bool")
                expr.inferred_type = str(BOOL)
                return BOOL
            if expr.op == "-":
                if rhs not in {I32, F64}:
                    self.diag.error(expr.span, "负号运算需要 i32 或 f64")
                expr.inferred_type = str(rhs)
                return rhs
        if isinstance(expr, ast.BinaryExpr):
            return self._check_binary(expr, owner_fn)
        if isinstance(expr, ast.CallExpr):
            return self._check_call(expr, owner_fn)
        self.diag.error(expr.span, "不支持的表达式")
        return I32

    def _check_struct_lit(self, expr: ast.StructLit, owner_fn: ast.Function) -> Type:
        fields = self.structs.get(expr.name)
        if fields is None:
            self.diag.error(expr.span, f"未定义结构体: {expr.name}")
            expr.inferred_type = expr.name
            return Type(expr.name)
        seen: set[str] = set()
        for init in expr.fields:
            if init.name in seen:
                self.diag.error(init.span, f"重复初始化字段: {init.name}")
            seen.add(init.name)
            expected = fields.get(init.name)
            got = self._check_expr(init.value, owner_fn)
            if expected is None:
                self.diag.error(init.span, f"结构体 {expr.name} 没有字段 {init.name}")
            elif got != expected:
                self.diag.error(init.span, f"字段 {init.name} 类型不匹配: {expected} <- {got}")
        for name in fields:
            if name not in seen:
                self.diag.error(expr.span, f"结构体 {expr.name} 缺少字段 {name}")
        expr.inferred_type = expr.name
        return Type(expr.name)

    def _check_field_access(self, expr: ast.FieldAccess, owner_fn: ast.Function) -> Type:
        base_ty = self._check_expr(expr.base, owner_fn)
        fields = self.structs.get(base_ty.name)
        if fields is None:
            self.diag.error(expr.span, f"类型 {base_ty} 没有字段 {expr.field}")
            expr.inferred_type = str(I32)
            return I32
        field_ty = fields.get(expr.field)
        if field_ty is None:
            self.diag.error(expr.span, f"结构体 {base_ty.name} 没有字段 {expr.field}")
            expr.inferred_type = str(I32)
            return I32
        expr.inferred_type = str(field_ty)
        return field_ty

    def _check_array_lit(self, expr: ast.ArrayLit, owner_fn: ast.Function) -> Type:
        if not expr.items:
            self.diag.error(expr.span, "空数组字面量暂时无法推断元素类型")
            expr.inferred_type = str(array(I32))
            return array(I32)
        item_tys = [self._check_expr(item, owner_fn) for item in expr.items]
        first = item_tys[0]
        for ty in item_tys[1:]:
            if ty != first:
                self.diag.error(expr.span, f"数组元素类型必须一致: {first} vs {ty}")
        arr_ty = array(first)
        expr.inferred_type = str(arr_ty)
        return arr_ty

    def _check_index(self, expr: ast.IndexExpr, owner_fn: ast.Function) -> Type:
        base_ty = self._check_expr(expr.base, owner_fn)
        idx_ty = self._check_expr(expr.index, owner_fn)
        if idx_ty != I32:
            self.diag.error(expr.span, f"数组索引必须是 i32，实际 {idx_ty}")
        if base_ty.name != "Array" or not base_ty.params:
            self.diag.error(expr.span, f"类型 {base_ty} 不支持索引访问")
            expr.inferred_type = str(I32)
            return I32
        item_ty = base_ty.params[0]
        expr.inferred_type = str(item_ty)
        return item_ty

    def _check_select(self, expr: ast.SelectExpr, owner_fn: ast.Function) -> Type:
        recv_cases = [c for c in expr.cases if c.kind == "recv"]
        send_cases = [c for c in expr.cases if c.kind == "send"]
        default_cases = [c for c in expr.cases if c.kind == "default"]
        if len(default_cases) != 1:
            self.diag.error(expr.span, "select 必须且只能有一个 default 分支")
        if not ((len(recv_cases) == 1 and len(send_cases) == 0) or (len(send_cases) == 1 and len(recv_cases) == 0)):
            self.diag.error(expr.span, "select 仅支持 recv+default 或 send+default 的教学子集")

        seen: list[Type] = []
        for c in expr.cases:
            if c.kind == "recv" and c.channel:
                cty = self._check_expr(c.channel, owner_fn)
                if cty.name != "Chan":
                    self.diag.error(c.span, "recv 需要通道类型 Chan[T]")
                case_ty = cty.params[0] if cty.params else I32
            elif c.kind == "send" and c.channel and c.value:
                cty = self._check_expr(c.channel, owner_fn)
                vty = self._check_expr(c.value, owner_fn)
                if cty.name != "Chan":
                    self.diag.error(c.span, "send 需要通道类型 Chan[T]")
                elif cty.params and cty.params[0] != vty:
                    self.diag.error(c.span, f"send 类型不匹配: Chan[{cty.params[0]}] <- {vty}")
                case_ty = vty
            else:
                case_ty = I32
            self.scopes.push()
            stmts = c.body.stmts
            for st in stmts[:-1]:
                self._check_stmt(st, VOID, owner_fn)
            if stmts and isinstance(stmts[-1], ast.ExprStmt):
                case_ty = self._check_expr(stmts[-1].expr, owner_fn)
            elif stmts:
                self._check_stmt(stmts[-1], VOID, owner_fn)
            self.scopes.pop()
            seen.append(case_ty)
        expr.inferred_type = str(seen[0] if seen else I32)
        return seen[0] if seen else I32

    def _check_binary(self, expr: ast.BinaryExpr, owner_fn: ast.Function) -> Type:
        lt = self._check_expr(expr.lhs, owner_fn)
        rt = self._check_expr(expr.rhs, owner_fn)
        if expr.op in {"+", "-", "*", "/", "%"}:
            if lt == rt and lt in {I32, F64}:
                if expr.op == "%" and lt != I32:
                    self.diag.error(expr.span, "% 运算只支持 i32")
                    expr.inferred_type = str(I32)
                    return I32
                expr.inferred_type = str(lt)
                return lt
            self.diag.error(expr.span, "算术运算要求两侧同为 i32 或同为 f64")
            expr.inferred_type = str(I32)
            return I32
        if expr.op in {"==", "!=", "<", "<=", ">", ">="}:
            if lt != rt:
                self.diag.error(expr.span, "比较两侧类型必须一致")
            expr.inferred_type = str(BOOL)
            return BOOL
        if expr.op in {"&&", "||"}:
            if lt != BOOL or rt != BOOL:
                self.diag.error(expr.span, "逻辑运算要求 bool")
            expr.inferred_type = str(BOOL)
            return BOOL
        self.diag.error(expr.span, f"不支持的二元运算: {expr.op}")
        return I32

    def _check_call(self, expr: ast.CallExpr, owner_fn: ast.Function) -> Type:
        if not isinstance(expr.callee, ast.NameExpr):
            self.diag.error(expr.span, "只支持直接函数调用")
            expr.inferred_type = str(I32)
            return I32
        callee = expr.callee.name
        if callee == "len":
            if len(expr.args) != 1:
                self.diag.error(expr.span, "len 需要 1 个参数")
            arg_types = [self._check_expr(arg, owner_fn) for arg in expr.args]
            if len(arg_types) == 1 and arg_types[0].name != "Array":
                self.diag.error(expr.args[0].span, f"len 参数必须是 Array[T]，实际 {arg_types[0]}")
            expr.inferred_type = str(I32)
            return I32
        sig = self.functions.get(callee)
        if sig is None:
            self.diag.error(expr.span, f"未定义函数: {callee}")
            expr.inferred_type = str(I32)
            return I32
        if sig.generic_params:
            return self._check_generic_call(expr, sig, owner_fn)

        # `print` is intentionally polymorphic over the primitive scalar
        # types and strings. The native backend dispatches to the matching
        # runtime helper, and the VM just str()s the value.
        if callee == "print":
            if len(expr.args) != 1:
                self.diag.error(expr.span, "参数数量不匹配: 期望 1")
            for arg in expr.args:
                self._check_expr(arg, owner_fn)
            expr.inferred_type = str(sig.ret)
            return sig.ret

        if len(sig.params) != len(expr.args):
            self.diag.error(expr.span, f"参数数量不匹配: 期望 {len(sig.params)}")
        for i, arg in enumerate(expr.args):
            aty = self._check_expr(arg, owner_fn)
            if i < len(sig.params) and aty != sig.params[i]:
                self.diag.error(arg.span, f"参数类型不匹配: 期望 {sig.params[i]}, 实际 {aty}")
        expr.inferred_type = str(sig.ret)
        return sig.ret

    def _check_generic_call(self, expr: ast.CallExpr, sig: FuncSig, owner_fn: ast.Function) -> Type:
        assert isinstance(expr.callee, ast.NameExpr)
        subst: dict[str, Type] = {}
        if len(sig.params) != len(expr.args):
            self.diag.error(expr.span, f"参数数量不匹配: 期望 {len(sig.params)}")
        for i, arg in enumerate(expr.args):
            aty = self._check_expr(arg, owner_fn)
            if i < len(sig.params):
                self._unify(sig.params[i], aty, subst, arg.span)
        for g in sig.generic_params:
            if g not in subst:
                self.diag.error(expr.span, f"泛型参数 {g} 无法推断")
                subst[g] = I32
            for b in sig.generic_bounds.get(g, []):
                if b == "Ord" and subst[g] not in {I32, STR, BOOL}:
                    self.diag.error(expr.span, f"泛型约束失败: {g}: {b}")
        ret = self._apply_subst(sig.ret, subst)
        self.generic_calls.append(GenericCallSite(expr.callee.name, subst.copy(), expr.span))
        expr.inferred_type = str(ret)
        return ret

    def _check_assign_target(self, target: ast.Expr, owner_fn: ast.Function) -> Type:
        if isinstance(target, ast.NameExpr):
            sym = self.scopes.lookup(target.name)
            if sym is None:
                self.diag.error(target.span, f"未声明变量: {target.name}", fixits=[f"是否想声明 let {target.name}: i32 = ...;"])
                target.inferred_type = str(I32)
                return I32
            target.inferred_type = str(sym.ty)
            return sym.ty
        if isinstance(target, ast.FieldAccess):
            return self._check_expr(target, owner_fn)
        if isinstance(target, ast.IndexExpr):
            return self._check_expr(target, owner_fn)
        self.diag.error(target.span, "赋值左侧必须是变量或字段访问")
        return I32

    def _unify(self, expected: Type, got: Type, subst: dict[str, Type], span) -> None:
        if is_type_var(expected):
            key = expected.name[1:]
            if key in subst and subst[key] != got:
                self.diag.error(span, f"泛型实参冲突: {subst[key]} vs {got}")
            else:
                subst[key] = got
            return
        if expected.name != got.name or len(expected.params) != len(got.params):
            self.diag.error(span, f"参数类型不匹配: 期望 {expected}, 实际 {got}")
            return
        for a, b in zip(expected.params, got.params, strict=True):
            self._unify(a, b, subst, span)

    def _apply_subst(self, ty: Type, subst: dict[str, Type]) -> Type:
        if is_type_var(ty):
            return subst.get(ty.name[1:], I32)
        if not ty.params:
            return ty
        return Type(ty.name, tuple(self._apply_subst(p, subst) for p in ty.params))

    def _resolve_type(self, tref: ast.TypeRef | None, generics: list[str] | None = None) -> Type:
        if tref is None:
            return VOID
        generics = generics or []
        if tref.name in generics:
            return type_var(tref.name)
        if tref.name == "Chan" and tref.params:
            return channel(self._resolve_type(tref.params[0], generics))
        if tref.name == "Array" and tref.params:
            return array(self._resolve_type(tref.params[0], generics))
        if tref.params:
            return Type(tref.name, tuple(self._resolve_type(p, generics) for p in tref.params))
        return BUILTINS.get(tref.name, Type(tref.name))
