from __future__ import annotations

from nexa.ir.hir import HIRFunction, HIRInstr, HIRKind, HIRModule


def const_fold(fn: HIRFunction) -> None:
    values: dict[str, int] = {}
    out: list[HIRInstr] = []
    for ins in fn.instrs:
        if ins.kind == HIRKind.CONST and ins.ty == "i32" and ins.dst and ins.args:
            values[ins.dst] = int(ins.args[0])
            out.append(ins)
        elif ins.kind == HIRKind.BIN and ins.dst and len(ins.args) == 2 and ins.args[0] in values and ins.args[1] in values:
            a, b = values[ins.args[0]], values[ins.args[1]]
            op = ins.op or ""
            if op == "+":
                c = a + b
            elif op == "-":
                c = a - b
            elif op == "*":
                c = a * b
            elif op == "/" and b != 0:
                c = a // b
            else:
                out.append(ins); continue
            values[ins.dst] = c
            out.append(HIRInstr(HIRKind.CONST, dst=ins.dst, args=[str(c)], ty="i32"))
        else:
            out.append(ins)
    fn.instrs = out


def dce(fn: HIRFunction) -> None:
    used: set[str] = set()
    for ins in fn.instrs:
        for a in ins.args:
            if a.startswith("t"):
                used.add(a)
    fn.instrs = [i for i in fn.instrs if not (i.dst and i.dst.startswith("t") and i.dst not in used and i.kind == HIRKind.CONST)]


def run_optimizations(mod: HIRModule) -> HIRModule:
    for fn in mod.functions:
        const_fold(fn)
        dce(fn)
    return mod
