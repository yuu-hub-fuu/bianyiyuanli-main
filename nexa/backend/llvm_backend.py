from __future__ import annotations

from dataclasses import dataclass

from nexa.ir.hir import HIRInstr, HIRKind, HIRModule


_UNSUPPORTED = {
    HIRKind.SPAWN,
    HIRKind.STRUCT_NEW,
    HIRKind.FIELD_GET,
    HIRKind.FIELD_SET,
    HIRKind.ARRAY_NEW,
    HIRKind.ARRAY_GET,
    HIRKind.ARRAY_SET,
}


@dataclass(slots=True)
class _Value:
    text: str
    ty: str


def validate_llvm_subset(module: HIRModule) -> tuple[bool, str]:
    for fn in module.functions:
        for ins in fn.instrs:
            if ins.kind in _UNSUPPORTED:
                return False, f"LLVM backend rejects unsupported instruction: {ins.kind.name}"
    return True, ""


def _slot_type(ty: str) -> str:
    if ty in {"str", "Chan"} or ty.startswith("Chan"):
        return "i8*"
    return "i32"


def _param_type(ty: str) -> str:
    return _slot_type(ty)


def _label(name: str) -> str:
    return f"%{name}"


def _escape_bytes(text: str) -> tuple[str, int]:
    data = text.encode("utf-8") + b"\0"
    escaped = "".join(chr(b) if 32 <= b <= 126 and b not in {34, 92} else f"\\{b:02X}" for b in data)
    return escaped, len(data)


def _collect_blocks(instrs: list[HIRInstr]) -> list[tuple[str, list[HIRInstr]]]:
    blocks: list[tuple[str, list[HIRInstr]]] = []
    current_name = "entry"
    current: list[HIRInstr] = []
    for ins in instrs:
        if ins.kind == HIRKind.LABEL and ins.target:
            blocks.append((current_name, current))
            current_name = ins.target
            current = []
        else:
            current.append(ins)
    blocks.append((current_name, current))
    return [(name, block) for name, block in blocks if block or name == "entry"]


def emit_llvm_ir(module: HIRModule) -> str:
    string_globals: list[str] = []
    lines = [
        "; Nexa LLVM IR",
        "declare i8* @rt_chan_new(i32)",
        "declare void @rt_chan_send(i8*, i32)",
        "declare i32 @rt_chan_recv(i8*)",
        "declare i1 @rt_chan_ready(i8*)",
        "declare void @rt_panic(i8*)",
        "",
    ]

    def add_string(value: str) -> _Value:
        escaped, size = _escape_bytes(value)
        name = f"@str_{len(string_globals)}"
        string_globals.append(f'{name} = private unnamed_addr constant [{size} x i8] c"{escaped}"')
        return _Value(f"getelementptr inbounds ([{size} x i8], [{size} x i8]* {name}, i32 0, i32 0)", "i8*")

    for fn in module.functions:
        params = [i for i in fn.instrs if i.kind == HIRKind.PARAM and i.dst]
        slot_types: dict[str, str] = {p.dst: _slot_type(p.ty) for p in params if p.dst}
        for ins in fn.instrs:
            if ins.dst:
                slot_types.setdefault(ins.dst, _slot_type(ins.ty))

        value_ids: dict[str, int] = {}
        load_id = 0

        def fresh(base: str) -> str:
            value_ids[base] = value_ids.get(base, 0) + 1
            suffix = "" if value_ids[base] == 1 else f"_{value_ids[base]}"
            return f"%{base}{suffix}"

        def load(name: str, out: list[str], hint: str) -> _Value:
            nonlocal load_id
            if name in slot_types:
                load_id += 1
                ty = slot_types[name]
                tmp = f"%load_{hint}_{load_id}"
                out.append(f"  {tmp} = load {ty}, {ty}* %slot_{name}")
                return _Value(tmp, ty)
            try:
                int(name)
            except ValueError:
                return _Value(f"%{name}", "i32")
            return _Value(name, "i32")

        def as_i32(value: _Value, out: list[str], hint: str) -> str:
            if value.ty == "i1":
                tmp = fresh(f"zext_{hint}")
                out.append(f"  {tmp} = zext i1 {value.text} to i32")
                return tmp
            return value.text

        def store(dst: str | None, value: _Value, out: list[str]) -> None:
            if not dst:
                return
            ty = slot_types.get(dst, value.ty)
            if ty == value.ty:
                out.append(f"  store {ty} {value.text}, {ty}* %slot_{dst}")
            elif ty == "i32" and value.ty == "i1":
                tmp = fresh(f"{dst}_i32")
                out.append(f"  {tmp} = zext i1 {value.text} to i32")
                out.append(f"  store i32 {tmp}, i32* %slot_{dst}")

        param_decl = ", ".join(f"{_param_type(p.ty)} %{p.dst}" for p in params)
        lines.append(f"define i32 @{fn.name}({param_decl}) {{")
        blocks = _collect_blocks(fn.instrs)
        arg_stack: list[_Value] = []

        for block_index, (block_name, instrs) in enumerate(blocks):
            lines.append(f"{block_name}:")
            if block_name == "entry":
                for name, ty in slot_types.items():
                    lines.append(f"  %slot_{name} = alloca {ty}")
                for p in params:
                    if p.dst:
                        lines.append(f"  store {_param_type(p.ty)} %{p.dst}, {_param_type(p.ty)}* %slot_{p.dst}")

            next_block = blocks[block_index + 1][0] if block_index + 1 < len(blocks) else None
            terminated = False
            i = 0
            while i < len(instrs):
                ins = instrs[i]
                if ins.kind == HIRKind.PARAM:
                    i += 1
                    continue
                if ins.kind == HIRKind.CONST and ins.dst and ins.args:
                    if ins.ty == "str":
                        store(ins.dst, add_string(ins.args[0]), lines)
                    elif ins.ty == "bool":
                        name = fresh(ins.dst)
                        value = "1" if ins.args[0] not in {"0", "false", "False"} else "0"
                        lines.append(f"  {name} = add i1 0, {value}")
                        store(ins.dst, _Value(name, "i1"), lines)
                    else:
                        name = fresh(ins.dst)
                        lines.append(f"  {name} = add i32 0, {ins.args[0]}")
                        store(ins.dst, _Value(name, "i32"), lines)
                elif ins.kind == HIRKind.BIN and ins.dst and len(ins.args) == 2:
                    a = load(ins.args[0], lines, ins.dst + "_a")
                    b = load(ins.args[1], lines, ins.dst + "_b")
                    op = ins.op or "+"
                    if op in {"+", "-", "*", "/", "%"}:
                        opcode = {"+": "add", "-": "sub", "*": "mul", "/": "sdiv", "%": "srem"}[op]
                        name = fresh(ins.dst)
                        lines.append(f"  {name} = {opcode} i32 {as_i32(a, lines, ins.dst + '_a')}, {as_i32(b, lines, ins.dst + '_b')}")
                        store(ins.dst, _Value(name, "i32"), lines)
                    elif op in {"==", "!=", "<", "<=", ">", ">="}:
                        cmp = {"==": "eq", "!=": "ne", "<": "slt", "<=": "sle", ">": "sgt", ">=": "sge"}[op]
                        cmp_name = fresh(f"cmp_{ins.dst}")
                        name = fresh(ins.dst)
                        lines.append(f"  {cmp_name} = icmp {cmp} i32 {as_i32(a, lines, ins.dst + '_a')}, {as_i32(b, lines, ins.dst + '_b')}")
                        lines.append(f"  {name} = zext i1 {cmp_name} to i32")
                        store(ins.dst, _Value(name, "i32"), lines)
                    elif op in {"&&", "||"}:
                        cmp_a = fresh(f"bool_{ins.dst}_a")
                        cmp_b = fresh(f"bool_{ins.dst}_b")
                        bool_name = fresh(f"bool_{ins.dst}")
                        name = fresh(ins.dst)
                        logic = "and" if op == "&&" else "or"
                        lines.append(f"  {cmp_a} = icmp ne i32 {as_i32(a, lines, ins.dst + '_a')}, 0")
                        lines.append(f"  {cmp_b} = icmp ne i32 {as_i32(b, lines, ins.dst + '_b')}, 0")
                        lines.append(f"  {bool_name} = {logic} i1 {cmp_a}, {cmp_b}")
                        lines.append(f"  {name} = zext i1 {bool_name} to i32")
                        store(ins.dst, _Value(name, "i32"), lines)
                elif ins.kind == HIRKind.UNARY and ins.dst and ins.args:
                    src = load(ins.args[0], lines, ins.dst)
                    name = fresh(ins.dst)
                    if ins.op == "-":
                        lines.append(f"  {name} = sub i32 0, {as_i32(src, lines, ins.dst)}")
                    else:
                        tmp = fresh(f"not_{ins.dst}")
                        lines.append(f"  {tmp} = icmp eq i32 {as_i32(src, lines, ins.dst)}, 0")
                        lines.append(f"  {name} = zext i1 {tmp} to i32")
                    store(ins.dst, _Value(name, "i32"), lines)
                elif ins.kind == HIRKind.MOVE and ins.dst and ins.args:
                    store(ins.dst, load(ins.args[0], lines, ins.dst), lines)
                elif ins.kind == HIRKind.ARG and ins.args:
                    arg_stack.append(load(ins.args[0], lines, "arg"))
                elif ins.kind == HIRKind.CALL and ins.op:
                    call_args = [load(a, lines, ins.op) for a in ins.args] if ins.args else list(arg_stack)
                    if ins.op == "chan":
                        cap = as_i32(call_args[0], lines, ins.dst or "chan") if call_args else "0"
                        if ins.dst:
                            name = fresh(ins.dst)
                            lines.append(f"  {name} = call i8* @rt_chan_new(i32 {cap})")
                            store(ins.dst, _Value(name, "i8*"), lines)
                    elif ins.op == "send":
                        ch = call_args[0] if call_args else _Value("null", "i8*")
                        val = call_args[1] if len(call_args) > 1 else _Value("0", "i32")
                        lines.append(f"  call void @rt_chan_send(i8* {ch.text}, i32 {as_i32(val, lines, ins.dst or 'send')})")
                    elif ins.op == "recv":
                        ch = call_args[0] if call_args else _Value("null", "i8*")
                        if ins.dst:
                            name = fresh(ins.dst)
                            lines.append(f"  {name} = call i32 @rt_chan_recv(i8* {ch.text})")
                            store(ins.dst, _Value(name, "i32"), lines)
                    elif ins.op == "panic":
                        arg = call_args[0] if call_args else add_string("panic")
                        lines.append(f"  call void @rt_panic(i8* {arg.text})")
                        if ins.dst:
                            name = fresh(ins.dst)
                            lines.append(f"  {name} = add i32 0, 0")
                            store(ins.dst, _Value(name, "i32"), lines)
                    else:
                        args = ", ".join(f"i32 {as_i32(arg, lines, ins.dst or ins.op)}" for arg in call_args)
                        if ins.dst:
                            name = fresh(ins.dst)
                            lines.append(f"  {name} = call i32 @{ins.op}({args})")
                            store(ins.dst, _Value(name, "i32"), lines)
                        else:
                            lines.append(f"  call i32 @{ins.op}({args})")
                    arg_stack.clear()
                elif ins.kind in {HIRKind.BRANCH_TRUE, HIRKind.BRANCH_READY} and ins.target:
                    fall = None
                    if i + 1 < len(instrs) and instrs[i + 1].kind == HIRKind.JUMP and instrs[i + 1].target:
                        fall = instrs[i + 1].target
                    elif next_block:
                        fall = next_block
                    else:
                        fall = ins.target
                    if ins.kind == HIRKind.BRANCH_READY:
                        ch = load(ins.args[0], lines, block_name) if ins.args else _Value("null", "i8*")
                        cond = fresh(f"ready_{block_name}")
                        lines.append(f"  {cond} = call i1 @rt_chan_ready(i8* {ch.text})")
                    else:
                        value = load(ins.args[0], lines, block_name) if ins.args else _Value("0", "i32")
                        cond = fresh(f"br_{block_name}")
                        lines.append(f"  {cond} = icmp ne i32 {as_i32(value, lines, block_name)}, 0")
                    lines.append(f"  br i1 {cond}, label {_label(ins.target)}, label {_label(fall)}")
                    terminated = True
                    break
                elif ins.kind == HIRKind.JUMP and ins.target:
                    lines.append(f"  br label {_label(ins.target)}")
                    terminated = True
                    break
                elif ins.kind == HIRKind.RET:
                    value = load(ins.args[0], lines, block_name + "_ret") if ins.args else _Value("0", "i32")
                    lines.append(f"  ret i32 {as_i32(value, lines, block_name + '_ret')}")
                    terminated = True
                    break
                i += 1
            if not terminated:
                if next_block:
                    lines.append(f"  br label {_label(next_block)}")
                else:
                    lines.append("  ret i32 0")
        lines.append("}")
        lines.append("")

    if string_globals:
        return "\n".join(lines + string_globals) + "\n"
    return "\n".join(lines) + "\n"


def try_emit_object(_llvm_ir: str) -> bytes:
    try:
        import llvmlite.binding as llvm  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("llvmlite not installed") from exc
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()
    target = llvm.Target.from_default_triple()
    tm = target.create_target_machine()
    mod = llvm.parse_assembly(_llvm_ir)
    mod.verify()
    return tm.emit_object(mod)
