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
    if ty == "f64":
        return "double"
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
        "declare void @rt_print_i32(i32)",
        "declare void @rt_print_f64(double)",
        "declare void @rt_print_str(i8*)",
        "declare i32 @rt_str_len(i8*)",
        "declare i8* @rt_str_clone(i8*)",
        "declare i8* @rt_str_cat(i8*, i8*)",
        "declare i8* @rt_str_remove(i8*, i8*)",
        "declare i8* @rt_substr(i8*, i32, i32)",
        "declare i32 @rt_find(i8*, i8*)",
        "declare i32 @rt_contains(i8*, i8*)",
        "declare i32 @rt_starts_with(i8*, i8*)",
        "declare i32 @rt_ends_with(i8*, i8*)",
        "declare i8* @rt_replace(i8*, i8*, i8*)",
        "declare i8* @rt_trim(i8*)",
        "declare i8* @rt_lower(i8*)",
        "declare i8* @rt_upper(i8*)",
        "declare i32 @rt_ord(i8*)",
        "declare i8* @rt_chr(i32)",
        "declare i32 @rt_parse_i32(i8*)",
        "declare double @rt_parse_f64(i8*)",
        "declare i8* @rt_to_str_i32(i32)",
        "declare i8* @rt_to_str_f64(double)",
        "declare i32 @rt_to_i32_str(i8*)",
        "declare i8* @rt_min_str(i8*, i8*)",
        "declare i8* @rt_max_str(i8*, i8*)",
        "declare i32 @rt_rand()",
        "declare void @rt_srand(i32)",
        "declare i32 @rt_rand_range(i32, i32)",
        "declare i32 @rt_time()",
        "declare i32 @rt_clock()",
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
                try:
                    float(name)
                except ValueError:
                    return _Value(f"%{name}", "i32")
                if "." in name or "e" in name.lower():
                    return _Value(name, "double")
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
                    elif ins.ty == "f64":
                        name = fresh(ins.dst)
                        lines.append(f"  {name} = fadd double 0.0, {ins.args[0]}")
                        store(ins.dst, _Value(name, "double"), lines)
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
                    if op in {"+", "-"} and ins.ty == "str":
                        name = fresh(ins.dst)
                        target = "rt_str_cat" if op == "+" else "rt_str_remove"
                        lines.append(f"  {name} = call i8* @{target}(i8* {a.text}, i8* {b.text})")
                        store(ins.dst, _Value(name, "i8*"), lines)
                    elif op in {"+", "-", "*", "/"} and (a.ty == "double" or b.ty == "double"):
                        opcode = {"+": "fadd", "-": "fsub", "*": "fmul", "/": "fdiv"}[op]
                        name = fresh(ins.dst)
                        lines.append(f"  {name} = {opcode} double {a.text}, {b.text}")
                        store(ins.dst, _Value(name, "double"), lines)
                    elif op in {"==", "!=", "<", "<=", ">", ">="} and (a.ty == "double" or b.ty == "double"):
                        cmp = {"==": "oeq", "!=": "one", "<": "olt", "<=": "ole", ">": "ogt", ">=": "oge"}[op]
                        cmp_name = fresh(f"cmp_{ins.dst}")
                        name = fresh(ins.dst)
                        lines.append(f"  {cmp_name} = fcmp {cmp} double {a.text}, {b.text}")
                        lines.append(f"  {name} = zext i1 {cmp_name} to i32")
                        store(ins.dst, _Value(name, "i32"), lines)
                    elif op in {"+", "-", "*", "/", "%"}:
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
                    elif ins.op == "print":
                        arg = call_args[0] if call_args else _Value("0", "i32")
                        if arg.ty == "i8*":
                            lines.append(f"  call void @rt_print_str(i8* {arg.text})")
                        elif arg.ty == "double":
                            lines.append(f"  call void @rt_print_f64(double {arg.text})")
                        else:
                            lines.append(f"  call void @rt_print_i32(i32 {as_i32(arg, lines, ins.dst or 'print')})")
                        if ins.dst:
                            name = fresh(ins.dst)
                            lines.append(f"  {name} = add i32 0, 0")
                            store(ins.dst, _Value(name, "i32"), lines)
                    elif ins.op == "len" and call_args and call_args[0].ty == "i8*":
                        if ins.dst:
                            name = fresh(ins.dst)
                            lines.append(f"  {name} = call i32 @rt_str_len(i8* {call_args[0].text})")
                            store(ins.dst, _Value(name, "i32"), lines)
                    elif ins.op in {"cat", "find", "contains", "starts_with", "ends_with"}:
                        a0 = call_args[0] if call_args else add_string("")
                        a1 = call_args[1] if len(call_args) > 1 else add_string("")
                        ret_ty = "i8*" if ins.op == "cat" else "i32"
                        target = {"cat": "rt_str_cat", "find": "rt_find", "contains": "rt_contains", "starts_with": "rt_starts_with", "ends_with": "rt_ends_with"}[ins.op]
                        if ins.dst:
                            name = fresh(ins.dst)
                            lines.append(f"  {name} = call {ret_ty} @{target}(i8* {a0.text}, i8* {a1.text})")
                            store(ins.dst, _Value(name, ret_ty), lines)
                    elif ins.op in {"substr", "replace"}:
                        if ins.op == "substr":
                            a0 = call_args[0] if call_args else add_string("")
                            start = as_i32(call_args[1], lines, ins.dst or "substr") if len(call_args) > 1 else "0"
                            count = as_i32(call_args[2], lines, ins.dst or "substr") if len(call_args) > 2 else "0"
                            args_text = f"i8* {a0.text}, i32 {start}, i32 {count}"
                            target = "rt_substr"
                        else:
                            a0 = call_args[0] if call_args else add_string("")
                            a1 = call_args[1] if len(call_args) > 1 else add_string("")
                            a2 = call_args[2] if len(call_args) > 2 else add_string("")
                            args_text = f"i8* {a0.text}, i8* {a1.text}, i8* {a2.text}"
                            target = "rt_replace"
                        if ins.dst:
                            name = fresh(ins.dst)
                            lines.append(f"  {name} = call i8* @{target}({args_text})")
                            store(ins.dst, _Value(name, "i8*"), lines)
                    elif ins.op in {"trim", "lower", "upper"}:
                        arg = call_args[0] if call_args else add_string("")
                        target = {"trim": "rt_trim", "lower": "rt_lower", "upper": "rt_upper"}[ins.op]
                        if ins.dst:
                            name = fresh(ins.dst)
                            lines.append(f"  {name} = call i8* @{target}(i8* {arg.text})")
                            store(ins.dst, _Value(name, "i8*"), lines)
                    elif ins.op in {"ord", "parse_i32", "parse_f64"}:
                        arg = call_args[0] if call_args else add_string("")
                        if ins.dst:
                            name = fresh(ins.dst)
                            if ins.op == "parse_f64":
                                lines.append(f"  {name} = call double @rt_parse_f64(i8* {arg.text})")
                                store(ins.dst, _Value(name, "double"), lines)
                            else:
                                target = "rt_ord" if ins.op == "ord" else "rt_parse_i32"
                                lines.append(f"  {name} = call i32 @{target}(i8* {arg.text})")
                                store(ins.dst, _Value(name, "i32"), lines)
                    elif ins.op == "chr":
                        arg = as_i32(call_args[0], lines, ins.dst or "chr") if call_args else "0"
                        if ins.dst:
                            name = fresh(ins.dst)
                            lines.append(f"  {name} = call i8* @rt_chr(i32 {arg})")
                            store(ins.dst, _Value(name, "i8*"), lines)
                    elif ins.op in {"str", "to_str"}:
                        arg = call_args[0] if call_args else _Value("0", "i32")
                        if ins.dst:
                            name = fresh(ins.dst)
                            if arg.ty == "i8*":
                                lines.append(f"  {name} = call i8* @rt_str_clone(i8* {arg.text})")
                            elif arg.ty == "double":
                                lines.append(f"  {name} = call i8* @rt_to_str_f64(double {arg.text})")
                            else:
                                lines.append(f"  {name} = call i8* @rt_to_str_i32(i32 {as_i32(arg, lines, ins.dst)})")
                            store(ins.dst, _Value(name, "i8*"), lines)
                    elif ins.op in {"int", "to_i32"}:
                        arg = call_args[0] if call_args else _Value("0", "i32")
                        if ins.dst:
                            name = fresh(ins.dst)
                            if arg.ty == "i8*":
                                lines.append(f"  {name} = call i32 @rt_to_i32_str(i8* {arg.text})")
                            elif arg.ty == "double":
                                lines.append(f"  {name} = fptosi double {arg.text} to i32")
                            else:
                                lines.append(f"  {name} = add i32 0, {as_i32(arg, lines, ins.dst)}")
                            store(ins.dst, _Value(name, "i32"), lines)
                    elif ins.op in {"float", "to_f64"}:
                        arg = call_args[0] if call_args else _Value("0", "i32")
                        if ins.dst:
                            name = fresh(ins.dst)
                            if arg.ty == "i8*":
                                lines.append(f"  {name} = call double @rt_parse_f64(i8* {arg.text})")
                            elif arg.ty == "double":
                                lines.append(f"  {name} = fadd double 0.0, {arg.text}")
                            else:
                                lines.append(f"  {name} = sitofp i32 {as_i32(arg, lines, ins.dst)} to double")
                            store(ins.dst, _Value(name, "double"), lines)
                    elif ins.op in {"bool", "to_bool"}:
                        arg = call_args[0] if call_args else _Value("0", "i32")
                        if ins.dst:
                            name = fresh(ins.dst)
                            if arg.ty == "i8*":
                                parsed = fresh(f"{ins.dst}_parsed")
                                lines.append(f"  {parsed} = call i32 @rt_to_i32_str(i8* {arg.text})")
                                lines.append(f"  {name} = icmp ne i32 {parsed}, 0")
                            elif arg.ty == "double":
                                lines.append(f"  {name} = fcmp one double {arg.text}, 0.0")
                            else:
                                lines.append(f"  {name} = icmp ne i32 {as_i32(arg, lines, ins.dst)}, 0")
                            store(ins.dst, _Value(name, "i1"), lines)
                    elif ins.op in {"abs", "min", "max"}:
                        if ins.dst:
                            name = fresh(ins.dst)
                            if ins.op == "abs":
                                arg_value = call_args[0] if call_args else _Value("0", "i32")
                                neg = fresh(f"{ins.dst}_neg")
                                cond = fresh(f"{ins.dst}_negcond")
                                if arg_value.ty == "double":
                                    lines.append(f"  {neg} = fsub double 0.0, {arg_value.text}")
                                    lines.append(f"  {cond} = fcmp olt double {arg_value.text}, 0.0")
                                    lines.append(f"  {name} = select i1 {cond}, double {neg}, double {arg_value.text}")
                                    store(ins.dst, _Value(name, "double"), lines)
                                    arg_stack.clear()
                                    i += 1
                                    continue
                                arg = as_i32(arg_value, lines, ins.dst)
                                lines.append(f"  {neg} = sub i32 0, {arg}")
                                lines.append(f"  {cond} = icmp slt i32 {arg}, 0")
                                lines.append(f"  {name} = select i1 {cond}, i32 {neg}, i32 {arg}")
                            elif call_args and call_args[0].ty == "i8*":
                                a0 = call_args[0]
                                a1 = call_args[1] if len(call_args) > 1 else add_string("")
                                target = "rt_min_str" if ins.op == "min" else "rt_max_str"
                                lines.append(f"  {name} = call i8* @{target}(i8* {a0.text}, i8* {a1.text})")
                                store(ins.dst, _Value(name, "i8*"), lines)
                                arg_stack.clear()
                                i += 1
                                continue
                            elif call_args and call_args[0].ty == "double":
                                a0 = call_args[0].text
                                a1 = call_args[1].text if len(call_args) > 1 else "0.0"
                                cond = fresh(f"{ins.dst}_cmp")
                                cmp = "olt" if ins.op == "min" else "ogt"
                                lines.append(f"  {cond} = fcmp {cmp} double {a0}, {a1}")
                                lines.append(f"  {name} = select i1 {cond}, double {a0}, double {a1}")
                                store(ins.dst, _Value(name, "double"), lines)
                                arg_stack.clear()
                                i += 1
                                continue
                            else:
                                a0 = as_i32(call_args[0], lines, ins.dst + "_a") if call_args else "0"
                                a1 = as_i32(call_args[1], lines, ins.dst + "_b") if len(call_args) > 1 else "0"
                                cond = fresh(f"{ins.dst}_cmp")
                                cmp = "slt" if ins.op == "min" else "sgt"
                                lines.append(f"  {cond} = icmp {cmp} i32 {a0}, {a1}")
                                lines.append(f"  {name} = select i1 {cond}, i32 {a0}, i32 {a1}")
                            store(ins.dst, _Value(name, "i32"), lines)
                    elif ins.op in {"rand", "time", "clock"}:
                        if ins.dst:
                            name = fresh(ins.dst)
                            target = {"rand": "rt_rand", "time": "rt_time", "clock": "rt_clock"}[ins.op]
                            lines.append(f"  {name} = call i32 @{target}()")
                            store(ins.dst, _Value(name, "i32"), lines)
                    elif ins.op == "srand":
                        seed = as_i32(call_args[0], lines, ins.dst or "srand") if call_args else "0"
                        lines.append(f"  call void @rt_srand(i32 {seed})")
                        if ins.dst:
                            name = fresh(ins.dst)
                            lines.append(f"  {name} = add i32 0, 0")
                            store(ins.dst, _Value(name, "i32"), lines)
                    elif ins.op == "rand_range":
                        lo = as_i32(call_args[0], lines, ins.dst or "rand_range") if call_args else "0"
                        hi = as_i32(call_args[1], lines, ins.dst or "rand_range") if len(call_args) > 1 else "0"
                        if ins.dst:
                            name = fresh(ins.dst)
                            lines.append(f"  {name} = call i32 @rt_rand_range(i32 {lo}, i32 {hi})")
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
