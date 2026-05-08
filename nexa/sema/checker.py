from __future__ import annotations

from dataclasses import dataclass, field

from nexa.frontend import ast
from nexa.frontend.diagnostics import DiagnosticBag
from .symbols import ScopeStack, Symbol
from .types import BOOL, BUILTINS, F64, I32, I64, JSON, RANGE, STR, TCP_LISTENER, TCP_STREAM, VOID, Type, array_any, array_type, channel, dict_type, fn_type, is_type_var, type_var


STD_MODULES = {"os", "fs", "io", "math", "str", "array", "collections", "time", "json", "net", "testing"}


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


def _stdlib_functions() -> dict[str, FuncSig]:
    t = type_var("T")
    u = type_var("U")
    arr_t = array_any(t)
    str_arr = array_any(STR)
    return {
        "os.getenv": FuncSig([STR], STR),
        "os.setenv": FuncSig([STR, STR], VOID),
        "os.exit": FuncSig([I32], VOID),
        "os.sleep": FuncSig([I32], VOID),
        "os.args": FuncSig([], str_arr),
        "os.getcwd": FuncSig([], STR),
        "os.chdir": FuncSig([STR], VOID),
        "fs.read_file": FuncSig([STR], STR),
        "fs.write_file": FuncSig([STR, STR], VOID),
        "fs.append_file": FuncSig([STR, STR], VOID),
        "fs.exists": FuncSig([STR], BOOL),
        "fs.is_dir": FuncSig([STR], BOOL),
        "fs.mkdir": FuncSig([STR], VOID),
        "fs.read_dir": FuncSig([STR], str_arr),
        "fs.remove": FuncSig([STR], VOID),
        "io.read_file": FuncSig([STR], STR),
        "io.write_file": FuncSig([STR, STR], VOID),
        "io.append_file": FuncSig([STR, STR], VOID),
        "io.exists": FuncSig([STR], BOOL),
        "io.is_dir": FuncSig([STR], BOOL),
        "io.mkdir": FuncSig([STR], VOID),
        "io.read_dir": FuncSig([STR], str_arr),
        "io.remove": FuncSig([STR], VOID),
        "math.abs": FuncSig([I32], I32),
        "math.max": FuncSig([I32, I32], I32),
        "math.min": FuncSig([I32, I32], I32),
        "math.pow": FuncSig([F64, F64], F64),
        "math.sqrt": FuncSig([F64], F64),
        "math.sin": FuncSig([F64], F64),
        "math.cos": FuncSig([F64], F64),
        "math.floor": FuncSig([F64], I32),
        "math.ceil": FuncSig([F64], I32),
        "math.random": FuncSig([], F64),
        "str.len": FuncSig([STR], I32),
        "str.concat": FuncSig([STR, STR], STR),
        "str.contains": FuncSig([STR, STR], BOOL),
        "str.starts_with": FuncSig([STR, STR], BOOL),
        "str.ends_with": FuncSig([STR, STR], BOOL),
        "str.split": FuncSig([STR, STR], str_arr),
        "str.join": FuncSig([str_arr, STR], STR),
        "str.replace": FuncSig([STR, STR, STR], STR),
        "str.substr": FuncSig([STR, I32, I32], STR),
        "str.trim": FuncSig([STR], STR),
        "str.to_upper": FuncSig([STR], STR),
        "str.to_lower": FuncSig([STR], STR),
        "str.parse_i32": FuncSig([STR], I32),
        "str.parse_f64": FuncSig([STR], F64),
        "str.format_i32": FuncSig([I32], STR),
        "str.format_f64": FuncSig([F64], STR),
        "array.len": FuncSig([arr_t], I32, ["T"]),
        "array.push": FuncSig([arr_t, t], arr_t, ["T"]),
        "array.pop": FuncSig([arr_t], t, ["T"]),
        "array.index_of": FuncSig([arr_t, t], I32, ["T"]),
        "array.contains": FuncSig([arr_t, t], BOOL, ["T"]),
        "array.map": FuncSig([arr_t, Type("fn")], array_any(u), ["T", "U"]),
        "array.filter": FuncSig([arr_t, Type("fn")], arr_t, ["T"]),
        "array.reduce": FuncSig([arr_t, u, Type("fn")], u, ["T", "U"]),
        "array.sort": FuncSig([array_any(I32)], array_any(I32)),
        "array.reverse": FuncSig([arr_t], arr_t, ["T"]),
        "array.slice": FuncSig([arr_t, I32, I32], arr_t, ["T"]),
        "collections.len": FuncSig([arr_t], I32, ["T"]),
        "collections.push": FuncSig([arr_t, t], arr_t, ["T"]),
        "collections.pop": FuncSig([arr_t], t, ["T"]),
        "collections.index_of": FuncSig([arr_t, t], I32, ["T"]),
        "collections.contains": FuncSig([arr_t, t], BOOL, ["T"]),
        "collections.map": FuncSig([arr_t, Type("fn")], array_any(u), ["T", "U"]),
        "collections.filter": FuncSig([arr_t, Type("fn")], arr_t, ["T"]),
        "collections.reduce": FuncSig([arr_t, u, Type("fn")], u, ["T", "U"]),
        "collections.sort": FuncSig([array_any(I32)], array_any(I32)),
        "collections.reverse": FuncSig([arr_t], arr_t, ["T"]),
        "collections.slice": FuncSig([arr_t, I32, I32], arr_t, ["T"]),
        "time.now_ms": FuncSig([], I64),
        "time.now_ns": FuncSig([], I64),
        "time.sleep": FuncSig([I32], VOID),
        "time.format_iso": FuncSig([I64], STR),
        "json.parse": FuncSig([STR], JSON),
        "json.stringify": FuncSig([JSON], STR),
        "net.dial": FuncSig([STR, I32], TCP_STREAM),
        "net.listen": FuncSig([STR, I32], TCP_LISTENER),
        "net.tcp_read": FuncSig([TCP_STREAM, I32], STR),
        "net.tcp_write": FuncSig([TCP_STREAM, STR], I32),
        "net.tcp_close": FuncSig([TCP_STREAM], VOID),
        "testing.assert_eq": FuncSig([t, t], VOID, ["T"]),
        "testing.assert_true": FuncSig([BOOL], VOID),
        "testing.assert_false": FuncSig([BOOL], VOID),
        "testing.assert_panic": FuncSig([Type("fn")], VOID),
    }


class Checker:
    def __init__(self, diagnostics: DiagnosticBag | None = None, mode: str = "full") -> None:
        self.diag = diagnostics or DiagnosticBag()
        self.scopes = ScopeStack()
        self.mode = mode
        self.loop_depth = 0
        self.generic_calls: list[GenericCallSite] = []
        self.structs: dict[str, dict[str, Type]] = {}
        self.enums: dict[str, ast.EnumDef] = {}
        self.enum_variants: dict[str, tuple[str, Type | None, list[str]]] = {}
        self.functions: dict[str, FuncSig] = {
            "print": FuncSig([I32], VOID),
            "panic": FuncSig([STR], VOID),
            "chan": FuncSig([I32], channel(I32)),
            "send": FuncSig([channel(I32), I32], VOID),
            "recv": FuncSig([channel(I32)], I32),
        }
        self.functions.update(_stdlib_functions())

    def analyze(self, module: ast.Module) -> SemanticResult:
        for item in module.items:
            if isinstance(item, ast.StructDef):
                fields = {f.name: self._resolve_type(f.type_ref) for f in item.fields}
                self.structs[item.name] = fields
                self.scopes.declare(Symbol(item.name, "struct", Type(item.name), self.scopes.scope_id))
            elif isinstance(item, ast.EnumDef):
                self.enums[item.name] = item
                enum_ty = Type(item.name, tuple(type_var(g) for g in item.generic_params))
                self.scopes.declare(Symbol(item.name, "enum", enum_ty, self.scopes.scope_id))
                for variant in item.variants:
                    payload = self._resolve_type(variant.payload, item.generic_params) if variant.payload else None
                    self.enum_variants[variant.name] = (item.name, payload, list(item.generic_params))
                    params = [payload] if payload else []
                    self.functions[variant.name] = FuncSig(params, enum_ty, list(item.generic_params))
                    self.scopes.declare(Symbol(variant.name, "enum_variant", enum_ty, self.scopes.scope_id))
            elif isinstance(item, ast.Function):
                ptys = [self._resolve_type(p.type_ref, item.generic_params) for p in item.params]
                rty = self._resolve_type(item.ret_type, item.generic_params)
                key = self._fn_key(item.name, len(item.params))
                self.functions[key] = FuncSig(ptys, rty, item.generic_params, item.generic_bounds)
                self.functions.setdefault(item.name, self.functions[key])
                self.scopes.declare(Symbol(key, "fn", Type("fn"), self.scopes.scope_id))
        for item in module.items:
            if isinstance(item, ast.Function):
                self._check_function(item)
        return SemanticResult(module, self.scopes, self.functions, self.generic_calls)

    def _fn_key(self, name: str, arity: int) -> str:
        return f"{name}__{arity}"

    def _check_function(self, fn: ast.Function) -> None:
        self.scopes.push()
        for p in fn.params:
            ty = self._resolve_type(p.type_ref, fn.generic_params)
            if not self.scopes.declare(Symbol(p.name, "param", ty, self.scopes.scope_id)):
                self.diag.error(p.span, f"重复参数名: {p.name}")
        self._check_block(fn.body, self._resolve_type(fn.ret_type, fn.generic_params), fn)
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
                ann = I32
                self.diag.error(stmt.span, f"变量 {stmt.name} 缺少类型信息", fixits=[f"let {stmt.name}: i32 = ...;"], code="E003")
            if val_ty is not None and not self._type_compatible(ann, val_ty):
                self.diag.error(stmt.span, f"类型不匹配: expected {ann}, actual {val_ty}", fixits=[f"将变量类型改为 {val_ty}"], code="E003")
            if not self.scopes.declare(Symbol(stmt.name, "var", ann, self.scopes.scope_id)):
                self.diag.error(stmt.span, f"重复声明: {stmt.name}")
        elif isinstance(stmt, ast.AssignStmt):
            target_ty = self._check_assign_target(stmt.target, owner_fn)
            rhs = self._check_expr(stmt.value, owner_fn)
            if not self._type_compatible(target_ty, rhs):
                self.diag.error(stmt.span, f"赋值类型不匹配: expected {target_ty}, actual {rhs}", code="E003")
        elif isinstance(stmt, ast.ExprStmt):
            self._check_expr(stmt.expr, owner_fn)
        elif isinstance(stmt, ast.ReturnStmt):
            got = VOID if stmt.value is None else self._check_expr(stmt.value, owner_fn)
            if not self._type_compatible(ret_ty, got):
                self.diag.error(stmt.span, f"返回类型不匹配: expected {ret_ty}, actual {got}", code="E003")
        elif isinstance(stmt, ast.IfStmt):
            cty = self._check_expr(stmt.cond, owner_fn)
            if cty != BOOL:
                self.diag.error(stmt.cond.span, f"if 条件必须是 bool，实际 {cty}")
            self._check_block(stmt.then_block, ret_ty, owner_fn)
            if stmt.else_block:
                self._check_block(stmt.else_block, ret_ty, owner_fn)
        elif isinstance(stmt, ast.WhileStmt):
            cty = self._check_expr(stmt.cond, owner_fn)
            if cty != BOOL:
                self.diag.error(stmt.cond.span, "while 条件必须是 bool")
            self.loop_depth += 1
            self._check_block(stmt.body, ret_ty, owner_fn)
            self.loop_depth -= 1
        elif isinstance(stmt, ast.ForStmt):
            self.scopes.push()
            if stmt.init:
                self._check_stmt(stmt.init, ret_ty, owner_fn)
            if stmt.cond and self._check_expr(stmt.cond, owner_fn) != BOOL:
                self.diag.error(stmt.cond.span, "for 条件必须是 bool")
            self.loop_depth += 1
            self._check_block(stmt.body, ret_ty, owner_fn)
            if stmt.step:
                self._check_stmt(stmt.step, ret_ty, owner_fn)
            self.loop_depth -= 1
            self.scopes.pop()
        elif isinstance(stmt, ast.ForInStmt):
            iterable_ty = self._check_expr(stmt.iterable, owner_fn)
            item_ty = I32
            if iterable_ty.name == "Array" and iterable_ty.params:
                item_ty = iterable_ty.params[0]
            elif iterable_ty != RANGE:
                self.diag.error(stmt.iterable.span, f"for-in expected Range or Array, actual {iterable_ty}", code="E003")
            self.scopes.push()
            self.scopes.declare(Symbol(stmt.name, "var", item_ty, self.scopes.scope_id))
            self.loop_depth += 1
            self._check_block(stmt.body, ret_ty, owner_fn)
            self.loop_depth -= 1
            self.scopes.pop()
        elif isinstance(stmt, ast.BreakStmt):
            if self.loop_depth == 0:
                self.diag.error(stmt.span, "break 只能出现在循环内部")
        elif isinstance(stmt, ast.ContinueStmt):
            if self.loop_depth == 0:
                self.diag.error(stmt.span, "continue 只能出现在循环内部")
        elif isinstance(stmt, ast.Block):
            self._check_block(stmt, ret_ty, owner_fn)
        elif isinstance(stmt, ast.SpawnStmt):
            self._check_expr(stmt.expr, owner_fn)

    def _check_assign_target(self, expr: ast.Expr, owner_fn: ast.Function) -> Type:
        if isinstance(expr, ast.NameExpr):
            sym = self.scopes.lookup(expr.name)
            if sym is None:
                self.diag.error(expr.span, f"未声明变量: {expr.name}", fixits=[f"let {expr.name}: i32 = ...;"], code="E002")
                return I32
            return sym.ty
        if isinstance(expr, ast.IndexExpr):
            return self._check_index(expr, owner_fn)
        if isinstance(expr, ast.SliceExpr):
            return self._check_slice(expr, owner_fn)
        if isinstance(expr, ast.RangeExpr):
            return self._check_range(expr, owner_fn)
        if isinstance(expr, ast.DictLit):
            return self._check_dict(expr, owner_fn)
        if isinstance(expr, ast.FieldAccess):
            return self._check_field(expr, owner_fn)
        self.diag.error(expr.span, "非法赋值目标")
        return I32

    def _check_expr(self, expr: ast.Expr | None, owner_fn: ast.Function) -> Type:
        if expr is None:
            return VOID
        if isinstance(expr, ast.IntLit):
            expr.inferred_type = str(I32); return I32
        if isinstance(expr, ast.FloatLit):
            expr.inferred_type = str(F64); return F64
        if isinstance(expr, ast.BoolLit):
            expr.inferred_type = str(BOOL); return BOOL
        if isinstance(expr, ast.StrLit):
            expr.inferred_type = str(STR); return STR
        if isinstance(expr, ast.InterpolatedString):
            for part in expr.parts:
                if isinstance(part, ast.Expr):
                    self._check_expr(part, owner_fn)
            expr.inferred_type = str(STR); return STR
        if isinstance(expr, ast.NameExpr):
            sym = self.scopes.lookup(expr.name)
            if sym is None:
                self.diag.error(expr.span, f"未声明标识符: {expr.name}", fixits=[f"let {expr.name}: i32 = ...;"], code="E002")
                if expr.name in self.enum_variants:
                    enum_name, _, generics = self.enum_variants[expr.name]
                    ty = Type(enum_name, tuple(I32 for _ in generics))
                    expr.inferred_type = str(ty); return ty
                expr.inferred_type = str(I32); return I32
            expr.inferred_type = str(sym.ty); return sym.ty
        if isinstance(expr, ast.ArrayLit):
            elem_ty = I32
            if expr.elements:
                elem_ty = self._check_expr(expr.elements[0], owner_fn)
                for element in expr.elements[1:]:
                    got = self._check_expr(element, owner_fn)
                    if got != elem_ty:
                        self.diag.error(element.span, f"数组元素类型不一致: expected {elem_ty}, actual {got}", code="E003")
            ty = array_type(elem_ty, len(expr.elements))
            expr.inferred_type = str(ty); return ty
        if isinstance(expr, ast.IndexExpr):
            return self._check_index(expr, owner_fn)
        if isinstance(expr, ast.SliceExpr):
            return self._check_slice(expr, owner_fn)
        if isinstance(expr, ast.RangeExpr):
            return self._check_range(expr, owner_fn)
        if isinstance(expr, ast.DictLit):
            return self._check_dict(expr, owner_fn)
        if isinstance(expr, ast.FieldAccess):
            return self._check_field(expr, owner_fn)
        if isinstance(expr, ast.StructLit):
            fields = self.structs.get(expr.name)
            if fields is None:
                self.diag.error(expr.span, f"未知结构体: {expr.name}")
                expr.inferred_type = expr.name; return Type(expr.name)
            for name, value in expr.fields.items():
                if name not in fields:
                    self.diag.error(expr.span, f"结构体 {expr.name} 没有字段 {name}")
                    continue
                got = self._check_expr(value, owner_fn)
                if got != fields[name]:
                    self.diag.error(value.span, f"字段 {name} 类型不匹配: expected {fields[name]}, actual {got}", code="E003")
            expr.inferred_type = expr.name; return Type(expr.name)
        if isinstance(expr, ast.BlockExpr) and expr.block:
            self.scopes.push()
            last_ty = VOID
            for st in expr.block.stmts[:-1]:
                self._check_stmt(st, VOID, owner_fn)
            if expr.block.stmts:
                tail = expr.block.stmts[-1]
                if isinstance(tail, ast.ExprStmt):
                    last_ty = self._check_expr(tail.expr, owner_fn)
                else:
                    self._check_stmt(tail, VOID, owner_fn)
            self.scopes.pop()
            expr.inferred_type = str(last_ty); return last_ty
        if isinstance(expr, ast.SelectExpr):
            return self._check_select(expr, owner_fn)
        if isinstance(expr, ast.MatchExpr):
            return self._check_match(expr, owner_fn)
        if isinstance(expr, ast.LambdaExpr):
            return self._check_lambda(expr, owner_fn)
        if isinstance(expr, ast.UnaryExpr):
            rhs = self._check_expr(expr.rhs, owner_fn)
            if expr.op == "!":
                if rhs != BOOL:
                    self.diag.error(expr.span, "! 运算需要 bool")
                expr.inferred_type = str(BOOL); return BOOL
            if expr.op == "-":
                if rhs not in {I32, F64}:
                    self.diag.error(expr.span, "负号运算需要 i32 或 f64")
                expr.inferred_type = str(rhs); return rhs
        if isinstance(expr, ast.BinaryExpr):
            return self._check_binary(expr, owner_fn)
        if isinstance(expr, ast.CallExpr):
            return self._check_call(expr, owner_fn)
        self.diag.error(expr.span, "不支持的表达式")
        expr.inferred_type = str(I32)
        return I32

    def _check_range(self, expr: ast.RangeExpr, owner_fn: ast.Function) -> Type:
        if expr.start and self._check_expr(expr.start, owner_fn) != I32:
            self.diag.error(expr.start.span, "range start must be i32", code="E003")
        if expr.end and self._check_expr(expr.end, owner_fn) != I32:
            self.diag.error(expr.end.span, "range end must be i32", code="E003")
        expr.inferred_type = str(RANGE); return RANGE

    def _check_dict(self, expr: ast.DictLit, owner_fn: ast.Function) -> Type:
        key_ty = STR
        val_ty = I32
        if expr.entries:
            key_ty = self._check_expr(expr.entries[0][0], owner_fn)
            val_ty = self._check_expr(expr.entries[0][1], owner_fn)
            for key, value in expr.entries[1:]:
                got_key = self._check_expr(key, owner_fn)
                got_val = self._check_expr(value, owner_fn)
                if got_key != key_ty:
                    self.diag.error(key.span, f"dict key type mismatch: expected {key_ty}, actual {got_key}", code="E003")
                if got_val != val_ty:
                    self.diag.error(value.span, f"dict value type mismatch: expected {val_ty}, actual {got_val}", code="E003")
        ty = dict_type(key_ty, val_ty)
        expr.inferred_type = str(ty); return ty

    def _check_slice(self, expr: ast.SliceExpr, owner_fn: ast.Function) -> Type:
        target_ty = self._check_expr(expr.target, owner_fn)
        if expr.start and self._check_expr(expr.start, owner_fn) != I32:
            self.diag.error(expr.start.span, "slice start must be i32", code="E003")
        if expr.end and self._check_expr(expr.end, owner_fn) != I32:
            self.diag.error(expr.end.span, "slice end must be i32", code="E003")
        if target_ty.name != "Array" or not target_ty.params:
            self.diag.error(expr.span, f"slice target must be array, actual {target_ty}", code="E003")
            expr.inferred_type = str(array_any(I32)); return array_any(I32)
        ty = array_any(target_ty.params[0])
        expr.inferred_type = str(ty); return ty

    def _check_lambda(self, expr: ast.LambdaExpr, owner_fn: ast.Function, expected_params: list[Type] | None = None) -> Type:
        self.scopes.push()
        param_tys: list[Type] = []
        for idx, param in enumerate(expr.params):
            ty = self._resolve_type(param.type_ref, owner_fn.generic_params) if param.type_ref else (expected_params[idx] if expected_params and idx < len(expected_params) else I32)
            param_tys.append(ty)
            self.scopes.declare(Symbol(param.name, "param", ty, self.scopes.scope_id))
        if isinstance(expr.body, ast.Block):
            ret_ty = self._check_block_tail(expr.body, owner_fn)
        elif isinstance(expr.body, ast.Expr):
            ret_ty = self._check_expr(expr.body, owner_fn)
        else:
            ret_ty = VOID
        self.scopes.pop()
        ty = fn_type(param_tys, ret_ty)
        expr.inferred_type = str(ty); return ty

    def _check_block_tail(self, block: ast.Block, owner_fn: ast.Function) -> Type:
        last_ty = VOID
        for st in block.stmts[:-1]:
            self._check_stmt(st, VOID, owner_fn)
        if block.stmts:
            tail = block.stmts[-1]
            if isinstance(tail, ast.ExprStmt):
                last_ty = self._check_expr(tail.expr, owner_fn)
            elif isinstance(tail, ast.ReturnStmt) and tail.value:
                last_ty = self._check_expr(tail.value, owner_fn)
            else:
                self._check_stmt(tail, VOID, owner_fn)
        return last_ty

    def _check_match(self, expr: ast.MatchExpr, owner_fn: ast.Function) -> Type:
        value_ty = self._check_expr(expr.value, owner_fn)
        arm_tys: list[Type] = []
        for arm in expr.arms:
            variant_info = self.enum_variants.get(arm.pattern.variant)
            payload_ty = None
            if variant_info is None:
                self.diag.error(arm.pattern.span, f"unknown enum variant {arm.pattern.variant}", code="E002")
            else:
                enum_name, payload_ty, _ = variant_info
                if value_ty.name != enum_name:
                    self.diag.error(arm.pattern.span, f"match variant {arm.pattern.variant} does not belong to {value_ty}", code="E003")
                if payload_ty and is_type_var(payload_ty) and value_ty.params:
                    payload_ty = value_ty.params[0]
            self.scopes.push()
            if arm.pattern.binding and payload_ty:
                self.scopes.declare(Symbol(arm.pattern.binding, "var", payload_ty, self.scopes.scope_id))
            arm_tys.append(self._check_block_tail(arm.body, owner_fn))
            self.scopes.pop()
        first = arm_tys[0] if arm_tys else VOID
        for ty in arm_tys[1:]:
            if ty != first and ty != VOID and first != VOID:
                self.diag.error(expr.span, f"match arms type mismatch: {first} vs {ty}", code="E003")
        expr.inferred_type = str(first); return first

    def _check_index(self, expr: ast.IndexExpr, owner_fn: ast.Function) -> Type:
        target_ty = self._check_expr(expr.target, owner_fn)
        index_ty = self._check_expr(expr.index, owner_fn)
        if index_ty != I32:
            self.diag.error(expr.span, f"数组索引必须是 i32，实际 {index_ty}")
        if target_ty.name != "Array" or not target_ty.params:
            self.diag.error(expr.span, f"索引目标必须是数组，实际 {target_ty}")
            expr.inferred_type = str(I32); return I32
        elem = target_ty.params[0]
        expr.inferred_type = str(elem); return elem

    def _check_field(self, expr: ast.FieldAccess, owner_fn: ast.Function) -> Type:
        target_ty = self._check_expr(expr.target, owner_fn)
        fields = self.structs.get(target_ty.name)
        if fields is None:
            self.diag.error(expr.span, f"字段访问目标必须是结构体，实际 {target_ty}")
            expr.inferred_type = str(I32); return I32
        if expr.field not in fields:
            self.diag.error(expr.span, f"结构体 {target_ty.name} 没有字段 {expr.field}")
            expr.inferred_type = str(I32); return I32
        ty = fields[expr.field]
        expr.inferred_type = str(ty); return ty

    def _check_binary(self, expr: ast.BinaryExpr, owner_fn: ast.Function) -> Type:
        lt = self._check_expr(expr.lhs, owner_fn)
        rt = self._check_expr(expr.rhs, owner_fn)
        if expr.op == "+" and lt == STR and rt == STR:
            expr.inferred_type = str(STR); return STR
        if expr.op in {"+", "-", "*", "/", "%"}:
            if lt != rt or lt not in {I32, F64}:
                self.diag.error(expr.span, f"算术运算类型不匹配: expected same i32/f64, actual {lt} and {rt}", code="E003")
            expr.inferred_type = str(lt); return lt
        if expr.op in {"==", "!=", "<", "<=", ">", ">="}:
            if lt != rt:
                self.diag.error(expr.span, f"比较两侧类型必须一致: {lt} vs {rt}", code="E003")
            expr.inferred_type = str(BOOL); return BOOL
        if expr.op in {"&&", "||"}:
            if lt != BOOL or rt != BOOL:
                self.diag.error(expr.span, "逻辑运算要求 bool")
            expr.inferred_type = str(BOOL); return BOOL
        expr.inferred_type = str(I32); return I32

    def _check_call(self, expr: ast.CallExpr, owner_fn: ast.Function) -> Type:
        if isinstance(expr.callee, ast.NameExpr):
            callee = expr.callee.name
        elif isinstance(expr.callee, ast.FieldAccess) and isinstance(expr.callee.target, ast.NameExpr):
            # Imported modules are flattened into the compile unit, but this lets
            # users keep Python-like call sites such as math.add(1, 2).
            module = expr.callee.target.name
            callee = f"{module}.{expr.callee.field}" if module in STD_MODULES else expr.callee.field
        else:
            self.diag.error(expr.span, "只支持直接函数调用")
            expr.inferred_type = str(I32); return I32
        if callee in self.enum_variants:
            enum_name, payload_ty, generics = self.enum_variants[callee]
            arg_tys = [self._check_expr(arg, owner_fn) for arg in expr.args]
            if payload_ty and arg_tys and is_type_var(payload_ty):
                params = (arg_tys[0],)
            else:
                params = tuple(I32 for _ in generics)
            if payload_ty and arg_tys and not is_type_var(payload_ty) and not self._type_compatible(payload_ty, arg_tys[0]):
                self.diag.error(expr.args[0].span, f"enum payload mismatch: expected {payload_ty}, actual {arg_tys[0]}", code="E003")
            ty = Type(enum_name, params)
            expr.inferred_type = str(ty); return ty
        if callee in {"array.map", "array.filter", "array.reduce", "collections.map", "collections.filter", "collections.reduce"}:
            return self._check_array_hof(callee, expr, owner_fn)
        sig = self.functions.get(self._fn_key(callee, len(expr.args))) or self.functions.get(callee)
        if sig is None:
            self.diag.error(expr.span, f"未定义函数: {callee}")
            expr.inferred_type = str(I32); return I32
        if sig.generic_params:
            subst: dict[str, Type] = {}
            for i, arg in enumerate(expr.args):
                aty = self._check_expr(arg, owner_fn)
                if i < len(sig.params):
                    self._unify(sig.params[i], aty, subst, arg.span)
            for g in sig.generic_params:
                subst.setdefault(g, I32)
            ret = self._apply_subst(sig.ret, subst)
            self.generic_calls.append(GenericCallSite(callee, subst.copy(), expr.span))
            expr.inferred_type = str(ret); return ret
        if len(sig.params) != len(expr.args):
            self.diag.error(expr.span, f"参数数量不匹配: expected {len(sig.params)}, actual {len(expr.args)}")
        for i, arg in enumerate(expr.args):
            aty = self._check_expr(arg, owner_fn)
            if i < len(sig.params) and not self._type_compatible(sig.params[i], aty):
                self.diag.error(arg.span, f"参数类型不匹配: expected {sig.params[i]}, actual {aty}", code="E003")
        expr.inferred_type = str(sig.ret); return sig.ret

    def _check_array_hof(self, callee: str, expr: ast.CallExpr, owner_fn: ast.Function) -> Type:
        if not expr.args:
            self.diag.error(expr.span, f"{callee} needs an array argument", code="E003")
            expr.inferred_type = str(I32); return I32
        arr_ty = self._check_expr(expr.args[0], owner_fn)
        elem_ty = arr_ty.params[0] if arr_ty.name == "Array" and arr_ty.params else I32
        if "map" in callee:
            if len(expr.args) < 2:
                self.diag.error(expr.span, f"{callee} needs a lambda", code="E003")
                expr.inferred_type = str(array_any(I32)); return array_any(I32)
            fn_ty = self._check_lambda(expr.args[1], owner_fn, [elem_ty]) if isinstance(expr.args[1], ast.LambdaExpr) else self._check_expr(expr.args[1], owner_fn)
            ret_ty = fn_ty.params[-1] if fn_ty.name == "Fn" and fn_ty.params else I32
            ty = array_any(ret_ty)
            expr.inferred_type = str(ty); return ty
        if "filter" in callee:
            if len(expr.args) >= 2:
                fn_ty = self._check_lambda(expr.args[1], owner_fn, [elem_ty]) if isinstance(expr.args[1], ast.LambdaExpr) else self._check_expr(expr.args[1], owner_fn)
                if fn_ty.name == "Fn" and fn_ty.params and fn_ty.params[-1] != BOOL:
                    self.diag.error(expr.args[1].span, f"{callee} lambda must return bool", code="E003")
            ty = array_any(elem_ty)
            expr.inferred_type = str(ty); return ty
        init_ty = self._check_expr(expr.args[1], owner_fn) if len(expr.args) > 1 else I32
        if len(expr.args) >= 3:
            self._check_lambda(expr.args[2], owner_fn, [init_ty, elem_ty]) if isinstance(expr.args[2], ast.LambdaExpr) else self._check_expr(expr.args[2], owner_fn)
        expr.inferred_type = str(init_ty); return init_ty

    def _check_select(self, expr: ast.SelectExpr, owner_fn: ast.Function) -> Type:
        default_cases = [c for c in expr.cases if c.kind == "default"]
        if len(default_cases) != 1:
            self.diag.error(expr.span, "select 必须且只能有一个 default 分支")
        seen: list[Type] = []
        for c in expr.cases:
            case_ty = I32
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
                    self.diag.error(c.span, f"send 类型不匹配: Chan[{cty.params[0]}] <- {vty}", code="E003")
                case_ty = vty
            self.scopes.push()
            for st in c.body.stmts[:-1]:
                self._check_stmt(st, VOID, owner_fn)
            if c.body.stmts and isinstance(c.body.stmts[-1], ast.ExprStmt):
                case_ty = self._check_expr(c.body.stmts[-1].expr, owner_fn)
            elif c.body.stmts:
                self._check_stmt(c.body.stmts[-1], VOID, owner_fn)
            self.scopes.pop()
            seen.append(case_ty)
        expr.inferred_type = str(seen[0] if seen else I32)
        return seen[0] if seen else I32

    def _type_compatible(self, expected: Type, got: Type) -> bool:
        if expected.name == "*" or got.name == "*":
            return True
        if expected == got:
            return True
        if expected.name != got.name or len(expected.params) != len(got.params):
            return False
        return all(self._type_compatible(a, b) for a, b in zip(expected.params, got.params, strict=True))

    def _unify(self, expected: Type, got: Type, subst: dict[str, Type], span) -> None:
        if expected.name == "*" or got.name == "*":
            return
        if is_type_var(expected):
            key = expected.name[1:]
            if key in subst and subst[key] != got:
                self.diag.error(span, f"泛型实参冲突: {subst[key]} vs {got}")
            else:
                subst[key] = got
            return
        if expected.name != got.name or len(expected.params) != len(got.params):
            self.diag.error(span, f"参数类型不匹配: expected {expected}, actual {got}", code="E003")
            return
        for a, b in zip(expected.params, got.params, strict=True):
            self._unify(a, b, subst, span)

    def _apply_subst(self, ty: Type, subst: dict[str, Type]) -> Type:
        if is_type_var(ty):
            return subst.get(ty.name[1:], I32)
        return Type(ty.name, tuple(self._apply_subst(p, subst) for p in ty.params))

    def _resolve_type(self, tref: ast.TypeRef | None, generics: list[str] | None = None) -> Type:
        if tref is None:
            return VOID
        generics = generics or []
        if tref.name in generics:
            return type_var(tref.name)
        if tref.name == "Chan" and tref.params:
            return channel(self._resolve_type(tref.params[0], generics))
        if tref.name == "Array" and len(tref.params) >= 2:
            inner = self._resolve_type(tref.params[0], generics)
            if tref.params[1].name == "*":
                return array_any(inner)
            try:
                size = int(tref.params[1].name)
            except ValueError:
                size = 0
            return array_type(inner, size)
        if tref.name == "Dict" and len(tref.params) >= 2:
            return dict_type(self._resolve_type(tref.params[0], generics), self._resolve_type(tref.params[1], generics))
        if tref.name == "Fn" and tref.params:
            params = [self._resolve_type(p, generics) for p in tref.params]
            return fn_type(params[:-1], params[-1])
        if tref.params:
            return Type(tref.name, tuple(self._resolve_type(p, generics) for p in tref.params))
        return BUILTINS.get(tref.name, Type(tref.name))
