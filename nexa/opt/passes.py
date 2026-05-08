from __future__ import annotations

from nexa.ir.hir import HIRFunction, HIRInstr, HIRKind, HIRModule


_PURE = {
    HIRKind.CONST,
    HIRKind.BIN,
    HIRKind.UNARY,
    HIRKind.MOVE,
    HIRKind.ARRAY_NEW,
    HIRKind.ARRAY_GET,
    HIRKind.STRUCT_NEW,
    HIRKind.FIELD_GET,
    HIRKind.ENUM_NEW,
    HIRKind.ENUM_TAG,
    HIRKind.ENUM_GET,
    HIRKind.CLOSURE,
    HIRKind.TO_STR,
    HIRKind.DICT_NEW,
    HIRKind.DICT_GET,
    HIRKind.RANGE_NEW,
    HIRKind.ARRAY_SLICE,
}

_ROOTS = {
    HIRKind.PARAM,
    HIRKind.ARG,
    HIRKind.CALL,
    HIRKind.RET,
    HIRKind.BRANCH_TRUE,
    HIRKind.BRANCH_READY,
    HIRKind.JUMP,
    HIRKind.SPAWN,
    HIRKind.LABEL,
    HIRKind.ARRAY_SET,
    HIRKind.FIELD_SET,
    HIRKind.CALL_VALUE,
}


def _literal_value(text: str, ty: str) -> object:
    if ty == "f64":
        return float(text)
    if ty == "bool":
        return text not in {"0", "false", "False"}
    if ty == "str":
        return text
    return int(text)


def _format_value(value: object, ty: str) -> str:
    if ty == "bool":
        return "1" if bool(value) else "0"
    if ty == "f64":
        return repr(float(value))
    return str(value)


def const_fold(fn: HIRFunction) -> None:
    values: dict[str, tuple[object, str]] = {}
    out: list[HIRInstr] = []
    for ins in fn.instrs:
        if ins.kind == HIRKind.CONST and ins.dst and ins.args:
            try:
                values[ins.dst] = (_literal_value(ins.args[0], ins.ty), ins.ty)
            except Exception:
                values.pop(ins.dst, None)
            out.append(ins)
            continue

        if ins.kind == HIRKind.BIN and ins.dst and len(ins.args) == 2 and ins.args[0] in values and ins.args[1] in values:
            a, aty = values[ins.args[0]]
            b, bty = values[ins.args[1]]
            op = ins.op or ""
            try:
                folded: object
                result_ty = ins.ty
                if op == "+" and (aty == "str" or bty == "str"):
                    folded = str(a) + str(b)
                    result_ty = "str"
                elif op == "+":
                    folded = a + b  # type: ignore[operator]
                elif op == "-":
                    folded = a - b  # type: ignore[operator]
                elif op == "*":
                    folded = a * b  # type: ignore[operator]
                elif op == "/" and b != 0:
                    folded = float(a) / float(b) if ins.ty == "f64" else int(a) // int(b)
                elif op == "%" and b != 0:
                    folded = int(a) % int(b)
                elif op == "==":
                    folded = a == b; result_ty = "bool"
                elif op == "!=":
                    folded = a != b; result_ty = "bool"
                elif op == "<":
                    folded = a < b; result_ty = "bool"  # type: ignore[operator]
                elif op == "<=":
                    folded = a <= b; result_ty = "bool"  # type: ignore[operator]
                elif op == ">":
                    folded = a > b; result_ty = "bool"  # type: ignore[operator]
                elif op == ">=":
                    folded = a >= b; result_ty = "bool"  # type: ignore[operator]
                elif op == "&&":
                    folded = bool(a) and bool(b); result_ty = "bool"
                elif op == "||":
                    folded = bool(a) or bool(b); result_ty = "bool"
                else:
                    raise ValueError
            except Exception:
                values.pop(ins.dst, None)
                out.append(ins)
                continue
            values[ins.dst] = (folded, result_ty)
            out.append(HIRInstr(HIRKind.CONST, dst=ins.dst, args=[_format_value(folded, result_ty)], ty=result_ty))
            continue

        if ins.kind == HIRKind.UNARY and ins.dst and ins.args and ins.args[0] in values:
            value, ty = values[ins.args[0]]
            if ins.op == "-":
                folded = -float(value) if ty == "f64" else -int(value)
                result_ty = ty
            elif ins.op == "!":
                folded = not bool(value)
                result_ty = "bool"
            else:
                values.pop(ins.dst, None)
                out.append(ins)
                continue
            values[ins.dst] = (folded, result_ty)
            out.append(HIRInstr(HIRKind.CONST, dst=ins.dst, args=[_format_value(folded, result_ty)], ty=result_ty))
            continue

        if ins.dst:
            values.pop(ins.dst, None)
        out.append(ins)
    fn.instrs = out


def _is_name(arg: str) -> bool:
    if not arg or arg in {"true", "false", "True", "False"}:
        return False
    try:
        float(arg)
        return False
    except ValueError:
        return True


def copy_propagation(fn: HIRFunction) -> None:
    aliases: dict[str, str] = {}

    def resolve(name: str) -> str:
        seen: set[str] = set()
        while name in aliases and name not in seen:
            seen.add(name)
            name = aliases[name]
        return name

    out: list[HIRInstr] = []
    for ins in fn.instrs:
        if ins.kind in {HIRKind.LABEL, HIRKind.JUMP, HIRKind.BRANCH_TRUE, HIRKind.BRANCH_READY, HIRKind.RET}:
            aliases.clear()
        args = [resolve(a) if _is_name(a) else a for a in ins.args]
        new = HIRInstr(ins.kind, dst=ins.dst, args=args, ty=ins.ty, op=ins.op, target=ins.target)
        if new.dst:
            aliases.pop(new.dst, None)
        if new.kind == HIRKind.MOVE and new.dst and new.args and _is_name(new.args[0]):
            aliases[new.dst] = resolve(new.args[0])
        out.append(new)
    fn.instrs = out


def dce(fn: HIRFunction) -> None:
    live: set[str] = set()
    kept: list[HIRInstr] = []
    dst_counts: dict[str, int] = {}
    for ins in fn.instrs:
        if ins.dst:
            dst_counts[ins.dst] = dst_counts.get(ins.dst, 0) + 1
    for ins in reversed(fn.instrs):
        critical = ins.kind in _ROOTS or ins.kind not in _PURE
        named_store = bool(ins.dst and dst_counts.get(ins.dst, 0) > 1)
        needed = critical or named_store or bool(ins.dst and ins.dst in live)
        if needed:
            kept.append(ins)
            if ins.dst:
                live.discard(ins.dst)
            live.update(a for a in ins.args if _is_name(a))
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


def run_optimizations(mod: HIRModule) -> HIRModule:
    for fn in mod.functions:
        const_fold(fn)
        copy_propagation(fn)
        dce(fn)
        remove_unreachable(fn)
    return mod
