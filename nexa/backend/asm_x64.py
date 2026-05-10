from __future__ import annotations

from nexa.ir.hir import HIRKind
from nexa.ir.mir import MIRFunction

ARG_REGS = ["rdi", "rsi", "rdx", "rcx", "r8", "r9"]


def _loc(name: str, alloc: dict[str, str | None], slots: dict[str, int]) -> str:
    reg = alloc.get(name)
    if reg:
        return reg
    if name not in slots:
        slots[name] = 8 * (len(slots) + 1)
    return f"qword [rbp-{slots[name]}]"


def emit_function(fn: MIRFunction, alloc: dict[str, str | None]) -> str:
    lines = ["; teaching pseudo x86-64, not ABI-complete", f"global {fn.name}", f"{fn.name}:", "  push rbp", "  mov rbp, rsp", "  sub rsp, 256"]
    slots: dict[str, int] = {}
    arg_buf: list[str] = []
    param_idx = 0

    for label in fn.order:
        block = fn.blocks.get(label)
        if block is None:
            continue
        lines.append(f"{label}:")
        for ins in block.instrs:
            if ins.kind == HIRKind.PARAM and ins.dst:
                src = ARG_REGS[param_idx] if param_idx < len(ARG_REGS) else f"qword [rbp+{16 + 8*(param_idx-len(ARG_REGS))}]"
                lines.append(f"  mov {_loc(ins.dst, alloc, slots)}, {src}")
                param_idx += 1
            elif ins.kind == HIRKind.ARG and ins.args:
                arg_buf.append(ins.args[0])
            elif ins.kind == HIRKind.CALL:
                callee = ins.op or ""
                if callee in {"recv", "send", "select_recv"} and ins.args:
                    arg_buf = ins.args
                for idx, a in enumerate(arg_buf):
                    if idx < len(ARG_REGS):
                        lines.append(f"  mov {ARG_REGS[idx]}, {_loc(a, alloc, slots)}")
                if callee == "send":
                    callee = "rt_chan_send"
                elif callee == "recv":
                    callee = "rt_chan_recv"
                lines.append(f"  call {callee}")
                if ins.dst:
                    lines.append(f"  mov {_loc(ins.dst, alloc, slots)}, rax")
                arg_buf.clear()
            elif ins.kind == HIRKind.CONST and ins.ty in {"i32", "bool"} and ins.dst and ins.args:
                lines.append(f"  mov {_loc(ins.dst, alloc, slots)}, {ins.args[0]}")
            elif ins.kind == HIRKind.BIN and ins.dst and len(ins.args) == 2:
                op = ins.op or "+"
                dst = _loc(ins.dst, alloc, slots)
                a = _loc(ins.args[0], alloc, slots)
                b = _loc(ins.args[1], alloc, slots)
                lines.append(f"  mov rax, {a}")
                if op in {"+", "-", "*"}:
                    m = {"+": "add", "-": "sub", "*": "imul"}[op]
                    lines.append(f"  {m} rax, {b}")
                elif op == "/":
                    lines.append("  cqo")
                    lines.append(f"  idiv {b}")
                elif op in {"==", "!=", "<", "<=", ">", ">="}:
                    lines.append(f"  cmp rax, {b}")
                    setop = {"==": "sete", "!=": "setne", "<": "setl", "<=": "setle", ">": "setg", ">=": "setge"}[op]
                    lines.append(f"  {setop} al")
                    lines.append("  movzx rax, al")
                lines.append(f"  mov {dst}, rax")
            elif ins.kind == HIRKind.UNARY and ins.dst and ins.args:
                dst = _loc(ins.dst, alloc, slots)
                src = _loc(ins.args[0], alloc, slots)
                lines.append(f"  mov rax, {src}")
                if ins.op == "-":
                    lines.append("  neg rax")
                else:
                    lines.extend(["  cmp rax, 0", "  sete al", "  movzx rax, al"])
                lines.append(f"  mov {dst}, rax")
            elif ins.kind == HIRKind.MOVE and ins.dst and ins.args:
                lines.append(f"  mov {_loc(ins.dst, alloc, slots)}, {_loc(ins.args[0], alloc, slots)}")
            elif ins.kind == HIRKind.RET:
                if ins.args:
                    lines.append(f"  mov rax, {_loc(ins.args[0], alloc, slots)}")
                lines.extend(["  leave", "  ret"])
            elif ins.kind == HIRKind.JUMP and ins.target:
                lines.append(f"  jmp {ins.target}")
            elif ins.kind == HIRKind.BRANCH_TRUE and ins.target and ins.args:
                lines.append(f"  cmp {_loc(ins.args[0], alloc, slots)}, 0")
                lines.append(f"  jne {ins.target}")
            elif ins.kind == HIRKind.BRANCH_READY and ins.target and ins.args:
                lines.append(f"  mov rdi, {_loc(ins.args[0], alloc, slots)}")
                lines.append("  call rt_chan_ready")
                lines.append("  cmp rax, 0")
                lines.append(f"  jne {ins.target}")
            elif ins.kind in {HIRKind.STRUCT_NEW, HIRKind.FIELD_GET, HIRKind.FIELD_SET, HIRKind.ARRAY_NEW, HIRKind.ARRAY_GET, HIRKind.ARRAY_SET}:
                lines.append(f"  ; {ins.kind.name} {ins.op or ''} is VM-only in this teaching backend")
    return "\n".join(lines) + "\n"
