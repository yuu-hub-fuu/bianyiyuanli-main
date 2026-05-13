"""Real Win64 x86-64 backend.

Emits GAS Intel-syntax assembly that the GNU assembler (`as.exe`) bundled
with MinGW64 can turn into a real `.o`, which the GNU linker (driven via
`gcc`) then links against [nexa_rt.c](../runtime/nexa_rt.c) to produce
an actual `.exe`.

Calling convention: Win64 (Microsoft x64).
    - First four integer args:  rcx, rdx, r8, r9
    - Args 5+:                  [rsp+32], [rsp+40], ...
    - 32-byte shadow space is allocated by the *caller* and lives at the
      bottom of every frame (the callee may scribble in it).
    - Stack must be 16-byte aligned at every `call` instruction.
    - Return value in rax.
    - Volatile (caller-saved):     rax, rcx, rdx, r8, r9, r10, r11
    - Non-volatile (callee-saved): rbx, rbp, rdi, rsi, r12-r15, rsp

Allocation strategy: every Nexa value lives in a stack slot at
[rbp - 8*N]. Volatile registers (rax/rcx/rdx) are used only as transient
scratch within a single quad — never to hold values across `call`. This
keeps the model trivially correct in the presence of arbitrary calls;
the linear-scan allocator computed in `compile_source` is still
displayed in artifacts but is intentionally not consulted here.

All Nexa scalars are stored as 64-bit signed integers, even when typed
i32/bool. The runtime narrows on the C side at print time.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from nexa.ir.hir import HIRKind
from nexa.ir.mir import MIRFunction, MIRInstr, MIRModule


WIN64_ARG_REGS = ["rcx", "rdx", "r8", "r9"]
WIN64_XMM_ARG_REGS = ["xmm0", "xmm1", "xmm2", "xmm3"]

_RUNTIME_BUILTINS = {
    "print": "nx_print_i32",  # default; resolves to nx_print_f64 when arg is f64
    "panic": "nx_panic",
    "read_i32": "nx_read_i32",
    "read_f64": "nx_read_f64",
    "read_str": "nx_read_str",
    "len": "nx_array_len",
    "cat": "nx_str_cat",
    "strlen": "nx_str_len",
    "substr": "nx_substr",
    "find": "nx_find",
    "contains": "nx_contains",
    "starts_with": "nx_starts_with",
    "ends_with": "nx_ends_with",
    "replace": "nx_replace",
    "trim": "nx_trim",
    "lower": "nx_lower",
    "upper": "nx_upper",
    "ord": "nx_ord",
    "chr": "nx_chr",
    "parse_i32": "nx_parse_i32",
    "parse_f64": "nx_parse_f64",
    "rand": "nx_rand",
    "srand": "nx_srand",
    "rand_range": "nx_rand_range",
    "time": "nx_time",
    "clock": "nx_clock",
    "ptr_get": "nx_ptr_get_i64",
    "ptr_set": "nx_ptr_set_i64",
    "ptr_new": "nx_ptr_new_i64",
    "chan": "nx_chan_new",
    "send": "nx_chan_send",
    "recv": "nx_chan_recv",
    "select_recv": "nx_chan_recv",
}

# (param_types, return_type) for runtime builtins. Used to drive Win64
# register-class selection (GPR vs XMM) at call sites.
_RUNTIME_SIGS: dict[str, tuple[list[str], str]] = {
    "print": (["i64"], "void"),
    "panic": (["str"], "void"),
    "read_i32": ([], "i64"),
    "read_f64": ([], "f64"),
    "read_str": ([], "str"),
    "len": (["i64"], "i64"),
    "cat": (["str", "str"], "str"),
    "strlen": (["str"], "i64"),
    "substr": (["str", "i64", "i64"], "str"),
    "find": (["str", "str"], "i64"),
    "contains": (["str", "str"], "i64"),
    "starts_with": (["str", "str"], "i64"),
    "ends_with": (["str", "str"], "i64"),
    "replace": (["str", "str", "str"], "str"),
    "trim": (["str"], "str"),
    "lower": (["str"], "str"),
    "upper": (["str"], "str"),
    "ord": (["str"], "i64"),
    "chr": (["i64"], "str"),
    "parse_i32": (["str"], "i64"),
    "parse_f64": (["str"], "f64"),
    "rand": ([], "i64"),
    "srand": (["i64"], "void"),
    "rand_range": (["i64", "i64"], "i64"),
    "time": ([], "i64"),
    "clock": ([], "i64"),
    "ptr_get": (["i64"], "i64"),
    "ptr_set": (["i64", "i64"], "void"),
    "ptr_new": (["i64"], "i64"),
    "chan": (["i64"], "i64"),
    "send": (["i64", "i64"], "void"),
    "recv": (["i64"], "i64"),
    "select_recv": (["i64"], "i64"),
}


def _is_float(ty: str | None) -> bool:
    return ty == "f64"


def _int_literal(value: str) -> int | None:
    if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
        return int(value)
    return None


def _float_literal(value: str) -> float | None:
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed if "." in value or "e" in value.lower() else None


def _is_power_of_two(value: int) -> bool:
    return value > 0 and (value & (value - 1)) == 0


def _shift_for_power_of_two(value: int) -> int:
    return value.bit_length() - 1


def _disp(value: int) -> str:
    return f"+{value}" if value >= 0 else str(value)


def asm_name(nexa_name: str) -> str:
    """Mangle a Nexa function name to its asm-level symbol.

    `main` becomes `nx_user_main` so the C runtime's libc-driven `main`
    can dispatch into it without colliding with the CRT entry point.
    All other functions are prefixed with `nx_` so they cannot clash
    with mnemonics or libc symbols.
    """
    if nexa_name == "main":
        return "nx_user_main"
    return "nx_" + nexa_name


def _resolve_callee(callee: str) -> str:
    if callee in _RUNTIME_BUILTINS:
        return _RUNTIME_BUILTINS[callee]
    return asm_name(callee)


def _escape_string_for_gas(value: str) -> str:
    out: list[str] = []
    for byte in value.encode("utf-8"):
        if byte == 0x22:
            out.append("\\\"")
        elif byte == 0x5C:
            out.append("\\\\")
        elif byte == 0x0A:
            out.append("\\n")
        elif byte == 0x0D:
            out.append("\\r")
        elif byte == 0x09:
            out.append("\\t")
        elif 32 <= byte <= 126:
            out.append(chr(byte))
        else:
            out.append(f"\\{byte:03o}")
    return "".join(out)


@dataclass
class _RodataPool:
    string_to_label: dict[str, str] = field(default_factory=dict)
    float_to_label: dict[str, str] = field(default_factory=dict)
    lines: list[str] = field(default_factory=list)

    def label_for(self, value: str) -> str:
        if value in self.string_to_label:
            return self.string_to_label[value]
        label = f".LCstr{len(self.string_to_label)}"
        self.string_to_label[value] = label
        self.lines.append(f"{label}:")
        self.lines.append(f'    .asciz "{_escape_string_for_gas(value)}"')
        return label

    def label_for_float(self, raw: str) -> str:
        # Normalize so that "1.5" and "1.50" share a slot.
        try:
            key = repr(float(raw))
        except ValueError:
            key = raw
        if key in self.float_to_label:
            return self.float_to_label[key]
        label = f".LCflt{len(self.float_to_label)}"
        self.float_to_label[key] = label
        self.lines.append("    .p2align 3")
        self.lines.append(f"{label}:")
        self.lines.append(f"    .double {key}")
        return label

    def render(self) -> list[str]:
        if not self.lines:
            return []
        return ["", "    .section .rodata", "    .p2align 3"] + self.lines


@dataclass
class _FunctionContext:
    fn: MIRFunction
    layouts: dict[str, list[str]]
    rodata: _RodataPool
    signatures: dict[str, tuple[list[str], str]]
    class_ids: dict[str, int] = field(default_factory=dict)
    virtual_methods: dict[str, dict[str, str]] = field(default_factory=dict)
    destructors: dict[str, str] = field(default_factory=dict)
    class_bases: dict[str, str | None] = field(default_factory=dict)
    slot_types: dict[str, str] = field(default_factory=dict)
    fn_ret_type: str = "i64"
    slots: dict[str, int] = field(default_factory=dict)
    str_temps: dict[str, str] = field(default_factory=dict)
    body: list[str] = field(default_factory=list)
    arg_buf: list[str] = field(default_factory=list)
    param_idx: int = 0
    max_outgoing_stack_args: int = 0
    epilogue: str = ""

    def slot(self, name: str) -> int:
        if name not in self.slots:
            self.slots[name] = (len(self.slots) + 1) * 8
        return self.slots[name]

    def loc(self, name: str) -> str:
        return f"qword ptr [rbp-{self.slot(name)}]"

    def type_of(self, name: str) -> str:
        if name in self.slot_types:
            return self.slot_types[name]
        if _float_literal(name) is not None:
            return "f64"
        if _int_literal(name) is not None:
            return "i64"
        # Numeric literals threaded directly into args have no slot type.
        return "i64"


def _compute_signatures(mod: MIRModule) -> dict[str, tuple[list[str], str]]:
    """Walk every function once to extract (param types, return type).

    The Win64 backend needs this at every call site so it can decide
    whether to drop each arg into a GPR or an XMM register, and whether
    to unpack the return value out of `rax` or `xmm0`. PARAM ordering in
    MIR matches the source signature, so we can read it linearly.
    """
    sigs: dict[str, tuple[list[str], str]] = {}
    for fn in mod.functions:
        params: list[str] = []
        ret_ty = "i64"
        for label in fn.order:
            block = fn.blocks.get(label)
            if block is None:
                continue
            for ins in block.instrs:
                if ins.kind == HIRKind.PARAM and ins.dst:
                    params.append(ins.ty or "i64")
                elif ins.kind == HIRKind.RET and ins.args and ins.ty and ins.ty != "void":
                    ret_ty = ins.ty
        sigs[fn.name] = (params, ret_ty)
    return sigs


def _compute_slot_types(fn: MIRFunction) -> dict[str, str]:
    types: dict[str, str] = {}
    for label in fn.order:
        block = fn.blocks.get(label)
        if block is None:
            continue
        for ins in block.instrs:
            if ins.dst and ins.ty and ins.ty != "void":
                # First definition wins for sane (SSA-like) input;
                # otherwise last wins, which is still safe because
                # all values are kept in 8-byte slots.
                types.setdefault(ins.dst, ins.ty)
    return types


def _emit_load(ctx: _FunctionContext, reg: str, src: str) -> None:
    """Load a value (variable name or immediate literal) into `reg`."""
    if src in ctx.str_temps:
        ctx.body.append(f"    mov {reg}, {ctx.loc(src)}")
        return
    if src.startswith("-") and src[1:].isdigit():
        ctx.body.append(f"    mov {reg}, {src}")
        return
    if src.isdigit():
        ctx.body.append(f"    mov {reg}, {src}")
        return
    if src in ctx.slots or src.isidentifier() or src.startswith("t"):
        ctx.body.append(f"    mov {reg}, {ctx.loc(src)}")
        return
    ctx.body.append(f"    mov {reg}, {src}")


def _emit_load_xmm(ctx: _FunctionContext, xmm: str, src: str) -> None:
    """Load an 8-byte value into an XMM register as a packed double.

    For variables, this is a `movsd` from the slot; for f64 literals
    threaded directly (rare path) we materialize a `.rodata` constant
    first. Slots not previously seen are auto-allocated.
    """
    if src in ctx.slots or src.isidentifier() or src.startswith("t"):
        ctx.body.append(f"    movsd {xmm}, {ctx.loc(src)}")
        return
    # Treat unknown source as a literal float.
    label = ctx.rodata.label_for_float(src)
    ctx.body.append(f"    movsd {xmm}, qword ptr [rip+{label}]")


def _emit_store_xmm(ctx: _FunctionContext, dst: str, xmm: str) -> None:
    ctx.body.append(f"    movsd {ctx.loc(dst)}, {xmm}")


def _emit_param(ctx: _FunctionContext, ins: MIRInstr) -> None:
    if not ins.dst:
        return
    idx = ctx.param_idx
    is_float = _is_float(ins.ty)
    if idx < len(WIN64_ARG_REGS):
        if is_float:
            # Win64: arg position N for a float arrives in xmm_N regardless
            # of any preceding integer args; the matching gpr slot stays
            # untouched (only varargs would fill both).
            ctx.body.append(f"    movsd {ctx.loc(ins.dst)}, {WIN64_XMM_ARG_REGS[idx]}")
        else:
            ctx.body.append(f"    mov {ctx.loc(ins.dst)}, {WIN64_ARG_REGS[idx]}")
    else:
        # Arg N>=5 lives at [rbp + 48 + 8*(N-4)]: see prologue comments.
        # Memory copy via rax preserves the bit pattern for both int and
        # float, so we can use the same path regardless of type.
        offset = 48 + 8 * (idx - len(WIN64_ARG_REGS))
        ctx.body.append(f"    mov rax, qword ptr [rbp+{offset}]")
        ctx.body.append(f"    mov {ctx.loc(ins.dst)}, rax")
    ctx.param_idx += 1


def _emit_const(ctx: _FunctionContext, ins: MIRInstr) -> None:
    if not ins.dst or not ins.args:
        return
    raw = ins.args[0]
    if ins.ty == "str":
        label = ctx.rodata.label_for(raw)
        ctx.str_temps[ins.dst] = label
        ctx.body.append(f"    lea rax, [rip+{label}]")
        ctx.body.append(f"    mov {ctx.loc(ins.dst)}, rax")
        return
    if ins.ty == "f64":
        label = ctx.rodata.label_for_float(raw)
        ctx.body.append(f"    movsd xmm0, qword ptr [rip+{label}]")
        _emit_store_xmm(ctx, ins.dst, "xmm0")
        return
    # i32/i64/bool: store as 64-bit signed integer.
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if value == 0:
        ctx.body.append("    xor rax, rax")
        ctx.body.append(f"    mov {ctx.loc(ins.dst)}, rax")
        return
    ctx.body.append(f"    mov rax, {value}")
    ctx.body.append(f"    mov {ctx.loc(ins.dst)}, rax")


def _emit_func_addr(ctx: _FunctionContext, ins: MIRInstr) -> None:
    if not ins.dst or not ins.args:
        return
    ctx.body.append(f"    lea rax, [rip+{_resolve_callee(ins.args[0])}]")
    ctx.body.append(f"    mov {ctx.loc(ins.dst)}, rax")


def _emit_move(ctx: _FunctionContext, ins: MIRInstr) -> None:
    if not ins.dst or not ins.args:
        return
    src = ins.args[0]
    if ins.dst == src:
        return
    _emit_load(ctx, "rax", src)
    ctx.body.append(f"    mov {ctx.loc(ins.dst)}, rax")
    if src in ctx.str_temps:
        ctx.str_temps[ins.dst] = ctx.str_temps[src]


def _emit_unary(ctx: _FunctionContext, ins: MIRInstr) -> None:
    if not ins.dst or not ins.args:
        return
    src = ins.args[0]
    if _is_float(ins.ty) and ins.op == "-":
        # 0.0 - src; xorpd zeroes both lanes.
        ctx.body.append("    xorpd xmm0, xmm0")
        _emit_load_xmm(ctx, "xmm1", src)
        ctx.body.append("    subsd xmm0, xmm1")
        _emit_store_xmm(ctx, ins.dst, "xmm0")
        return
    _emit_load(ctx, "rax", src)
    if ins.op == "-":
        ctx.body.append("    neg rax")
    else:  # "!"
        ctx.body.append("    cmp rax, 0")
        ctx.body.append("    sete al")
        ctx.body.append("    movzx rax, al")
    ctx.body.append(f"    mov {ctx.loc(ins.dst)}, rax")


_SETCC = {"==": "sete", "!=": "setne", "<": "setl", "<=": "setle", ">": "setg", ">=": "setge"}

# After `ucomisd xmm_a, xmm_b`, the resulting flags are CF/PF/ZF set
# by IEEE comparison. We assume operands are not NaN (matches the rest
# of the project: the front end has no NaN literal and the optimizer
# does not introduce one).
_SETCC_F = {"==": "sete", "!=": "setne", "<": "setb", "<=": "setbe", ">": "seta", ">=": "setae"}


def _emit_bin_f64(ctx: _FunctionContext, ins: MIRInstr) -> None:
    if not ins.dst or len(ins.args) != 2:
        return
    op = ins.op or "+"
    a, b = ins.args
    _emit_load_xmm(ctx, "xmm0", a)
    _emit_load_xmm(ctx, "xmm1", b)
    if op == "+":
        ctx.body.append("    addsd xmm0, xmm1")
    elif op == "-":
        ctx.body.append("    subsd xmm0, xmm1")
    elif op == "*":
        ctx.body.append("    mulsd xmm0, xmm1")
    elif op == "/":
        ctx.body.append("    divsd xmm0, xmm1")
    else:
        ctx.body.append(f"    ; unsupported f64 BIN op {op!r}")
    _emit_store_xmm(ctx, ins.dst, "xmm0")


def _emit_bin_f64_cmp(ctx: _FunctionContext, ins: MIRInstr) -> None:
    if not ins.dst or len(ins.args) != 2:
        return
    op = ins.op or "=="
    a, b = ins.args
    _emit_load_xmm(ctx, "xmm0", a)
    _emit_load_xmm(ctx, "xmm1", b)
    ctx.body.append("    ucomisd xmm0, xmm1")
    setcc = _SETCC_F.get(op, "sete")
    ctx.body.append(f"    {setcc} al")
    ctx.body.append("    movzx rax, al")
    ctx.body.append(f"    mov {ctx.loc(ins.dst)}, rax")


def _emit_bin(ctx: _FunctionContext, ins: MIRInstr) -> None:
    if not ins.dst or len(ins.args) != 2:
        return
    op = ins.op or "+"
    a, b = ins.args
    if ins.ty == "str" and op in {"+", "-"}:
        _emit_load(ctx, "rcx", a)
        _emit_load(ctx, "rdx", b)
        ctx.body.append(f"    call {'nx_str_cat' if op == '+' else 'nx_str_remove'}")
        ctx.body.append(f"    mov {ctx.loc(ins.dst)}, rax")
        return
    # Float arithmetic: result type is f64.
    if _is_float(ins.ty) and op in {"+", "-", "*", "/"}:
        _emit_bin_f64(ctx, ins)
        return
    # Float comparison: operands are f64 even though result is bool.
    if op in _SETCC and (_is_float(ctx.type_of(a)) or _is_float(ctx.type_of(b))):
        _emit_bin_f64_cmp(ctx, ins)
        return

    _emit_load(ctx, "rax", a)
    aval = _int_literal(a)
    bval = _int_literal(b)
    if op == "+":
        if bval == 0:
            pass
        elif aval == 0:
            _emit_load(ctx, "rax", b)
        elif bval is not None:
            ctx.body.append(f"    lea rax, [rax{_disp(bval)}]")
        elif aval is not None:
            _emit_load(ctx, "rax", b)
            ctx.body.append(f"    lea rax, [rax{_disp(aval)}]")
        else:
            _emit_load(ctx, "rcx", b)
            ctx.body.append("    lea rax, [rax+rcx]")
    elif op == "-":
        if bval == 0:
            pass
        elif bval is not None:
            ctx.body.append(f"    lea rax, [rax{_disp(-bval)}]")
        else:
            _emit_load(ctx, "rcx", b)
            ctx.body.append("    sub rax, rcx")
    elif op == "*":
        literal = bval
        value_src = a
        if literal is None and aval is not None:
            literal = aval
            value_src = b
            _emit_load(ctx, "rax", value_src)
        if literal == 0:
            ctx.body.append("    xor rax, rax")
        elif literal == 1:
            pass
        elif literal == 2:
            ctx.body.append("    lea rax, [rax+rax]")
        elif literal == 3:
            ctx.body.append("    lea rax, [rax+rax*2]")
        elif literal == 5:
            ctx.body.append("    lea rax, [rax+rax*4]")
        elif literal == 9:
            ctx.body.append("    lea rax, [rax+rax*8]")
        elif literal is not None and _is_power_of_two(literal):
            ctx.body.append(f"    shl rax, {_shift_for_power_of_two(literal)}")
        else:
            _emit_load(ctx, "rcx", b)
            ctx.body.append("    imul rax, rcx")
    elif op == "/":
        if bval == 1:
            ctx.body.append(f"    mov {ctx.loc(ins.dst)}, rax")
            return
        _emit_load(ctx, "rcx", b)
        ctx.body.append("    cqo")
        ctx.body.append("    idiv rcx")
    elif op == "%":
        _emit_load(ctx, "rcx", b)
        ctx.body.append("    cqo")
        ctx.body.append("    idiv rcx")
        ctx.body.append("    mov rax, rdx")
    elif op in _SETCC:
        if bval == 0:
            ctx.body.append("    test rax, rax")
        else:
            _emit_load(ctx, "rcx", b)
            ctx.body.append("    cmp rax, rcx")
        ctx.body.append(f"    {_SETCC[op]} al")
        ctx.body.append("    movzx rax, al")
    elif op == "&&":
        _emit_load(ctx, "rcx", b)
        ctx.body.append("    test rax, rax")
        ctx.body.append("    setne al")
        ctx.body.append("    movzx rax, al")
        ctx.body.append("    test rcx, rcx")
        ctx.body.append("    setne cl")
        ctx.body.append("    movzx rcx, cl")
        ctx.body.append("    and rax, rcx")
    elif op == "||":
        _emit_load(ctx, "rcx", b)
        ctx.body.append("    test rax, rax")
        ctx.body.append("    setne al")
        ctx.body.append("    movzx rax, al")
        ctx.body.append("    test rcx, rcx")
        ctx.body.append("    setne cl")
        ctx.body.append("    movzx rcx, cl")
        ctx.body.append("    or rax, rcx")
    else:
        ctx.body.append(f"    ; unsupported BIN op {op!r}")
    ctx.body.append(f"    mov {ctx.loc(ins.dst)}, rax")


def _emit_call_args(ctx: _FunctionContext, args: list[str], param_types: list[str]) -> None:
    """Move the call's arguments into registers / shadow stack slots.

    `param_types` parallels `args`: each entry is the *expected* type of
    the corresponding parameter. We use it to pick gpr-vs-xmm and to
    decide whether stack-spilled args go through `rax` or `xmm0` as the
    intermediate. When the callee's signature is unknown we fall back
    to the caller-side type seen in `slot_types`.
    """
    stack_extra = max(0, len(args) - len(WIN64_ARG_REGS))
    ctx.max_outgoing_stack_args = max(ctx.max_outgoing_stack_args, stack_extra)
    for idx, a in enumerate(args):
        ty = param_types[idx] if idx < len(param_types) else ctx.type_of(a)
        is_float = _is_float(ty)
        if idx < len(WIN64_ARG_REGS):
            if is_float:
                _emit_load_xmm(ctx, WIN64_XMM_ARG_REGS[idx], a)
            else:
                _emit_load(ctx, WIN64_ARG_REGS[idx], a)
        else:
            offset = 32 + 8 * (idx - len(WIN64_ARG_REGS))
            if is_float:
                _emit_load_xmm(ctx, "xmm0", a)
                ctx.body.append(f"    movsd qword ptr [rsp+{offset}], xmm0")
            else:
                _emit_load(ctx, "rax", a)
                ctx.body.append(f"    mov qword ptr [rsp+{offset}], rax")


def _resolve_print_target(ctx: _FunctionContext, args: list[str]) -> str:
    """`print()` is the only polymorphic builtin: dispatch by arg type."""
    if args and ctx.type_of(args[0]) == "str":
        return "nx_print_str"
    if args and _is_float(ctx.type_of(args[0])):
        return "nx_print_f64"
    return "nx_print_i32"


def _callee_signature(ctx: _FunctionContext, callee: str, fallback_args: list[str]) -> tuple[list[str], str]:
    if callee in _RUNTIME_SIGS:
        params, ret = _RUNTIME_SIGS[callee]
        return list(params), ret
    if callee in ctx.signatures:
        params, ret = ctx.signatures[callee]
        return list(params), ret
    # Unknown function: best effort — use caller-side types so we still
    # land each f64 in an xmm register.
    return [ctx.type_of(a) for a in fallback_args], "i64"


def _runtime_dispatch(ctx: _FunctionContext, callee: str, args: list[str], ret_hint: str | None) -> tuple[str, list[str], str] | None:
    first_ty = ctx.type_of(args[0]) if args else "i64"
    result_ty = ret_hint or "i64"
    if callee == "len" and first_ty == "str":
        return "nx_str_len", ["str"], "i64"
    if callee in {"str", "to_str"}:
        if first_ty == "f64":
            return "nx_to_str_f64", ["f64"], "str"
        if first_ty == "str":
            return "nx_str_clone", ["str"], "str"
        return "nx_to_str_i64", ["i64"], "str"
    if callee in {"int", "to_i32"}:
        if first_ty == "f64":
            return "nx_to_i32_f64", ["f64"], "i64"
        if first_ty == "str":
            return "nx_to_i32_str", ["str"], "i64"
        return "nx_to_i32_i64", ["i64"], "i64"
    if callee in {"float", "to_f64"}:
        if first_ty == "f64":
            return "nx_to_f64_f64", ["f64"], "f64"
        if first_ty == "str":
            return "nx_to_f64_str", ["str"], "f64"
        return "nx_to_f64_i64", ["i64"], "f64"
    if callee in {"bool", "to_bool"}:
        if first_ty == "f64":
            return "nx_to_bool_f64", ["f64"], "i64"
        if first_ty == "str":
            return "nx_to_bool_str", ["str"], "i64"
        return "nx_to_bool_i64", ["i64"], "i64"
    if callee == "abs":
        if first_ty == "f64" or result_ty == "f64":
            return "nx_abs_f64", ["f64"], "f64"
        return "nx_abs_i64", ["i64"], "i64"
    if callee in {"min", "max"}:
        prefix = "nx_min" if callee == "min" else "nx_max"
        if result_ty == "str" or first_ty == "str":
            return f"{prefix}_str", ["str", "str"], "str"
        if result_ty == "f64" or first_ty == "f64":
            return f"{prefix}_f64", ["f64", "f64"], "f64"
        return f"{prefix}_i64", ["i64", "i64"], "i64"
    if callee in {"copy", "clone", "shallow_copy", "deep_copy"}:
        if first_ty == "str":
            return "nx_str_clone", ["str"], "str"
        return "nx_to_i32_i64", ["i64"], result_ty
    if callee == "ptr_new":
        if first_ty == "f64":
            return "nx_ptr_new_f64", ["f64"], "i64"
        return "nx_ptr_new_i64", ["i64"], "i64"
    if callee == "ptr_get":
        if result_ty == "f64":
            return "nx_ptr_get_f64", ["i64"], "f64"
        return "nx_ptr_get_i64", ["i64"], "i64"
    if callee == "ptr_set":
        second_ty = ctx.type_of(args[1]) if len(args) > 1 else "i64"
        if second_ty == "f64":
            return "nx_ptr_set_f64", ["i64", "f64"], "void"
        return "nx_ptr_set_i64", ["i64", "i64"], "void"
    if callee == "const_ptr_new":
        if first_ty == "f64":
            return "nx_ptr_new_f64", ["f64"], "i64"
        return "nx_ptr_new_i64", ["i64"], "i64"
    return None


def _emit_call(ctx: _FunctionContext, ins: MIRInstr) -> None:
    callee = ins.op or ""
    if callee in {"recv", "send", "select_recv", "chan"} and ins.args:
        args = list(ins.args)
    else:
        args = list(ctx.arg_buf)

    if callee == "print":
        target = _resolve_print_target(ctx, args)
        # Seed param types from the actual arg type so xmm vs gpr is right.
        param_types = [ctx.type_of(a) for a in args]
        ret_ty = "void"
    elif dispatched := _runtime_dispatch(ctx, callee, args, ins.ty):
        target, param_types, ret_ty = dispatched
    else:
        target = _resolve_callee(callee)
        param_types, ret_ty = _callee_signature(ctx, callee, args)

    _emit_call_args(ctx, args, param_types)
    ctx.body.append(f"    call {target}")
    if ins.dst:
        if _is_float(ret_ty):
            _emit_store_xmm(ctx, ins.dst, "xmm0")
        else:
            ctx.body.append(f"    mov {ctx.loc(ins.dst)}, rax")
    ctx.arg_buf.clear()


def _emit_struct_new(ctx: _FunctionContext, ins: MIRInstr) -> None:
    if not ins.dst:
        return
    struct_name = ins.op or ""
    layout = ctx.layouts.get(struct_name, [])
    size = max(8, 8 * len(layout))
    ctx.body.append(f"    mov rcx, {size}")
    ctx.body.append("    call nx_alloc")
    ctx.body.append(f"    mov {ctx.loc(ins.dst)}, rax")
    # ins.args are [name1, val1, name2, val2, ...]
    for i in range(0, len(ins.args), 2):
        if i + 1 >= len(ins.args):
            break
        fname = ins.args[i]
        fval = ins.args[i + 1]
        try:
            offset = layout.index(fname) * 8
        except ValueError:
            ctx.body.append(f"    ; warning: field {fname} not in layout of {struct_name}")
            continue
        ctx.body.append(f"    mov rcx, {ctx.loc(ins.dst)}")
        _emit_load(ctx, "rdx", fval)
        ctx.body.append(f"    mov qword ptr [rcx+{offset}], rdx")


def _split_struct_field(op: str | None) -> tuple[str, str]:
    if not op:
        return "", ""
    if "." in op:
        s, f = op.rsplit(".", 1)
        return s, f
    return "", op


def _emit_field_get(ctx: _FunctionContext, ins: MIRInstr) -> None:
    if not ins.dst or not ins.args:
        return
    struct_name, field = _split_struct_field(ins.op)
    layout = ctx.layouts.get(struct_name, [])
    try:
        offset = layout.index(field) * 8
    except ValueError:
        offset = 0
        ctx.body.append(f"    ; warning: field {field} not in layout {struct_name}")
    _emit_load(ctx, "rax", ins.args[0])
    ctx.body.append(f"    mov rax, qword ptr [rax+{offset}]")
    ctx.body.append(f"    mov {ctx.loc(ins.dst)}, rax")


def _emit_field_set(ctx: _FunctionContext, ins: MIRInstr) -> None:
    if len(ins.args) != 2:
        return
    struct_name, field = _split_struct_field(ins.op)
    layout = ctx.layouts.get(struct_name, [])
    try:
        offset = layout.index(field) * 8
    except ValueError:
        offset = 0
        ctx.body.append(f"    ; warning: field {field} not in layout {struct_name}")
    _emit_load(ctx, "rax", ins.args[0])
    _emit_load(ctx, "rcx", ins.args[1])
    ctx.body.append(f"    mov qword ptr [rax+{offset}], rcx")


def _emit_array_new(ctx: _FunctionContext, ins: MIRInstr) -> None:
    if not ins.dst:
        return
    n = len(ins.args)
    size = 8 * (n + 1)
    ctx.body.append(f"    mov rcx, {size}")
    ctx.body.append("    call nx_alloc")
    ctx.body.append(f"    mov {ctx.loc(ins.dst)}, rax")
    ctx.body.append(f"    mov qword ptr [rax], {n}")
    for i, a in enumerate(ins.args):
        ctx.body.append(f"    mov rcx, {ctx.loc(ins.dst)}")
        _emit_load(ctx, "rdx", a)
        ctx.body.append(f"    mov qword ptr [rcx+{8 + i*8}], rdx")


def _emit_array_get(ctx: _FunctionContext, ins: MIRInstr) -> None:
    if not ins.dst or len(ins.args) != 2:
        return
    _emit_load(ctx, "rax", ins.args[0])
    _emit_load(ctx, "rcx", ins.args[1])
    ctx.body.append("    mov rax, qword ptr [rax+8+rcx*8]")
    ctx.body.append(f"    mov {ctx.loc(ins.dst)}, rax")


def _emit_array_set(ctx: _FunctionContext, ins: MIRInstr) -> None:
    if len(ins.args) != 3:
        return
    _emit_load(ctx, "rax", ins.args[0])
    _emit_load(ctx, "rcx", ins.args[1])
    _emit_load(ctx, "rdx", ins.args[2])
    ctx.body.append("    mov qword ptr [rax+8+rcx*8], rdx")


def _emit_ptr_addr(ctx: _FunctionContext, ins: MIRInstr) -> None:
    if not ins.dst or not ins.args:
        return
    src = ins.args[0]
    ctx.body.append(f"    lea rax, {ctx.loc(src)}")
    ctx.body.append(f"    mov {ctx.loc(ins.dst)}, rax")


def _emit_ptr_load(ctx: _FunctionContext, ins: MIRInstr) -> None:
    if not ins.dst or not ins.args:
        return
    _emit_load(ctx, "rax", ins.args[0])
    ctx.body.append("    mov rax, qword ptr [rax]")
    ctx.body.append(f"    mov {ctx.loc(ins.dst)}, rax")


def _emit_ptr_store(ctx: _FunctionContext, ins: MIRInstr) -> None:
    if len(ins.args) != 2:
        return
    _emit_load(ctx, "rax", ins.args[0])
    _emit_load(ctx, "rdx", ins.args[1])
    ctx.body.append("    mov qword ptr [rax], rdx")


def _emit_ret(ctx: _FunctionContext, ins: MIRInstr) -> None:
    if ins.args:
        if _is_float(ctx.fn_ret_type):
            _emit_load_xmm(ctx, "xmm0", ins.args[0])
        else:
            _emit_load(ctx, "rax", ins.args[0])
    else:
        if _is_float(ctx.fn_ret_type):
            ctx.body.append("    xorpd xmm0, xmm0")
        else:
            ctx.body.append("    xor rax, rax")
    ctx.body.append(f"    jmp {ctx.epilogue}")


def _emit_jump(ctx: _FunctionContext, ins: MIRInstr) -> None:
    if ins.target:
        ctx.body.append(f"    jmp .L_{ctx.fn.name}_{ins.target}")


def _emit_branch_true(ctx: _FunctionContext, ins: MIRInstr) -> None:
    if not ins.args or not ins.target:
        return
    _emit_load(ctx, "rax", ins.args[0])
    ctx.body.append("    test rax, rax")
    ctx.body.append(f"    jne .L_{ctx.fn.name}_{ins.target}")


def _emit_branch_ready(ctx: _FunctionContext, ins: MIRInstr) -> None:
    if not ins.args or not ins.target:
        return
    _emit_load(ctx, "rcx", ins.args[0])
    ctx.body.append("    call nx_chan_ready")
    ctx.body.append("    test rax, rax")
    ctx.body.append(f"    jne .L_{ctx.fn.name}_{ins.target}")


def _emit_arg(ctx: _FunctionContext, ins: MIRInstr) -> None:
    if ins.args:
        ctx.arg_buf.append(ins.args[0])


def _emit_instr(ctx: _FunctionContext, ins: MIRInstr) -> None:
    if ins.kind == HIRKind.PARAM:
        _emit_param(ctx, ins)
    elif ins.kind == HIRKind.CONST:
        _emit_const(ctx, ins)
    elif ins.kind == HIRKind.MOVE:
        _emit_move(ctx, ins)
    elif ins.kind == HIRKind.UNARY:
        _emit_unary(ctx, ins)
    elif ins.kind == HIRKind.BIN:
        _emit_bin(ctx, ins)
    elif ins.kind == HIRKind.ARG:
        _emit_arg(ctx, ins)
    elif ins.kind == HIRKind.CALL:
        _emit_call(ctx, ins)
    elif ins.kind == HIRKind.RET:
        _emit_ret(ctx, ins)
    elif ins.kind == HIRKind.JUMP:
        _emit_jump(ctx, ins)
    elif ins.kind == HIRKind.BRANCH_TRUE:
        _emit_branch_true(ctx, ins)
    elif ins.kind == HIRKind.BRANCH_READY:
        _emit_branch_ready(ctx, ins)
    elif ins.kind == HIRKind.STRUCT_NEW:
        _emit_struct_new(ctx, ins)
    elif ins.kind == HIRKind.FIELD_GET:
        _emit_field_get(ctx, ins)
    elif ins.kind == HIRKind.FIELD_SET:
        _emit_field_set(ctx, ins)
    elif ins.kind == HIRKind.ARRAY_NEW:
        _emit_array_new(ctx, ins)
    elif ins.kind == HIRKind.ARRAY_GET:
        _emit_array_get(ctx, ins)
    elif ins.kind == HIRKind.ARRAY_SET:
        _emit_array_set(ctx, ins)
    elif ins.kind == HIRKind.PTR_ADDR:
        _emit_ptr_addr(ctx, ins)
    elif ins.kind == HIRKind.PTR_LOAD:
        _emit_ptr_load(ctx, ins)
    elif ins.kind == HIRKind.PTR_STORE:
        _emit_ptr_store(ctx, ins)
    elif ins.kind == HIRKind.SPAWN:
        ctx.body.append("    ; SPAWN: native build is single-threaded; ignored")
    elif ins.kind == HIRKind.LABEL:
        # Block boundaries are emitted at block-level; HIR inline LABELs
        # in MIR shouldn't appear, but tolerate gracefully.
        if ins.target:
            ctx.body.append(f".L_{ctx.fn.name}_{ins.target}:")


def _build_function(
    fn: MIRFunction,
    layouts: dict[str, list[str]],
    rodata: _RodataPool,
    signatures: dict[str, tuple[list[str], str]],
) -> list[str]:
    slot_types = _compute_slot_types(fn)
    _, fn_ret_ty = signatures.get(fn.name, ([], "i64"))
    ctx = _FunctionContext(
        fn=fn,
        layouts=layouts,
        rodata=rodata,
        signatures=signatures,
        slot_types=slot_types,
        fn_ret_type=fn_ret_ty,
    )
    ctx.epilogue = f".L_{fn.name}_epilogue"

    for label in fn.order:
        block = fn.blocks.get(label)
        if block is None:
            continue
        ctx.body.append(f".L_{fn.name}_{label}:")
        for ins in block.instrs:
            _emit_instr(ctx, ins)

    # Ensure every path falls through to epilogue.
    if _is_float(ctx.fn_ret_type):
        ctx.body.append("    xorpd xmm0, xmm0")
    else:
        ctx.body.append("    xor rax, rax")
    ctx.body.append(f"    jmp {ctx.epilogue}")

    n_slots = len(ctx.slots)
    extra_args_bytes = 8 * ctx.max_outgoing_stack_args
    frame = 8 * n_slots + 32 + extra_args_bytes
    if frame % 16 != 0:
        frame += 16 - (frame % 16)

    sym = asm_name(fn.name)
    asm: list[str] = []
    asm.append(f"    .globl {sym}")
    asm.append(f"    .def    {sym};    .scl 2;    .type 32;    .endef")
    asm.append(f"{sym}:")
    asm.append("    push rbp")
    asm.append("    mov rbp, rsp")
    if frame:
        asm.append(f"    sub rsp, {frame}")
    asm.extend(ctx.body)
    asm.append(f"{ctx.epilogue}:")
    asm.append("    mov rsp, rbp")
    asm.append("    pop rbp")
    asm.append("    ret")
    return asm


def emit_function(fn: MIRFunction, alloc: dict[str, str | None] | None = None,
                  layouts: dict[str, list[str]] | None = None,
                  signatures: dict[str, tuple[list[str], str]] | None = None) -> str:
    """Emit a single function as a self-contained chunk of GAS Intel asm.

    `alloc` is accepted for compatibility with the linear-scan pipeline
    in compile_source but is intentionally ignored: the real backend
    uses pure stack allocation so values trivially survive arbitrary
    `call` instructions without spill bookkeeping. Used at module level
    only for inspection; real builds go through emit_module.
    """
    rodata = _RodataPool()
    sigs = signatures or {fn.name: ([], "i64")}
    body = _build_function(fn, layouts or {}, rodata, sigs)
    out = ["    .intel_syntax noprefix", "    .text"] + body
    out.extend(rodata.render())
    return "\n".join(out) + "\n"


def emit_module(mod: MIRModule) -> str:
    """Emit the full module as one Win64 assembly translation unit.

    Output is written to `out/<source>.s` and fed to gcc/as/ld via
    `nexa.backend.build`.
    """
    layouts = mod.struct_layouts
    signatures = _compute_signatures(mod)
    rodata = _RodataPool()
    parts: list[str] = ["    .intel_syntax noprefix", "    .text"]
    for fn in mod.functions:
        parts.extend(_build_function(fn, layouts, rodata, signatures))
        parts.append("")
    parts.extend(rodata.render())
    return "\n".join(parts).rstrip() + "\n"
