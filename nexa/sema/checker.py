from __future__ import annotations

from dataclasses import dataclass, field

from nexa.frontend import ast
from nexa.frontend.diagnostics import DiagnosticBag
from .symbols import ScopeStack, Symbol
from .types import BOOL, BUILTINS, F64, I32, STR, Type, VOID, array, channel, const_ptr, func, is_type_var, ptr, type_var


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
        self.class_bases: dict[str, str | None] = {}
        self.class_field_meta: dict[tuple[str, str], tuple[str, str]] = {}
        self.class_methods: dict[str, dict[str, str]] = {}
        self.virtual_methods: dict[str, dict[str, str]] = {}
        self.constructors: dict[str, str] = {}
        self.destructors: dict[str, str] = {}
        self.current_class: str | None = None
        T = type_var("T")
        self.functions: dict[str, FuncSig] = {
            "print": FuncSig([I32], VOID),
            "panic": FuncSig([STR], VOID),
            "read_i32": FuncSig([], I32),
            "read_f64": FuncSig([], F64),
            "read_str": FuncSig([], STR),
            "cat": FuncSig([STR, STR], STR),
            "strlen": FuncSig([STR], I32),
            "substr": FuncSig([STR, I32, I32], STR),
            "find": FuncSig([STR, STR], I32),
            "contains": FuncSig([STR, STR], BOOL),
            "starts_with": FuncSig([STR, STR], BOOL),
            "ends_with": FuncSig([STR, STR], BOOL),
            "replace": FuncSig([STR, STR, STR], STR),
            "trim": FuncSig([STR], STR),
            "lower": FuncSig([STR], STR),
            "upper": FuncSig([STR], STR),
            "ord": FuncSig([STR], I32),
            "chr": FuncSig([I32], STR),
            "parse_i32": FuncSig([STR], I32),
            "parse_f64": FuncSig([STR], F64),
            "rand": FuncSig([], I32),
            "srand": FuncSig([I32], VOID),
            "rand_range": FuncSig([I32, I32], I32),
            "time": FuncSig([], I32),
            "clock": FuncSig([], I32),
            "ptr_new": FuncSig([T], ptr(T), ["T"]),
            "ptr_get": FuncSig([ptr(T)], T, ["T"]),
            "ptr_set": FuncSig([ptr(T), T], VOID, ["T"]),
            "const_ptr_new": FuncSig([T], const_ptr(T), ["T"]),
            "call": FuncSig([], I32),
            "copy": FuncSig([T], T, ["T"]),
            "clone": FuncSig([T], T, ["T"]),
            "shallow_copy": FuncSig([T], T, ["T"]),
            "deep_copy": FuncSig([T], T, ["T"]),
            "chan": FuncSig([I32], channel(I32)),
            "send": FuncSig([channel(I32), I32], VOID),
            "recv": FuncSig([channel(I32)], I32),
        }

    def analyze(self, module: ast.Module) -> SemanticResult:
        for item in module.items:
            if isinstance(item, ast.ClassDef):
                self.class_bases[item.name] = item.base

        for item in module.items:
            if isinstance(item, ast.StructDef):
                st = Type(item.name)
                self.structs[item.name] = {f.name: self._resolve_type(f.type_ref) for f in item.fields}
                self.scopes.declare(Symbol(item.name, "struct", st, self.scopes.scope_id))
            if isinstance(item, ast.ClassDef):
                self._register_class(item)
            if isinstance(item, ast.Function):
                ptys = [self._resolve_type(p.type_ref, item.generic_params) for p in item.params]
                rty = self._resolve_type(item.ret_type, item.generic_params)
                self.functions[item.name] = FuncSig(ptys, rty, item.generic_params, item.generic_bounds)
                self.scopes.declare(Symbol(item.name, "fn", Type("fn"), self.scopes.scope_id))
        for item in module.items:
            if isinstance(item, ast.Function):
                self._check_function(item)
            if isinstance(item, ast.ClassDef):
                for method in item.methods:
                    self._check_function(method)
        return SemanticResult(module, self.scopes, self.functions, self.generic_calls, self.structs)

    def _register_class(self, item: ast.ClassDef) -> None:
        fields: dict[str, Type] = {}
        if item.base:
            fields.update(self.structs.get(item.base, {}))
            self.class_methods[item.name] = dict(self.class_methods.get(item.base, {}))
        else:
            self.class_methods[item.name] = {}
        for f in item.fields:
            fields[f.name] = self._resolve_type(f.type_ref)
            self.class_field_meta[(item.name, f.name)] = (f.visibility, f.owner or item.name)
        self.structs[item.name] = fields
        self.scopes.declare(Symbol(item.name, "class", Type(item.name), self.scopes.scope_id))
        for method in item.methods:
            public_name = method.name.split("__", 1)[-1]
            if method.is_constructor:
                public_name = "__init"
                self.constructors[item.name] = method.name
            elif method.is_destructor:
                public_name = "__drop"
                self.destructors[item.name] = method.name
            self.class_methods.setdefault(item.name, {})[public_name] = method.name
            if method.is_virtual or method.is_override or method.is_destructor:
                self.virtual_methods.setdefault(item.name, {})[public_name] = method.name
                if method.is_override and item.base and public_name not in self.virtual_methods.get(item.base, {}):
                    self.diag.error(method.span, f"override method {public_name} does not override a virtual base method")
            ptys = [self._resolve_type(p.type_ref, method.generic_params) for p in method.params]
            rty = self._resolve_type(method.ret_type, method.generic_params)
            self.functions[method.name] = FuncSig(ptys, rty, method.generic_params, method.generic_bounds)
            self.scopes.declare(Symbol(method.name, "method", Type("fn"), self.scopes.scope_id))

    def _check_function(self, fn: ast.Function) -> None:
        prev_class = self.current_class
        self.current_class = fn.owner_class
        self.scopes.push()
        for p in fn.params:
            ty = self._resolve_type(p.type_ref, fn.generic_params)
            ok = self.scopes.declare(Symbol(p.name, "param", ty, self.scopes.scope_id))
            if not ok:
                self.diag.error(p.span, f"重复参数名: {p.name}")
        expected = self._resolve_type(fn.ret_type, fn.generic_params)
        self._check_block(fn.body, expected, fn)
        self.scopes.pop()
        self.current_class = prev_class

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
        elif isinstance(stmt, ast.DeleteStmt):
            ty = self._check_expr(stmt.value, owner_fn)
            if ty.name not in {"Ptr", "ConstPtr"} or not ty.params:
                self.diag.error(stmt.span, f"delete expects Ptr[T], got {ty}")
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
                sig = self.functions.get(expr.name)
                if sig is not None:
                    out = func(sig.params, sig.ret)
                    expr.inferred_type = str(out)
                    return out
                self.diag.error(expr.span, f"未声明标识符: {expr.name}", fixits=[f"是否想声明 let {expr.name}: i32 = ...;"])
                expr.inferred_type = str(I32)
                return I32
            expr.inferred_type = str(sym.ty)
            return sym.ty
        if isinstance(expr, ast.StructLit):
            return self._check_struct_lit(expr, owner_fn)
        if isinstance(expr, ast.NewExpr):
            return self._check_new_expr(expr, owner_fn)
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
            if expr.op == "&":
                if not isinstance(expr.rhs, ast.NameExpr):
                    self.diag.error(expr.span, "& expects a local variable name")
                out = ptr(rhs)
                expr.inferred_type = str(out)
                return out
            if expr.op == "*":
                if rhs.name not in {"Ptr", "ConstPtr"} or not rhs.params:
                    self.diag.error(expr.span, "* expects Ptr[T] or ConstPtr[T]")
                    expr.inferred_type = str(I32)
                    return I32
                out = rhs.params[0]
                expr.inferred_type = str(out)
                return out
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

    def _check_new_expr(self, expr: ast.NewExpr, owner_fn: ast.Function) -> Type:
        class_ty = self._resolve_type(expr.type_ref, owner_fn.generic_params)
        ctor_name = self.constructors.get(class_ty.name)
        if class_ty.name not in self.structs:
            self.diag.error(expr.span, f"new expects a class or struct type, got {class_ty}")
        arg_types = [self._check_expr(arg, owner_fn) for arg in expr.args]
        if ctor_name:
            sig = self.functions[ctor_name]
            expected = sig.params[1:]
            if len(expected) != len(arg_types):
                self.diag.error(expr.span, f"constructor for {class_ty.name} expects {len(expected)} arguments")
            for idx, (got, exp) in enumerate(zip(arg_types, expected, strict=False)):
                if got != exp:
                    self.diag.error(expr.args[idx].span, f"constructor argument expects {exp}, got {got}")
        elif arg_types:
            self.diag.error(expr.span, f"{class_ty.name} has no constructor accepting arguments")
        out = ptr(class_ty)
        expr.inferred_type = str(out)
        return out

    def _check_field_access(self, expr: ast.FieldAccess, owner_fn: ast.Function) -> Type:
        base_ty = self._check_expr(expr.base, owner_fn)
        if base_ty.name in {"Ptr", "ConstPtr"} and base_ty.params:
            base_ty = base_ty.params[0]
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
        meta = self._field_meta(base_ty.name, expr.field)
        if meta is not None:
            visibility, owner = meta
            if visibility == "private" and self.current_class != owner:
                self.diag.error(expr.span, f"field {expr.field} is private in {owner}")
        expr.inferred_type = str(field_ty)
        return field_ty

    def _field_meta(self, class_name: str, field: str) -> tuple[str, str] | None:
        cur: str | None = class_name
        while cur:
            meta = self.class_field_meta.get((cur, field))
            if meta is not None:
                return meta
            cur = self.class_bases.get(cur)
        return None

    def _lookup_method(self, class_name: str, method: str) -> str | None:
        cur: str | None = class_name
        while cur:
            found = self.class_methods.get(cur, {}).get(method)
            if found:
                return found
            cur = self.class_bases.get(cur)
        return None

    def _virtual_method_names(self, class_name: str) -> set[str]:
        out: set[str] = set()
        cur: str | None = class_name
        while cur:
            out.update(self.virtual_methods.get(cur, {}).keys())
            cur = self.class_bases.get(cur)
        return out

    def _is_subclass(self, child: str, parent: str) -> bool:
        cur = self.class_bases.get(child)
        while cur:
            if cur == parent:
                return True
            cur = self.class_bases.get(cur)
        return False

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
        if expr.op == "+" and lt == STR and rt == STR:
            expr.inferred_type = str(STR)
            return STR
        if expr.op == "-" and lt == STR and rt == STR:
            expr.inferred_type = str(STR)
            return STR
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
        if isinstance(expr.callee, ast.FieldAccess) and expr.callee.base:
            field = expr.callee.field
            if isinstance(expr.callee.base, ast.NameExpr) and expr.callee.base.name in self.structs:
                target = f"{expr.callee.base.name}__{field}"
                if target not in self.functions:
                    self.diag.error(expr.span, f"类型 {expr.callee.base.name} 没有方法 {field}")
                    expr.inferred_type = str(I32)
                    return I32
                expr.callee = ast.NameExpr(expr.callee.span, None, target)
                return self._check_call(expr, owner_fn)

            base_ty = self._check_expr(expr.callee.base, owner_fn)
            static_ty = base_ty.params[0] if base_ty.name in {"Ptr", "ConstPtr"} and base_ty.params else base_ty
            target = self._lookup_method(static_ty.name, field)
            if target is None:
                target = f"{static_ty.name}__{field}"
                if target not in self.functions:
                    self.diag.error(expr.span, f"类型 {static_ty} 没有方法 {field}")
                    expr.inferred_type = str(I32)
                    return I32
            sig = self.functions[target]
            expr.resolved_callee = target
            if field in self._virtual_method_names(static_ty.name):
                expr.virtual_method = field
                expr.static_type = static_ty.name
            if len(sig.params) != len(expr.args) + 1:
                self.diag.error(expr.span, f"method {field} expects {max(0, len(sig.params) - 1)} arguments")
            if sig.params and sig.params[0] != static_ty and not self._is_subclass(static_ty.name, sig.params[0].name):
                self.diag.error(expr.callee.base.span, f"method self expects {sig.params[0]}, got {static_ty}")
            for i, arg in enumerate(expr.args, start=1):
                aty = self._check_expr(arg, owner_fn)
                if i < len(sig.params) and aty != sig.params[i]:
                    self.diag.error(arg.span, f"method argument expects {sig.params[i]}, got {aty}")
            expr.inferred_type = str(sig.ret)
            return sig.ret
        if not isinstance(expr.callee, ast.NameExpr):
            self.diag.error(expr.span, "只支持直接函数调用")
            expr.inferred_type = str(I32)
            return I32
        callee = expr.callee.name
        if callee == "len":
            if len(expr.args) != 1:
                self.diag.error(expr.span, "len 需要 1 个参数")
            arg_types = [self._check_expr(arg, owner_fn) for arg in expr.args]
            if len(arg_types) == 1 and arg_types[0] == STR:
                expr.inferred_type = str(I32)
                return I32
            if len(arg_types) == 1 and arg_types[0].name != "Array":
                self.diag.error(expr.args[0].span, f"len 参数必须是 Array[T]，实际 {arg_types[0]}")
            expr.inferred_type = str(I32)
            return I32
        if callee in {"str", "to_str"}:
            if len(expr.args) != 1:
                self.diag.error(expr.span, f"{callee} expects 1 argument")
            for arg in expr.args:
                self._check_expr(arg, owner_fn)
            expr.inferred_type = str(STR)
            return STR
        if callee in {"int", "to_i32"}:
            if len(expr.args) != 1:
                self.diag.error(expr.span, f"{callee} expects 1 argument")
            for arg in expr.args:
                self._check_expr(arg, owner_fn)
            expr.inferred_type = str(I32)
            return I32
        if callee in {"float", "to_f64"}:
            if len(expr.args) != 1:
                self.diag.error(expr.span, f"{callee} expects 1 argument")
            for arg in expr.args:
                self._check_expr(arg, owner_fn)
            expr.inferred_type = str(F64)
            return F64
        if callee in {"bool", "to_bool"}:
            if len(expr.args) != 1:
                self.diag.error(expr.span, f"{callee} expects 1 argument")
            for arg in expr.args:
                self._check_expr(arg, owner_fn)
            expr.inferred_type = str(BOOL)
            return BOOL
        if callee == "abs":
            if len(expr.args) != 1:
                self.diag.error(expr.span, "abs expects 1 argument")
            arg_types = [self._check_expr(arg, owner_fn) for arg in expr.args]
            ret = arg_types[0] if arg_types and arg_types[0] in {I32, F64} else I32
            if arg_types and arg_types[0] not in {I32, F64}:
                self.diag.error(expr.args[0].span, f"abs expects i32 or f64, got {arg_types[0]}")
            expr.inferred_type = str(ret)
            return ret
        if callee in {"min", "max"}:
            if len(expr.args) != 2:
                self.diag.error(expr.span, f"{callee} expects 2 arguments")
            arg_types = [self._check_expr(arg, owner_fn) for arg in expr.args]
            ret = arg_types[0] if arg_types else I32
            if len(arg_types) == 2 and (arg_types[0] != arg_types[1] or arg_types[0] not in {I32, F64, STR}):
                self.diag.error(expr.span, f"{callee} expects two values of the same i32, f64, or str type")
                ret = I32
            expr.inferred_type = str(ret)
            return ret
        if callee == "ptr_get":
            if len(expr.args) != 1:
                self.diag.error(expr.span, "ptr_get expects 1 argument")
            arg_types = [self._check_expr(arg, owner_fn) for arg in expr.args]
            if arg_types and arg_types[0].name in {"Ptr", "ConstPtr"} and arg_types[0].params:
                ret = arg_types[0].params[0]
            else:
                self.diag.error(expr.span, f"ptr_get expects Ptr[T] or ConstPtr[T]")
                ret = I32
            expr.inferred_type = str(ret)
            return ret
        if callee == "ptr_set":
            arg_types = [self._check_expr(arg, owner_fn) for arg in expr.args]
            if len(arg_types) != 2:
                self.diag.error(expr.span, "ptr_set expects 2 arguments")
            elif arg_types[0].name == "ConstPtr":
                self.diag.error(expr.args[0].span, "cannot write through ConstPtr[T]")
            elif arg_types[0].name != "Ptr" or not arg_types[0].params:
                self.diag.error(expr.args[0].span, "ptr_set expects Ptr[T]")
            elif arg_types[0].params[0] != arg_types[1]:
                self.diag.error(expr.args[1].span, f"ptr_set expects {arg_types[0].params[0]}, got {arg_types[1]}")
            expr.inferred_type = str(VOID)
            return VOID
        if callee == "const_ptr_new":
            if len(expr.args) != 1:
                self.diag.error(expr.span, "const_ptr_new expects 1 argument")
            arg_types = [self._check_expr(arg, owner_fn) for arg in expr.args]
            ret = const_ptr(arg_types[0] if arg_types else I32)
            expr.inferred_type = str(ret)
            return ret
        if callee == "call":
            if not expr.args:
                self.diag.error(expr.span, "call expects a function pointer and arguments")
                expr.inferred_type = str(I32)
                return I32
            fn_ty = self._check_expr(expr.args[0], owner_fn)
            if fn_ty.name != "Func" or not fn_ty.params:
                self.diag.error(expr.args[0].span, f"call expects Func[..., R], got {fn_ty}")
                expr.inferred_type = str(I32)
                return I32
            expected_args = list(fn_ty.params[:-1])
            ret = fn_ty.params[-1]
            for idx, arg in enumerate(expr.args[1:]):
                got = self._check_expr(arg, owner_fn)
                if idx < len(expected_args) and got != expected_args[idx]:
                    self.diag.error(arg.span, f"call argument expects {expected_args[idx]}, got {got}")
            if len(expr.args) - 1 != len(expected_args):
                self.diag.error(expr.span, f"call expects {len(expected_args)} call arguments")
            expr.inferred_type = str(ret)
            return ret
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
        if isinstance(target, ast.UnaryExpr) and target.op == "*":
            if target.rhs:
                rhs = self._check_expr(target.rhs, owner_fn)
                if rhs.name == "ConstPtr":
                    self.diag.error(target.span, "cannot write through ConstPtr[T]")
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
        if tref.name == "Ptr" and tref.params:
            return ptr(self._resolve_type(tref.params[0], generics))
        if tref.name == "ConstPtr" and tref.params:
            return const_ptr(self._resolve_type(tref.params[0], generics))
        if tref.name == "Func" and tref.params:
            resolved = [self._resolve_type(p, generics) for p in tref.params]
            return func(resolved[:-1], resolved[-1]) if resolved else func([], I32)
        if tref.params:
            return Type(tref.name, tuple(self._resolve_type(p, generics) for p in tref.params))
        return BUILTINS.get(tref.name, Type(tref.name))
