from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from nexa.backend.asm_x64 import _compute_signatures, emit_function, emit_module
from nexa.backend.build import BuildError, BuildOutput, build_module, run_executable
from nexa.backend.llvm_backend import emit_llvm_ir, validate_llvm_subset
from nexa.backend.regalloc import compute_intervals, linear_scan
from nexa.frontend import ast
from nexa.frontend.diagnostics import Diagnostic, DiagnosticBag, Level
from nexa.frontend.lexer import LexTables, Lexer
from nexa.frontend.tokens import Span
from nexa.frontend.macro import MacroExpander
from nexa.frontend.parser import Parser
from nexa.frontend.tokens import Token
from nexa.ir.hir import HIRInstr, HIRKind, HIRModule
from nexa.ir.lower import Lowerer, hir_to_mir
from nexa.ir.mir import MIRFunction, MIRModule
from nexa.opt.passes import run_optimizations
from nexa.sema.checker import Checker, SemanticResult
from nexa.sema.monomorphize import monomorphize
from nexa.vm import HIRVM, VMFrame


@dataclass(slots=True)
class StageResult:
    name: str
    status: str
    detail: str


@dataclass(slots=True)
class BuildArtifacts:
    tokens: list[str] = field(default_factory=list)
    tables: dict[str, list[str]] = field(default_factory=dict)
    ast_text: str = ""
    symbols: list[str] = field(default_factory=list)
    hir_raw: HIRModule | None = None
    hir_opt: HIRModule | None = None
    cfg: dict[str, list[str]] = field(default_factory=dict)
    asm: dict[str, str] = field(default_factory=dict)
    asm_module: str = ""
    llvm_ir: str = ""
    hir_raw_structured: list[dict] = field(default_factory=list)
    hir_opt_structured: list[dict] = field(default_factory=list)
    symbol_rows: list[dict] = field(default_factory=list)
    token_rows: list[dict] = field(default_factory=list)
    cfg_structured: dict[str, dict] = field(default_factory=dict)


@dataclass(slots=True)
class BuildResult:
    diagnostics: list[Diagnostic]
    artifacts: BuildArtifacts
    timeline: list[StageResult] = field(default_factory=list)
    run_value: int | None = None
    run_stdout: list[str] = field(default_factory=list)
    vm_trace: list[VMFrame] = field(default_factory=list)
    build: BuildOutput | None = None
    exe_exit_code: int | None = None
    exe_stdout: str = ""
    exe_stderr: str = ""


def _ast_dump(node: object, indent: int = 0) -> list[str]:
    pad = "  " * indent
    if isinstance(node, ast.Module):
        out = [f"{pad}Module"]
        for i in node.items:
            out.extend(_ast_dump(i, indent + 1))
        return out
    if isinstance(node, ast.Function):
        prefix = "pub " if node.is_public else ""
        out = [f"{pad}{prefix}Function {node.name}"]
        for p in node.params:
            out.append(f"{pad}  Param {p.name}: {p.type_ref.name}")
        out.extend(_ast_dump(node.body, indent + 1))
        return out
    if isinstance(node, ast.StructDef):
        out = [f"{pad}Struct {node.name}"]
        for f in node.fields:
            out.append(f"{pad}  Field {f.name}: {f.type_ref.name}")
        return out
    if isinstance(node, ast.ImplBlock):
        out = [f"{pad}Impl {node.type_name}"]
        for method in node.methods:
            out.extend(_ast_dump(method, indent + 1))
        return out
    if isinstance(node, ast.ImportDecl):
        alias = f" as {node.alias}" if node.alias else ""
        return [f'{pad}Import "{node.path}"{alias}']
    if isinstance(node, ast.Block):
        out = [f"{pad}Block"]
        for s in node.stmts:
            out.extend(_ast_dump(s, indent + 1))
        return out
    if isinstance(node, ast.LetStmt):
        return [f"{pad}Let {node.name}"]
    if isinstance(node, ast.AssignStmt):
        target = node.target.name if isinstance(node.target, ast.NameExpr) else _expr_label(node.target)
        return [f"{pad}Assign {target}"]
    if isinstance(node, ast.ReturnStmt):
        return [f"{pad}Return"]
    if isinstance(node, ast.IfStmt):
        out = [f"{pad}If"]
        out.extend(_ast_dump(node.then_block, indent + 1))
        if node.else_block:
            out.extend(_ast_dump(node.else_block, indent + 1))
        return out
    if isinstance(node, ast.WhileStmt):
        out = [f"{pad}While"]
        out.extend(_ast_dump(node.body, indent + 1))
        return out
    if isinstance(node, ast.ExprStmt):
        return [f"{pad}ExprStmt"]
    return [f"{pad}{type(node).__name__}"]


def _expr_label(node: object) -> str:
    if isinstance(node, ast.FieldAccess):
        return f"{_expr_label(node.base)}.{node.field}"
    if isinstance(node, ast.NameExpr):
        return node.name
    if isinstance(node, ast.StructLit):
        return node.name
    if isinstance(node, ast.IndexExpr):
        return f"{_expr_label(node.base)}[]"
    if isinstance(node, ast.ArrayLit):
        return "ArrayLit"
    return type(node).__name__


def _hir_lines(hir_mod) -> list[str]:
    lines: list[str] = []
    if hir_mod is None:
        return lines
    for fn in hir_mod.functions:
        lines.append(f"{fn.name}:")
        for idx, i in enumerate(fn.instrs, 1):
            args = ", ".join(i.args)
            lines.append(f"  {idx:03d}: ({i.kind.name}, op={i.op}, args=[{args}], dst={i.dst}, target={i.target}, ty={i.ty}) @{i.span[0]}:{i.span[1]}")
    return lines


def _hir_instr_text(ins: HIRInstr) -> str:
    args = ", ".join(ins.args)
    return f"{ins.kind.name} op={ins.op} args=[{args}] dst={ins.dst} target={ins.target} ty={ins.ty}"


def _hir_structured(hir_mod: HIRModule | None) -> list[dict]:
    rows: list[dict] = []
    if hir_mod is None:
        return rows
    for fn in hir_mod.functions:
        for idx, ins in enumerate(fn.instrs, 1):
            rows.append(
                {
                    "fn": fn.name,
                    "index": idx,
                    "kind": ins.kind.name,
                    "op": ins.op,
                    "args": list(ins.args),
                    "dst": ins.dst,
                    "target": ins.target,
                    "ty": ins.ty,
                    "line": ins.span[0],
                    "col": ins.span[1],
                    "text": _hir_instr_text(ins),
                }
            )
    return rows


def _token_rows(tokens: list[Token]) -> list[dict]:
    return [
        {
            "kind": t.kind.name,
            "lexeme": t.lexeme,
            "line": t.span.line,
            "col": t.span.col,
        }
        for t in tokens
    ]


def _symbol_rows(sema: SemanticResult) -> list[dict]:
    return [
        {"name": n, "category": c, "type": t, "scope": sid, "slot": slot}
        for n, c, t, sid, slot in sema.symbols.dump_rows()
    ]


def _cfg_dump(fn: MIRFunction) -> list[str]:
    rows = []
    for b in fn.order:
        if b not in fn.blocks:
            continue
        blk = fn.blocks[b]
        if not blk.instrs and not blk.preds and not blk.succs and b != "entry":
            continue
        rows.append(f"[{b}] preds={sorted(blk.preds)} succs={sorted(blk.succs)}")
        for i in blk.instrs:
            rows.append(f"  {i.kind.name} op={i.op} args={i.args} target={i.target} -> {i.dst}")
    return rows


def _cfg_structured(mir_mod: MIRModule) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for fn in mir_mod.functions:
        blocks = []
        edges = []
        for idx, name in enumerate(fn.order):
            block = fn.blocks.get(name)
            if block is None:
                continue
            if not block.instrs and not block.preds and not block.succs and name != "entry":
                continue
            blocks.append(
                {
                    "id": name,
                    "instrs": [
                        f"{ins.kind.name} op={ins.op} args={ins.args} target={ins.target} -> {ins.dst}"
                        for ins in block.instrs
                    ],
                }
            )
            branch = next((ins for ins in reversed(block.instrs) if ins.kind in {HIRKind.BRANCH_TRUE, HIRKind.BRANCH_READY}), None)
            jump = next((ins for ins in reversed(block.instrs) if ins.kind == HIRKind.JUMP), None)
            if branch and branch.target:
                edges.append({"from": name, "to": branch.target, "label": "true"})
                fall = next((s for s in fn.order[idx + 1 :] if s in block.succs and s != branch.target), None)
                if fall:
                    edges.append({"from": name, "to": fall, "label": "false"})
            elif jump and jump.target:
                edges.append({"from": name, "to": jump.target, "label": "jump"})
            else:
                for succ in sorted(block.succs):
                    edges.append({"from": name, "to": succ, "label": ""})
        out[fn.name] = {"blocks": blocks, "edges": edges}
    return out


def _notify_stage(callback: Callable[[StageResult], object] | None, result: StageResult) -> None:
    if callback is None:
        return
    maybe_awaitable = callback(result)
    if inspect.isawaitable(maybe_awaitable):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(maybe_awaitable)
        else:
            loop.create_task(maybe_awaitable)


def _suggestions(diag: DiagnosticBag) -> None:
    for d in diag.items:
        if "缺少分号" in d.message and not d.fixits:
            d.fixits.append("在此处插入 ';'")
        if "未声明" in d.message and not d.fixits:
            d.fixits.append("先使用 let 声明该变量")


def _module_name_for_path(path: Path) -> str:
    chars = [ch if ch.isalnum() or ch == "_" else "_" for ch in path.stem]
    name = "".join(chars).strip("_")
    return name or "module"


def _collect_local_function_names(module: ast.Module) -> set[str]:
    return {item.name for item in module.items if isinstance(item, ast.Function)}


def _public_function_names(module: ast.Module) -> set[str]:
    return {item.name for item in module.items if isinstance(item, ast.Function) and item.is_public}


def _import_alias(import_decl: ast.ImportDecl, parent: Path) -> str:
    if import_decl.alias:
        return import_decl.alias
    return _module_name_for_path((parent / import_decl.path).resolve())


def _rewrite_qualified_call_names_in_expr(expr: ast.Expr | None, modules: dict[str, dict[str, str]]) -> None:
    if expr is None:
        return
    if isinstance(expr, ast.CallExpr):
        if (
            isinstance(expr.callee, ast.FieldAccess)
            and isinstance(expr.callee.base, ast.NameExpr)
            and expr.callee.base.name in modules
            and expr.callee.field in modules[expr.callee.base.name]
        ):
            expr.callee = ast.NameExpr(expr.callee.span, None, modules[expr.callee.base.name][expr.callee.field])
        else:
            _rewrite_qualified_call_names_in_expr(expr.callee, modules)
        for arg in expr.args:
            _rewrite_qualified_call_names_in_expr(arg, modules)
    elif isinstance(expr, ast.UnaryExpr):
        _rewrite_qualified_call_names_in_expr(expr.rhs, modules)
    elif isinstance(expr, ast.BinaryExpr):
        _rewrite_qualified_call_names_in_expr(expr.lhs, modules)
        _rewrite_qualified_call_names_in_expr(expr.rhs, modules)
    elif isinstance(expr, ast.StructLit):
        for field in expr.fields:
            _rewrite_qualified_call_names_in_expr(field.value, modules)
    elif isinstance(expr, ast.FieldAccess):
        _rewrite_qualified_call_names_in_expr(expr.base, modules)
    elif isinstance(expr, ast.ArrayLit):
        for item in expr.items:
            _rewrite_qualified_call_names_in_expr(item, modules)
    elif isinstance(expr, ast.IndexExpr):
        _rewrite_qualified_call_names_in_expr(expr.base, modules)
        _rewrite_qualified_call_names_in_expr(expr.index, modules)
    elif isinstance(expr, ast.BlockExpr) and expr.block:
        _rewrite_qualified_call_names_in_block(expr.block, modules)
    elif isinstance(expr, ast.SelectExpr):
        for case in expr.cases:
            _rewrite_qualified_call_names_in_expr(case.channel, modules)
            _rewrite_qualified_call_names_in_expr(case.value, modules)
            _rewrite_qualified_call_names_in_block(case.body, modules)


def _rewrite_qualified_call_names_in_stmt(stmt: ast.Stmt, modules: dict[str, dict[str, str]]) -> None:
    if isinstance(stmt, ast.LetStmt):
        _rewrite_qualified_call_names_in_expr(stmt.value, modules)
    elif isinstance(stmt, ast.AssignStmt):
        _rewrite_qualified_call_names_in_expr(stmt.target, modules)
        _rewrite_qualified_call_names_in_expr(stmt.value, modules)
    elif isinstance(stmt, ast.ExprStmt):
        _rewrite_qualified_call_names_in_expr(stmt.expr, modules)
    elif isinstance(stmt, ast.ReturnStmt):
        _rewrite_qualified_call_names_in_expr(stmt.value, modules)
    elif isinstance(stmt, ast.IfStmt):
        _rewrite_qualified_call_names_in_expr(stmt.cond, modules)
        _rewrite_qualified_call_names_in_block(stmt.then_block, modules)
        if stmt.else_block:
            _rewrite_qualified_call_names_in_block(stmt.else_block, modules)
    elif isinstance(stmt, ast.WhileStmt):
        _rewrite_qualified_call_names_in_expr(stmt.cond, modules)
        _rewrite_qualified_call_names_in_block(stmt.body, modules)
    elif isinstance(stmt, ast.SpawnStmt):
        _rewrite_qualified_call_names_in_expr(stmt.expr, modules)
    elif isinstance(stmt, ast.Block):
        _rewrite_qualified_call_names_in_block(stmt, modules)


def _rewrite_qualified_call_names_in_block(block: ast.Block, modules: dict[str, dict[str, str]]) -> None:
    for stmt in block.stmts:
        _rewrite_qualified_call_names_in_stmt(stmt, modules)


def _rewrite_call_names_in_expr(expr: ast.Expr | None, rename: dict[str, str]) -> None:
    if expr is None:
        return
    if isinstance(expr, ast.CallExpr):
        if isinstance(expr.callee, ast.NameExpr) and expr.callee.name in rename:
            expr.callee.name = rename[expr.callee.name]
        _rewrite_call_names_in_expr(expr.callee, rename)
        for arg in expr.args:
            _rewrite_call_names_in_expr(arg, rename)
    elif isinstance(expr, ast.UnaryExpr):
        _rewrite_call_names_in_expr(expr.rhs, rename)
    elif isinstance(expr, ast.BinaryExpr):
        _rewrite_call_names_in_expr(expr.lhs, rename)
        _rewrite_call_names_in_expr(expr.rhs, rename)
    elif isinstance(expr, ast.StructLit):
        for field in expr.fields:
            _rewrite_call_names_in_expr(field.value, rename)
    elif isinstance(expr, ast.FieldAccess):
        _rewrite_call_names_in_expr(expr.base, rename)
    elif isinstance(expr, ast.ArrayLit):
        for item in expr.items:
            _rewrite_call_names_in_expr(item, rename)
    elif isinstance(expr, ast.IndexExpr):
        _rewrite_call_names_in_expr(expr.base, rename)
        _rewrite_call_names_in_expr(expr.index, rename)
    elif isinstance(expr, ast.BlockExpr) and expr.block:
        _rewrite_call_names_in_block(expr.block, rename)
    elif isinstance(expr, ast.SelectExpr):
        for case in expr.cases:
            _rewrite_call_names_in_expr(case.channel, rename)
            _rewrite_call_names_in_expr(case.value, rename)
            _rewrite_call_names_in_block(case.body, rename)


def _rewrite_call_names_in_stmt(stmt: ast.Stmt, rename: dict[str, str]) -> None:
    if isinstance(stmt, ast.LetStmt):
        _rewrite_call_names_in_expr(stmt.value, rename)
    elif isinstance(stmt, ast.AssignStmt):
        _rewrite_call_names_in_expr(stmt.target, rename)
        _rewrite_call_names_in_expr(stmt.value, rename)
    elif isinstance(stmt, ast.ExprStmt):
        _rewrite_call_names_in_expr(stmt.expr, rename)
    elif isinstance(stmt, ast.ReturnStmt):
        _rewrite_call_names_in_expr(stmt.value, rename)
    elif isinstance(stmt, ast.IfStmt):
        _rewrite_call_names_in_expr(stmt.cond, rename)
        _rewrite_call_names_in_block(stmt.then_block, rename)
        if stmt.else_block:
            _rewrite_call_names_in_block(stmt.else_block, rename)
    elif isinstance(stmt, ast.WhileStmt):
        _rewrite_call_names_in_expr(stmt.cond, rename)
        _rewrite_call_names_in_block(stmt.body, rename)
    elif isinstance(stmt, ast.SpawnStmt):
        _rewrite_call_names_in_expr(stmt.expr, rename)
    elif isinstance(stmt, ast.Block):
        _rewrite_call_names_in_block(stmt, rename)


def _rewrite_call_names_in_block(block: ast.Block, rename: dict[str, str]) -> None:
    for stmt in block.stmts:
        _rewrite_call_names_in_stmt(stmt, rename)


def _flatten_impls(module: ast.Module) -> ast.Module:
    items: list[object] = []
    for item in module.items:
        if isinstance(item, ast.ImplBlock):
            rename = {method.name: f"{item.type_name}__{method.name}" for method in item.methods}
            for method in item.methods:
                method.name = rename[method.name]
                _rewrite_call_names_in_block(method.body, rename)
                items.append(method)
        else:
            items.append(item)
    module.items = items
    return module


def _rename_module_functions(module: ast.Module, module_name: str, keep_main: bool) -> dict[str, str]:
    rename: dict[str, str] = {}
    for item in module.items:
        if isinstance(item, ast.Function) and (item.name != "main" or not keep_main):
            rename[item.name] = f"{module_name}__{item.name}"
    for item in module.items:
        if isinstance(item, ast.Function):
            if item.name in rename:
                item.name = rename[item.name]
            _rewrite_call_names_in_block(item.body, rename)
    return rename


def _parse_source_to_module(source: str, diag: DiagnosticBag) -> ast.Module:
    tokens = Lexer(source, diag).scan()
    return Parser(tokens, diag).parse()


def _resolve_imports(module: ast.Module, base_path: Path | None, diag: DiagnosticBag) -> ast.Module:
    imported_items: list[object] = []
    imported_renames: dict[str, str] = {}
    seen: set[Path] = set()
    loaded_symbols: dict[Path, dict[str, str]] = {}

    def load_import(path_text: str, parent: Path) -> dict[str, str]:
        imp_path = (parent / path_text).resolve()
        if imp_path in loaded_symbols:
            return loaded_symbols[imp_path]
        seen.add(imp_path)
        if not imp_path.exists():
            diag.error(Span(0, 0, 1, 1), f"import 文件不存在: {imp_path}")
            loaded_symbols[imp_path] = {}
            return {}
        try:
            imp_source = imp_path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            diag.error(Span(0, 0, 1, 1), f"import 文件读取失败: {imp_path}: {exc}")
            loaded_symbols[imp_path] = {}
            return {}
        imp_module = _parse_source_to_module(imp_source, diag)
        imp_module = _flatten_impls(imp_module)
        nested_modules: dict[str, dict[str, str]] = {}
        nested_visible: dict[str, str] = {}
        for item in list(imp_module.items):
            if isinstance(item, ast.ImportDecl):
                nested_symbols = load_import(item.path, imp_path.parent)
                nested_modules[_import_alias(item, imp_path.parent)] = nested_symbols
                for original, mangled in nested_symbols.items():
                    nested_visible.setdefault(original, mangled)
        local_names = _collect_local_function_names(imp_module)
        for item in imp_module.items:
            if isinstance(item, ast.Function):
                _rewrite_qualified_call_names_in_block(item.body, nested_modules)
                _rewrite_call_names_in_block(item.body, {k: v for k, v in nested_visible.items() if k not in local_names})
        public_names = _public_function_names(imp_module)
        local_rename = _rename_module_functions(imp_module, _module_name_for_path(imp_path), keep_main=False)
        public_rename = {name: mangled for name, mangled in local_rename.items() if name in public_names}
        for original, mangled in local_rename.items():
            if original in imported_renames and imported_renames[original] != mangled:
                diag.error(Span(0, 0, 1, 1), f"import 函数名冲突: {original}")
            else:
                if original in public_rename:
                    imported_renames[original] = mangled
        imported_items.extend(item for item in imp_module.items if not isinstance(item, ast.ImportDecl))
        loaded_symbols[imp_path] = public_rename
        return public_rename

    imports = [item for item in module.items if isinstance(item, ast.ImportDecl)]
    if not imports:
        return module
    import_modules: dict[str, dict[str, str]] = {}
    if imports:
        if base_path is None:
            diag.error(imports[0].span, "当前编译入口没有文件路径，无法解析 import")
        else:
            for item in imports:
                import_modules[_import_alias(item, base_path.parent)] = load_import(item.path, base_path.parent)

    entry_name = _module_name_for_path(base_path) if base_path else "main"
    local_names = _collect_local_function_names(module)
    visible_imports = {k: v for k, v in imported_renames.items() if k not in local_names}
    for item in module.items:
        if isinstance(item, ast.Function):
            _rewrite_qualified_call_names_in_block(item.body, import_modules)
            _rewrite_call_names_in_block(item.body, visible_imports)
    _rename_module_functions(module, entry_name, keep_main=True)
    own_items = [item for item in module.items if not isinstance(item, ast.ImportDecl)]
    return ast.Module(module.span, imported_items + own_items)


def compile_source(
    source: str,
    mode: str = "full",
    export_dir: str | None = None,
    run: bool = False,
    trace: bool = False,
    on_stage: Callable[[StageResult], object] | None = None,
    build: bool = False,
    build_dir: str | None = None,
    source_stem: str = "program",
    run_exe: bool = False,
    source_path: str | None = None,
) -> BuildResult:
    diag = DiagnosticBag()
    timeline: list[StageResult] = []
    artifacts = BuildArtifacts()

    def stage(name: str, status: str, detail: str) -> None:
        result = StageResult(name, status, detail)
        timeline.append(result)
        _notify_stage(on_stage, result)

    lexer = Lexer(source, diag)
    tokens = lexer.scan()
    artifacts.tokens = [f"{t.kind.name}:{t.lexeme}" for t in tokens]
    artifacts.token_rows = _token_rows(tokens)
    stage("Lexer", "failed" if diag.has_errors() else "ok", f"tokens={len(tokens)}")
    if diag.has_errors():
        stage("Parser", "skipped", "blocked by lexer errors")
        stage("MacroExpand", "skipped", "blocked")
        stage("Sema", "skipped", "blocked")
        stage("Monomorphize", "skipped", "blocked")
        stage("Sema(redo)", "skipped", "blocked")
        stage("HIR", "skipped", "blocked")
        stage("Optimize", "skipped", "blocked")
        stage("MIR", "skipped", "blocked")
        stage("RegAlloc", "skipped", "blocked")
        stage("Backend", "skipped", "blocked")
        _suggestions(diag)
        return BuildResult(diagnostics=diag.items, artifacts=artifacts, timeline=timeline)

    parser = Parser(tokens, diag)
    module = parser.parse()
    module = _flatten_impls(module)
    module = _resolve_imports(module, Path(source_path).resolve() if source_path else None, diag)
    artifacts.ast_text = "\n".join(_ast_dump(module))
    stage("Parser", "failed" if diag.has_errors() else "ok", f"items={len(module.items)}")
    if diag.has_errors():
        stage("MacroExpand", "skipped", "blocked by parser errors")
        stage("Sema", "skipped", "blocked")
        stage("Monomorphize", "skipped", "blocked")
        stage("Sema(redo)", "skipped", "blocked")
        stage("HIR", "skipped", "blocked")
        stage("Optimize", "skipped", "blocked")
        stage("MIR", "skipped", "blocked")
        stage("RegAlloc", "skipped", "blocked")
        stage("Backend", "skipped", "blocked")
        _suggestions(diag)
        return BuildResult(diagnostics=diag.items, artifacts=artifacts, timeline=timeline)

    if mode == "full":
        module = MacroExpander(diag).expand_module(module)
    stage("MacroExpand", "failed" if diag.has_errors() else "ok", "enabled" if mode == "full" else "core-mode disabled")
    artifacts.ast_text = "\n".join(_ast_dump(module))

    sema_pre: SemanticResult = Checker(diag, mode=mode).analyze(module)
    stage("Sema", "failed" if diag.has_errors() else "ok", f"symbols={len(sema_pre.symbols.history)}")
    if diag.has_errors():
        stage("Monomorphize", "skipped", "blocked by sema errors")
        stage("Sema(redo)", "skipped", "blocked")
        stage("HIR", "skipped", "blocked")
        stage("Optimize", "skipped", "blocked")
        stage("MIR", "skipped", "blocked")
        stage("RegAlloc", "skipped", "blocked")
        stage("Backend", "skipped", "blocked")
        artifacts.tables = _format_tables(lexer.tables, sema_pre, [])
        artifacts.symbols = [f"{n:<12} {c:<8} {t:<12} scope={sid} slot={slot}" for n, c, t, sid, slot in sema_pre.symbols.dump_rows()]
        artifacts.symbol_rows = _symbol_rows(sema_pre)
        _suggestions(diag)
        return BuildResult(diagnostics=diag.items, artifacts=artifacts, timeline=timeline)

    if mode == "full":
        module = monomorphize(module, sema_pre.generic_calls)
    stage("Monomorphize", "failed" if diag.has_errors() else "ok", "enabled" if mode == "full" else "core-mode disabled")

    # Re-run semantic analysis after monomorphization so cloned functions get proper concrete typing.
    sema: SemanticResult = Checker(diag, mode=mode).analyze(module)
    stage("Sema(redo)", "failed" if diag.has_errors() else "ok", f"symbols={len(sema.symbols.history)}")
    if diag.has_errors():
        stage("HIR", "skipped", "blocked by sema errors")
        stage("Optimize", "skipped", "blocked")
        stage("MIR", "skipped", "blocked")
        stage("RegAlloc", "skipped", "blocked")
        stage("Backend", "skipped", "blocked")
        artifacts.tables = _format_tables(lexer.tables, sema, [])
        artifacts.symbols = [f"{n:<12} {c:<8} {t:<12} scope={sid} slot={slot}" for n, c, t, sid, slot in sema.symbols.dump_rows()]
        artifacts.symbol_rows = _symbol_rows(sema)
        _suggestions(diag)
        return BuildResult(diagnostics=diag.items, artifacts=artifacts, timeline=timeline)

    lowerer = Lowerer()
    hir_raw_mod = lowerer.lower_module(module)
    hir_raw_lines = _hir_lines(hir_raw_mod)
    artifacts.hir_raw = hir_raw_mod
    artifacts.hir_raw_structured = _hir_structured(hir_raw_mod)
    stage("HIR", "ok", f"instrs={sum(len(f.instrs) for f in hir_raw_mod.functions)}")

    hir_opt_mod = run_optimizations(hir_raw_mod)
    hir_opt_lines = _hir_lines(hir_opt_mod)
    artifacts.hir_opt = hir_opt_mod
    artifacts.hir_opt_structured = _hir_structured(hir_opt_mod)
    stage("Optimize", "ok", "const-fold + dce")

    ok_llvm, llvm_msg = validate_llvm_subset(hir_opt_mod)
    llvm_ir = emit_llvm_ir(hir_opt_mod) if ok_llvm else ""
    if not ok_llvm:
        diag.warn(Span(0, 0, 1, 1), llvm_msg)
    mir_mod = hir_to_mir(hir_opt_mod)
    stage("MIR", "ok", f"functions={len(mir_mod.functions)}")

    asm: dict[str, str] = {}
    cfg_dump: dict[str, list[str]] = {}
    sigs = _compute_signatures(mir_mod)
    for fn in mir_mod.functions:
        intervals = compute_intervals(fn)
        alloc = linear_scan(intervals, ["rbx", "r12", "r13", "r14", "r15"])
        asm[fn.name] = emit_function(fn, alloc, mir_mod.struct_layouts, sigs)
        cfg_dump[fn.name] = _cfg_dump(fn)
    asm_module_text = emit_module(mir_mod)
    stage("RegAlloc", "ok", "linear-scan")
    stage("Backend", "warning" if not ok_llvm else "ok", f"asm-fns={len(asm)}")

    _suggestions(diag)

    artifacts.tables = _format_tables(lexer.tables, sema, hir_opt_lines)
    artifacts.tables["hir_raw"] = hir_raw_lines
    artifacts.tables["hir_opt"] = hir_opt_lines
    artifacts.symbols = [f"{n:<12} {c:<8} {t:<12} scope={sid} slot={slot}" for n, c, t, sid, slot in sema.symbols.dump_rows()]
    artifacts.symbol_rows = _symbol_rows(sema)
    artifacts.cfg = cfg_dump
    artifacts.cfg_structured = _cfg_structured(mir_mod)
    artifacts.asm = asm
    artifacts.asm_module = asm_module_text
    artifacts.llvm_ir = llvm_ir

    run_value = None
    run_stdout: list[str] = []
    vm_trace: list[VMFrame] = []
    if run and not diag.has_errors():
        try:
            vm = HIRVM(hir_opt_mod)
            if trace:
                vm_res, vm_trace = vm.run_with_trace("main")
            else:
                vm_res = vm.run("main")
            run_value = vm_res.return_value
            run_stdout = vm_res.stdout
        except Exception as exc:  # noqa: BLE001
            run_stdout = [f"runtime error: {exc}"]
            diag.add(Level.ERROR, Span(0, 0, 1, 1), f"运行时错误: {exc}")

    if export_dir:
        _export_graphs(module, mir_mod, export_dir)

    build_output: BuildOutput | None = None
    exe_exit: int | None = None
    exe_out = ""
    exe_err = ""
    if build and not diag.has_errors():
        try:
            build_output = build_module(mir_mod, source_stem, out_dir=build_dir or "out")
            stage("NativeBuild", "ok", f"exe={build_output.exe_path}")
            if run_exe:
                exe_exit, exe_out, exe_err = run_executable(build_output.exe_path)
                stage("NativeRun", "ok" if exe_exit == 0 else "warning", f"exit={exe_exit}")
        except BuildError as exc:
            stage("NativeBuild", "failed", str(exc))
            diag.add(Level.ERROR, Span(0, 0, 1, 1), f"native build error: {exc}")

    return BuildResult(
        diagnostics=diag.items,
        artifacts=artifacts,
        timeline=timeline,
        run_value=run_value,
        run_stdout=run_stdout,
        vm_trace=vm_trace,
        build=build_output,
        exe_exit_code=exe_exit,
        exe_stdout=exe_out,
        exe_stderr=exe_err,
    )


def _format_tables(lt: LexTables, sema: SemanticResult, hir_lines: list[str]) -> dict[str, list[str]]:
    quads = [ln.strip() for ln in hir_lines if "(" in ln and ")" in ln]
    return {
        "keywords": sorted(lt.keyword_table),
        "delimiters": sorted(lt.delimiter_table),
        "identifiers": sorted(lt.identifier_table),
        "constants": sorted(lt.constant_table),
        "symbols": [f"{n}|{c}|{t}|scope={sid}|slot={slot}" for n, c, t, sid, slot in sema.symbols.dump_rows()],
        "quadruples": quads,
    }


def _export_graphs(module: ast.Module, mir_mod, export_dir: str) -> None:
    out = Path(export_dir)
    out.mkdir(parents=True, exist_ok=True)
    # AST DOT
    ast_dot = ["digraph AST {"]
    nid = 0

    def emit(node, parent=None):
        nonlocal nid
        cur = f"n{nid}"; nid += 1
        label = type(node).__name__
        if isinstance(node, ast.Function):
            label += f"\\n{node.name}"
        ast_dot.append(f'{cur} [label="{label}"];')
        if parent:
            ast_dot.append(f"{parent} -> {cur};")
        if isinstance(node, ast.Module):
            for i in node.items:
                emit(i, cur)
        elif isinstance(node, ast.Function):
            emit(node.body, cur)
        elif isinstance(node, ast.Block):
            for s in node.stmts:
                emit(s, cur)
        elif isinstance(node, ast.IfStmt):
            emit(node.then_block, cur)
            if node.else_block:
                emit(node.else_block, cur)
        elif isinstance(node, ast.WhileStmt):
            emit(node.body, cur)

    emit(module)
    ast_dot.append("}")
    (out / "ast.dot").write_text("\n".join(ast_dot), encoding="utf-8")

    for fn in mir_mod.functions:
        lines = ["digraph CFG {"]
        for name, blk in fn.blocks.items():
            if not blk.instrs and not blk.preds and not blk.succs and name != "entry":
                continue
            lines.append(f'{name} [shape=box,label="{name}"];')
            for s in blk.succs:
                if s in fn.blocks:
                    lines.append(f"{name} -> {s};")
        lines.append("}")
        (out / f"cfg_{fn.name}.dot").write_text("\n".join(lines), encoding="utf-8")

    try:
        import graphviz  # type: ignore

        graphviz.Source((out / "ast.dot").read_text(encoding="utf-8")).render((out / "ast"), format="svg", cleanup=True)
        for fn in mir_mod.functions:
            dot = out / f"cfg_{fn.name}.dot"
            graphviz.Source(dot.read_text(encoding="utf-8")).render((out / f"cfg_{fn.name}"), format="svg", cleanup=True)
    except Exception:
        pass
