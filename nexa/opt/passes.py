from __future__ import annotations

from dataclasses import replace
from itertools import count

from nexa.ir.hir import HIRFunction, HIRInstr, HIRKind, HIRModule


_COMMUTATIVE_OPS = {"+", "*", "==", "!=", "&&", "||"}
_PURE_KINDS = {HIRKind.CONST, HIRKind.MOVE, HIRKind.UNARY, HIRKind.BIN}
_CONTROL_KINDS = {HIRKind.LABEL, HIRKind.JUMP, HIRKind.BRANCH_TRUE, HIRKind.BRANCH_READY, HIRKind.RET}
_CRITICAL_KINDS = {
    HIRKind.PARAM,
    HIRKind.ARG,
    HIRKind.CALL,
    HIRKind.RET,
    HIRKind.LABEL,
    HIRKind.JUMP,
    HIRKind.BRANCH_TRUE,
    HIRKind.BRANCH_READY,
    HIRKind.SPAWN,
    HIRKind.FIELD_SET,
    HIRKind.ARRAY_SET,
}


def _is_int_literal(value: str) -> bool:
    return value.isdigit() or (value.startswith("-") and value[1:].isdigit())


def _is_float_literal(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return "." in value or "e" in value.lower()


def _is_literal(value: str) -> bool:
    return _is_int_literal(value) or _is_float_literal(value)


def _is_name(value: str) -> bool:
    return bool(value) and not _is_literal(value) and value not in {"true", "false", "True", "False"}


def _literal_for_type(raw: str, ty: str) -> int | float:
    if ty == "f64" or _is_float_literal(raw):
        return float(raw)
    return int(raw)


def _format_literal(value: int | float | bool, ty: str) -> str:
    if ty == "bool":
        return "1" if bool(value) else "0"
    if ty == "f64":
        return repr(float(value))
    return str(int(value))


def _const_instr(dst: str, value: int | float | bool, ty: str, span: tuple[int, int] = (0, 0)) -> HIRInstr:
    return HIRInstr(HIRKind.CONST, dst=dst, args=[_format_literal(value, ty)], ty=ty, span=span)


def _resolve_alias(name: str, aliases: dict[str, str]) -> str:
    seen: set[str] = set()
    while name in aliases and name not in seen:
        seen.add(name)
        name = aliases[name]
    return name


def _rewrite_args(args: list[str], aliases: dict[str, str], constants: dict[str, tuple[str, str]]) -> list[str]:
    out: list[str] = []
    for arg in args:
        resolved = _resolve_alias(arg, aliases) if _is_name(arg) else arg
        if resolved in constants:
            out.append(constants[resolved][0])
        else:
            out.append(resolved)
    return out


def _clobber(dst: str | None, aliases: dict[str, str], constants: dict[str, tuple[str, str]]) -> None:
    if not dst:
        return
    aliases.pop(dst, None)
    constants.pop(dst, None)
    for name, value in list(aliases.items()):
        if value == dst:
            aliases.pop(name, None)


def propagate_constants_and_copies(fn: HIRFunction) -> None:
    """Forward local propagation within straight-line regions."""
    aliases: dict[str, str] = {}
    constants: dict[str, tuple[str, str]] = {}
    out: list[HIRInstr] = []

    for ins in fn.instrs:
        if ins.kind == HIRKind.LABEL:
            aliases.clear()
            constants.clear()

        if ins.kind == HIRKind.MOVE and ins.dst and not (ins.dst.startswith("t") or ins.dst.startswith("__inl")):
            args = [_resolve_alias(arg, aliases) if _is_name(arg) else arg for arg in ins.args]
        else:
            args = _rewrite_args(ins.args, aliases, constants)
        new = replace(ins, args=args)

        if new.kind == HIRKind.CONST and new.dst and new.args:
            _clobber(new.dst, aliases, constants)
            if new.ty in {"i32", "i64", "bool", "f64"} and _is_literal(new.args[0]):
                constants[new.dst] = (new.args[0], new.ty)
        elif new.kind == HIRKind.MOVE and new.dst and new.args:
            src = new.args[0]
            _clobber(new.dst, aliases, constants)
            if _is_literal(src):
                if new.dst.startswith("t") or new.dst.startswith("__inl"):
                    new = HIRInstr(HIRKind.CONST, dst=new.dst, args=[src], ty=new.ty, span=new.span)
                constants[new.dst] = (src, new.ty)
            elif _is_name(src):
                aliases[new.dst] = src
        elif new.dst:
            _clobber(new.dst, aliases, constants)

        out.append(new)
        if ins.kind in _CONTROL_KINDS or ins.kind in {HIRKind.CALL, HIRKind.ARRAY_SET, HIRKind.FIELD_SET, HIRKind.SPAWN}:
            aliases.clear()
            constants.clear()

    fn.instrs = out


def _fold_binary(op: str, left: str, right: str, ty: str) -> tuple[int | float | bool, str] | None:
    if not (_is_literal(left) and _is_literal(right)):
        return None
    # Keep f64 arithmetic visible for the native SSE backend and report output.
    if ty == "f64":
        return None
    a = _literal_for_type(left, ty)
    b = _literal_for_type(right, ty)
    try:
        if op == "+":
            return a + b, ty
        if op == "-":
            return a - b, ty
        if op == "*":
            return a * b, ty
        if op == "/" and b != 0:
            return (float(a) / float(b), "f64") if ty == "f64" else (int(a) // int(b), ty)
        if op == "%" and b != 0 and ty != "f64":
            return int(a) % int(b), ty
        if op == "==":
            return a == b, "bool"
        if op == "!=":
            return a != b, "bool"
        if op == "<":
            return a < b, "bool"
        if op == "<=":
            return a <= b, "bool"
        if op == ">":
            return a > b, "bool"
        if op == ">=":
            return a >= b, "bool"
        if op == "&&":
            return bool(a) and bool(b), "bool"
        if op == "||":
            return bool(a) or bool(b), "bool"
    except Exception:
        return None
    return None


def _simplify_binary(ins: HIRInstr) -> HIRInstr:
    if not ins.dst or len(ins.args) != 2:
        return ins
    op = ins.op or ""
    a, b = ins.args
    folded = _fold_binary(op, a, b, ins.ty)
    if folded is not None:
        value, ty = folded
        return _const_instr(ins.dst, value, ty, ins.span)

    if ins.ty == "f64":
        return ins

    if op == "+":
        if b == "0":
            return HIRInstr(HIRKind.MOVE, dst=ins.dst, args=[a], ty=ins.ty, span=ins.span)
        if a == "0":
            return HIRInstr(HIRKind.MOVE, dst=ins.dst, args=[b], ty=ins.ty, span=ins.span)
    elif op == "-":
        if b == "0":
            return HIRInstr(HIRKind.MOVE, dst=ins.dst, args=[a], ty=ins.ty, span=ins.span)
    elif op == "*":
        if a == "0" or b == "0":
            return _const_instr(ins.dst, 0, ins.ty, ins.span)
        if b == "1":
            return HIRInstr(HIRKind.MOVE, dst=ins.dst, args=[a], ty=ins.ty, span=ins.span)
        if a == "1":
            return HIRInstr(HIRKind.MOVE, dst=ins.dst, args=[b], ty=ins.ty, span=ins.span)
        if b == "2":
            return HIRInstr(HIRKind.BIN, dst=ins.dst, args=[a, a], op="+", ty=ins.ty, span=ins.span)
        if a == "2":
            return HIRInstr(HIRKind.BIN, dst=ins.dst, args=[b, b], op="+", ty=ins.ty, span=ins.span)
    elif op == "/":
        if b == "1":
            return HIRInstr(HIRKind.MOVE, dst=ins.dst, args=[a], ty=ins.ty, span=ins.span)
    elif op == "&&":
        if a == "0" or b == "0":
            return _const_instr(ins.dst, 0, "bool", ins.span)
        if a == "1":
            return HIRInstr(HIRKind.MOVE, dst=ins.dst, args=[b], ty="bool", span=ins.span)
        if b == "1":
            return HIRInstr(HIRKind.MOVE, dst=ins.dst, args=[a], ty="bool", span=ins.span)
    elif op == "||":
        if a == "1" or b == "1":
            return _const_instr(ins.dst, 1, "bool", ins.span)
        if a == "0":
            return HIRInstr(HIRKind.MOVE, dst=ins.dst, args=[b], ty="bool", span=ins.span)
        if b == "0":
            return HIRInstr(HIRKind.MOVE, dst=ins.dst, args=[a], ty="bool", span=ins.span)
    return ins


def const_fold_and_algebra(fn: HIRFunction) -> None:
    out: list[HIRInstr] = []
    for ins in fn.instrs:
        if ins.kind == HIRKind.UNARY and ins.dst and ins.args and _is_literal(ins.args[0]):
            value = _literal_for_type(ins.args[0], ins.ty)
            if ins.op == "-":
                out.append(_const_instr(ins.dst, -value, ins.ty, ins.span))
            elif ins.op == "!":
                out.append(_const_instr(ins.dst, not bool(value), "bool", ins.span))
            else:
                out.append(ins)
        elif ins.kind == HIRKind.BIN:
            out.append(_simplify_binary(ins))
        else:
            out.append(ins)
    fn.instrs = out


def common_subexpression_elimination(fn: HIRFunction) -> None:
    exprs: dict[tuple[object, ...], str] = {}
    out: list[HIRInstr] = []

    def kill(name: str | None) -> None:
        if not name:
            return
        for key, dst in list(exprs.items()):
            if dst == name or name in key:
                exprs.pop(key, None)

    for ins in fn.instrs:
        if ins.kind in _CONTROL_KINDS or ins.kind in {HIRKind.CALL, HIRKind.FIELD_SET, HIRKind.ARRAY_SET, HIRKind.SPAWN}:
            exprs.clear()
            out.append(ins)
            continue

        if ins.kind in {HIRKind.UNARY, HIRKind.BIN} and ins.dst:
            args = tuple(ins.args)
            if ins.kind == HIRKind.BIN and (ins.op or "") in _COMMUTATIVE_OPS:
                args = tuple(sorted(args))
            key = (ins.kind, ins.op, args, ins.ty)
            if key in exprs:
                out.append(HIRInstr(HIRKind.MOVE, dst=ins.dst, args=[exprs[key]], ty=ins.ty, span=ins.span))
                continue
            kill(ins.dst)
            exprs[key] = ins.dst
            out.append(ins)
        else:
            kill(ins.dst)
            out.append(ins)
    fn.instrs = out


def _loop_ranges(instrs: list[HIRInstr]) -> list[tuple[int, int, str]]:
    labels: dict[str, int] = {}
    for idx, ins in enumerate(instrs):
        if ins.kind == HIRKind.LABEL and ins.target:
            labels[ins.target] = idx
    ranges: list[tuple[int, int, str]] = []
    for idx, ins in enumerate(instrs):
        if ins.kind == HIRKind.JUMP and ins.target in labels and labels[ins.target] < idx:
            ranges.append((labels[ins.target], idx, ins.target))
    return ranges


def _safe_to_hoist(ins: HIRInstr) -> bool:
    if not ins.dst or not ins.dst.startswith("t"):
        return False
    if ins.kind == HIRKind.CONST:
        return True
    if ins.kind == HIRKind.UNARY:
        return True
    if ins.kind == HIRKind.BIN:
        return (ins.op or "") not in {"/", "%"}
    return False


def loop_invariant_code_motion(fn: HIRFunction) -> None:
    instrs = list(fn.instrs)
    for start, end, _target in reversed(_loop_ranges(instrs)):
        body_indexes = range(start + 1, end)
        assigned = {ins.dst for ins in instrs[start + 1 : end] if ins.dst}
        moved_defs: set[str] = set()
        movable: list[int] = []
        for idx in body_indexes:
            ins = instrs[idx]
            if not _safe_to_hoist(ins):
                continue
            args = [a for a in ins.args if _is_name(a)]
            if all(arg not in assigned or arg in moved_defs for arg in args):
                movable.append(idx)
                if ins.dst:
                    moved_defs.add(ins.dst)
        if not movable:
            continue
        moved = [instrs[idx] for idx in movable]
        movable_set = set(movable)
        instrs = instrs[:start] + moved + [ins for idx, ins in enumerate(instrs[start: end + 1], start) if idx not in movable_set] + instrs[end + 1 :]
    fn.instrs = instrs


def dead_code_elimination(fn: HIRFunction) -> None:
    live: set[str] = set()
    kept: list[HIRInstr] = []
    dst_counts: dict[str, int] = {}
    for ins in fn.instrs:
        if ins.dst:
            dst_counts[ins.dst] = dst_counts.get(ins.dst, 0) + 1
    for ins in reversed(fn.instrs):
        critical = ins.kind in _CRITICAL_KINDS or ins.kind not in _PURE_KINDS
        removable_dst = bool(ins.dst and (ins.dst.startswith("t") or ins.dst.startswith("__inl")))
        branch_join_store = bool(ins.dst and dst_counts.get(ins.dst, 0) > 1)
        needed = critical or branch_join_store or not removable_dst or bool(ins.dst and ins.dst in live)
        if needed:
            kept.append(ins)
            if ins.dst:
                live.discard(ins.dst)
            live.update(arg for arg in ins.args if _is_name(arg))
        elif ins.dst:
            live.discard(ins.dst)
    fn.instrs = list(reversed(kept))


def remove_unreachable(fn: HIRFunction) -> None:
    out: list[HIRInstr] = []
    reachable = True
    referenced = {ins.target for ins in fn.instrs if ins.target}
    for ins in fn.instrs:
        if ins.kind == HIRKind.LABEL:
            reachable = ins.target in referenced
        if reachable:
            out.append(ins)
        if ins.kind in {HIRKind.JUMP, HIRKind.RET}:
            reachable = False
    fn.instrs = out


def _simple_inline_candidates(mod: HIRModule) -> dict[str, HIRFunction]:
    allowed = {HIRKind.PARAM, HIRKind.CONST, HIRKind.MOVE, HIRKind.UNARY, HIRKind.BIN, HIRKind.RET}
    out: dict[str, HIRFunction] = {}
    for fn in mod.functions:
        if fn.name == "main" or len(fn.instrs) > 16:
            continue
        if all(ins.kind in allowed for ins in fn.instrs) and any(ins.kind == HIRKind.RET for ins in fn.instrs):
            out[fn.name] = fn
    return out


def inline_small_functions(mod: HIRModule) -> None:
    candidates = _simple_inline_candidates(mod)
    serial = count(1)
    for fn in mod.functions:
        if not candidates:
            return
        out: list[HIRInstr] = []
        pending_args: list[str] = []
        for ins in fn.instrs:
            if ins.kind == HIRKind.ARG and ins.args:
                pending_args.append(ins.args[0])
                out.append(ins)
                continue
            if ins.kind == HIRKind.CALL and ins.op in candidates and ins.dst:
                callee = candidates[ins.op]
                params = [i.dst for i in callee.instrs if i.kind == HIRKind.PARAM and i.dst]
                if len(params) == len(pending_args):
                    for _ in pending_args:
                        out.pop()
                    prefix = f"__inl{next(serial)}_{ins.op}_"
                    names = dict(zip(params, pending_args, strict=False))

                    def mapped(name: str) -> str:
                        if name in names:
                            return names[name]
                        if _is_literal(name):
                            return name
                        if name not in names:
                            names[name] = prefix + name
                        return names[name]

                    for cin in callee.instrs:
                        if cin.kind == HIRKind.PARAM:
                            continue
                        if cin.kind == HIRKind.RET:
                            src = mapped(cin.args[0]) if cin.args else "0"
                            out.append(HIRInstr(HIRKind.MOVE, dst=ins.dst, args=[src], ty=ins.ty, span=ins.span))
                            break
                        out.append(
                            HIRInstr(
                                cin.kind,
                                dst=mapped(cin.dst) if cin.dst else None,
                                args=[mapped(a) for a in cin.args],
                                ty=cin.ty,
                                op=cin.op,
                                target=cin.target,
                                span=ins.span,
                            )
                        )
                    pending_args.clear()
                    continue
            pending_args.clear()
            out.append(ins)
        fn.instrs = out


def optimize_function(fn: HIRFunction) -> None:
    for _ in range(3):
        before = [(i.kind, i.dst, tuple(i.args), i.op, i.target, i.ty) for i in fn.instrs]
        propagate_constants_and_copies(fn)
        const_fold_and_algebra(fn)
        common_subexpression_elimination(fn)
        loop_invariant_code_motion(fn)
        dead_code_elimination(fn)
        remove_unreachable(fn)
        after = [(i.kind, i.dst, tuple(i.args), i.op, i.target, i.ty) for i in fn.instrs]
        if after == before:
            break


def run_optimizations(mod: HIRModule) -> HIRModule:
    inline_small_functions(mod)
    for fn in mod.functions:
        optimize_function(fn)
    return mod
