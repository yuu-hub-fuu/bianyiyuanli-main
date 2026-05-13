from __future__ import annotations

import copy
import random
import time
from dataclasses import dataclass

from nexa.ir.hir import HIRKind, HIRModule
from nexa.runtime import rt_core


@dataclass(slots=True)
class VMResult:
    return_value: int
    stdout: list[str]


@dataclass(slots=True)
class VMFrame:
    fn: str
    ip: int
    instr: str
    env: dict[str, object]
    stdout: list[str]


class HIRVM:
    def __init__(self, module: HIRModule) -> None:
        self.module = {f.name: f for f in module.functions}
        self.virtual_methods = module.virtual_methods
        self.destructors = module.destructors
        self.class_bases = module.class_bases
        self.class_by_id = {v: k for k, v in module.class_ids.items()}
        self.output: list[str] = []

    def run(self, entry: str = "main") -> VMResult:
        ret = self._call(entry, [])
        return VMResult(int(ret or 0), self.output)

    def run_with_trace(self, entry: str = "main", max_steps: int = 10000) -> tuple[VMResult, list[VMFrame]]:
        trace: list[VMFrame] = []
        ret = self._call(entry, [], trace, max_steps)
        return VMResult(int(ret or 0), self.output), trace

    def _call(self, name: str, args: list[object], trace: list[VMFrame] | None = None, max_steps: int = 10000) -> object:
        if name == "print":
            self.output.append(str(args[0]))
            return 0
        if name == "read_i32":
            return int(input())
        if name == "read_f64":
            return float(input())
        if name == "read_str":
            return input()
        if name == "len":
            return len(args[0])
        if name == "panic":
            raise RuntimeError(str(args[0]))
        if name in {"str", "to_str"}:
            v = args[0]
            if isinstance(v, bool):
                return "true" if v else "false"
            return str(v)
        if name in {"int", "to_i32"}:
            return int(float(args[0])) if isinstance(args[0], str) else int(args[0])
        if name in {"float", "to_f64"}:
            return float(args[0])
        if name in {"bool", "to_bool"}:
            v = args[0]
            if isinstance(v, str):
                return 0 if v == "" or v.lower() in {"0", "false"} else 1
            return 1 if bool(v) else 0
        if name == "cat":
            return str(args[0]) + str(args[1])
        if name == "strlen":
            return len(str(args[0]))
        if name == "substr":
            s = str(args[0]); start = max(0, int(args[1])); n = max(0, int(args[2]))
            return s[start:start + n]
        if name == "find":
            return str(args[0]).find(str(args[1]))
        if name == "contains":
            return 1 if str(args[1]) in str(args[0]) else 0
        if name == "starts_with":
            return 1 if str(args[0]).startswith(str(args[1])) else 0
        if name == "ends_with":
            return 1 if str(args[0]).endswith(str(args[1])) else 0
        if name == "replace":
            return str(args[0]).replace(str(args[1]), str(args[2]))
        if name == "trim":
            return str(args[0]).strip()
        if name == "lower":
            return str(args[0]).lower()
        if name == "upper":
            return str(args[0]).upper()
        if name == "ord":
            s = str(args[0])
            return ord(s[0]) if s else 0
        if name == "chr":
            return chr(int(args[0]))
        if name == "parse_i32":
            return int(float(str(args[0]).strip()))
        if name == "parse_f64":
            return float(str(args[0]).strip())
        if name == "rand":
            return random.randint(0, 2_147_483_647)
        if name == "srand":
            random.seed(int(args[0])); return 0
        if name == "rand_range":
            lo, hi = int(args[0]), int(args[1])
            if hi < lo:
                lo, hi = hi, lo
            return random.randint(lo, hi)
        if name == "time":
            return int(time.time())
        if name == "clock":
            return int(time.process_time() * 1000)
        if name == "abs":
            return abs(args[0])
        if name == "min":
            return args[0] if args[0] <= args[1] else args[1]
        if name == "max":
            return args[0] if args[0] >= args[1] else args[1]
        if name == "ptr_new":
            return {"value": args[0]}
        if name == "ptr_get":
            ref = args[0]
            if isinstance(ref, dict) and "env" in ref:
                return ref["env"][ref["name"]]
            return ref["value"]
        if name == "ptr_set":
            ref = args[0]
            if isinstance(ref, dict) and "env" in ref:
                ref["env"][ref["name"]] = args[1]
            else:
                ref["value"] = args[1]
            return 0
        if name in {"copy", "clone", "shallow_copy"}:
            return copy.copy(args[0])
        if name == "deep_copy":
            return copy.deepcopy(args[0])
        if name == "chan":
            return rt_core.rt_chan_new(int(args[0]))
        if name == "send":
            rt_core.rt_chan_send(args[0], args[1]); return 0
        if name == "recv":
            return rt_core.rt_chan_recv(args[0])
        if name == "select_recv":
            return rt_core.rt_select_recv([args[0]], default=args[1])

        if name not in self.module:
            raise RuntimeError(f"VM: undefined function {name}")
        fn = self.module[name]
        env: dict[str, object] = {}
        labels: dict[str, int] = {}
        pending_args: list[object] = []

        param_names = [i.dst for i in fn.instrs if i.kind == HIRKind.PARAM and i.dst]
        for idx, p in enumerate(param_names):
            env[p] = args[idx] if idx < len(args) else 0

        for idx, ins in enumerate(fn.instrs):
            if ins.kind == HIRKind.LABEL and ins.target:
                labels[ins.target] = idx

        ip = 0
        steps = 0
        while ip < len(fn.instrs):
            ins = fn.instrs[ip]
            op = ins.kind
            if trace is not None:
                trace.append(VMFrame(name, ip, ins.kind.name, dict(env), list(self.output)))
            steps += 1
            if steps > max_steps:
                raise RuntimeError("VM: step limit exceeded")

            def val(x: str | None) -> object:
                if x is None:
                    return 0
                if x in env:
                    return env[x]
                try:
                    return int(x)
                except Exception:
                    try:
                        return float(x)
                    except Exception:
                        return x

            def num(x: object) -> int | float:
                return x if isinstance(x, float) else int(x)

            if op == HIRKind.PARAM:
                ip += 1; continue
            if op == HIRKind.CONST and ins.dst and ins.args:
                env[ins.dst] = float(ins.args[0]) if ins.ty == "f64" else val(ins.args[0])
            elif op == HIRKind.FUNC_ADDR and ins.dst and ins.args:
                env[ins.dst] = ins.args[0]
            elif op == HIRKind.MOVE and ins.dst and ins.args:
                env[ins.dst] = val(ins.args[0])
            elif op == HIRKind.STRUCT_NEW and ins.dst:
                obj: dict[str, object] = {"__struct__": ins.op or ins.ty, "__class__": ins.op or ins.ty, "__deleted__": 0}
                for i in range(0, len(ins.args), 2):
                    if i + 1 < len(ins.args):
                        key = ins.args[i]
                        got = val(ins.args[i + 1])
                        obj[key] = got
                        if key == "__class_id":
                            obj["__class__"] = self.class_by_id.get(int(got), obj["__class__"])
                env[ins.dst] = obj
            elif op == HIRKind.FIELD_GET and ins.dst and ins.args and ins.op:
                obj = val(ins.args[0])
                if not isinstance(obj, dict):
                    raise RuntimeError(f"VM: field access on non-struct value {obj!r}")
                fname = ins.op.rsplit(".", 1)[-1]
                if fname not in obj:
                    raise RuntimeError(f"VM: missing field {fname}")
                env[ins.dst] = obj[fname]
            elif op == HIRKind.FIELD_SET and len(ins.args) == 2 and ins.op:
                obj = val(ins.args[0])
                if not isinstance(obj, dict):
                    raise RuntimeError(f"VM: field assignment on non-struct value {obj!r}")
                fname = ins.op.rsplit(".", 1)[-1]
                obj[fname] = val(ins.args[1])
            elif op == HIRKind.ARRAY_NEW and ins.dst:
                env[ins.dst] = [val(a) for a in ins.args]
            elif op == HIRKind.ARRAY_GET and ins.dst and len(ins.args) == 2:
                arr = val(ins.args[0])
                if not isinstance(arr, list):
                    raise RuntimeError(f"VM: index access on non-array value {arr!r}")
                env[ins.dst] = arr[int(val(ins.args[1]))]
            elif op == HIRKind.ARRAY_SET and len(ins.args) == 3:
                arr = val(ins.args[0])
                if not isinstance(arr, list):
                    raise RuntimeError(f"VM: index assignment on non-array value {arr!r}")
                arr[int(val(ins.args[1]))] = val(ins.args[2])
            elif op == HIRKind.PTR_ADDR and ins.dst and ins.args:
                env[ins.dst] = {"env": env, "name": ins.args[0]}
            elif op == HIRKind.PTR_LOAD and ins.dst and ins.args:
                ref = val(ins.args[0])
                if isinstance(ref, dict) and "env" in ref:
                    env[ins.dst] = ref["env"][ref["name"]]
                elif isinstance(ref, dict) and "value" in ref:
                    env[ins.dst] = ref["value"]
                else:
                    raise RuntimeError(f"VM: dereference on non-pointer value {ref!r}")
            elif op == HIRKind.PTR_STORE and len(ins.args) == 2:
                ref = val(ins.args[0])
                if isinstance(ref, dict) and "env" in ref:
                    ref["env"][ref["name"]] = val(ins.args[1])
                elif isinstance(ref, dict) and "value" in ref:
                    ref["value"] = val(ins.args[1])
                else:
                    raise RuntimeError(f"VM: pointer assignment on non-pointer value {ref!r}")
            elif op == HIRKind.UNARY and ins.dst and ins.args:
                r = num(val(ins.args[0]))
                env[ins.dst] = -r if ins.op == "-" else (0 if r else 1)
            elif op == HIRKind.BIN and ins.dst and len(ins.args) == 2:
                a, b = val(ins.args[0]), val(ins.args[1])
                sym = ins.op or "+"
                if sym == "+" and isinstance(a, str) and isinstance(b, str): env[ins.dst] = a + b
                elif sym == "-" and isinstance(a, str) and isinstance(b, str): env[ins.dst] = a.replace(b, "")
                elif sym == "+": env[ins.dst] = num(a) + num(b)
                elif sym == "-": env[ins.dst] = num(a) - num(b)
                elif sym == "*": env[ins.dst] = num(a) * num(b)
                elif sym == "/": env[ins.dst] = (num(a) / num(b)) if isinstance(num(a), float) or isinstance(num(b), float) else int(a) // int(b)
                elif sym == "%": env[ins.dst] = int(a) % int(b)
                elif sym == "==": env[ins.dst] = int(a == b)
                elif sym == "!=": env[ins.dst] = int(a != b)
                elif sym == "<": env[ins.dst] = int(a < b) if isinstance(a, str) and isinstance(b, str) else int(num(a) < num(b))
                elif sym == "<=": env[ins.dst] = int(a <= b) if isinstance(a, str) and isinstance(b, str) else int(num(a) <= num(b))
                elif sym == ">": env[ins.dst] = int(a > b) if isinstance(a, str) and isinstance(b, str) else int(num(a) > num(b))
                elif sym == ">=": env[ins.dst] = int(a >= b) if isinstance(a, str) and isinstance(b, str) else int(num(a) >= num(b))
                elif sym == "&&": env[ins.dst] = int(bool(a) and bool(b))
                elif sym == "||": env[ins.dst] = int(bool(a) or bool(b))
            elif op == HIRKind.ARG and ins.args:
                pending_args.append(val(ins.args[0]))
            elif op == HIRKind.CALL and ins.op:
                call_args = pending_args
                if ins.op in {"recv", "send", "select_recv"} and ins.args:
                    call_args = [val(a) for a in ins.args]
                ret = self._call(ins.op, call_args, trace, max_steps)
                pending_args = []
                if ins.dst:
                    env[ins.dst] = ret
            elif op == HIRKind.CALL_PTR and ins.dst and ins.args:
                fn_value = val(ins.args[0])
                if not isinstance(fn_value, str):
                    raise RuntimeError(f"VM: function pointer expected, got {fn_value!r}")
                ret = self._call(fn_value, pending_args, trace, max_steps)
                pending_args = []
                env[ins.dst] = ret
            elif op == HIRKind.CALL_VIRTUAL and ins.op:
                call_args = [val(a) for a in ins.args]
                obj = call_args[0] if call_args else None
                class_name = obj.get("__class__") if isinstance(obj, dict) else None
                target = self._resolve_virtual(str(class_name), ins.op)
                ret = self._call(target, call_args, trace, max_steps)
                if ins.dst:
                    env[ins.dst] = ret
            elif op == HIRKind.DELETE_OBJECT and ins.args:
                obj = val(ins.args[0])
                if isinstance(obj, dict) and not obj.get("__deleted__"):
                    for target in self._destructor_chain(str(obj.get("__class__"))):
                        self._call(target, [obj], trace, max_steps)
                    obj["__deleted__"] = 1
            elif op == HIRKind.BRANCH_TRUE and ins.target and ins.args:
                if int(val(ins.args[0])) != 0:
                    ip = labels[ins.target]
                    continue
            elif op == HIRKind.BRANCH_READY and ins.target and ins.args:
                ch = val(ins.args[0])
                if hasattr(ch, "q") and not ch.q.empty():
                    ip = labels[ins.target]
                    continue
            elif op == HIRKind.JUMP and ins.target:
                ip = labels[ins.target]
                continue
            elif op == HIRKind.RET:
                return val(ins.args[0] if ins.args else None)
            ip += 1
        return 0

    def _resolve_virtual(self, class_name: str, method: str) -> str:
        cur: str | None = class_name
        while cur:
            found = self.virtual_methods.get(cur, {}).get(method)
            if found:
                return found
            cur = self.class_bases.get(cur)
        raise RuntimeError(f"VM: virtual method {class_name}.{method} not found")

    def _destructor_chain(self, class_name: str) -> list[str]:
        out: list[str] = []
        cur: str | None = class_name
        while cur:
            found = self.destructors.get(cur)
            if found:
                out.append(found)
            cur = self.class_bases.get(cur)
        return out


class VMDebugger:
    """Simple debugger facade over VM trace."""

    def __init__(self, module: HIRModule) -> None:
        self._vm = HIRVM(module)
        self._trace: list[VMFrame] = []
        self._idx = 0
        self._result: VMResult | None = None

    def start(self, entry: str = "main", max_steps: int = 10000) -> None:
        self._result, self._trace = self._vm.run_with_trace(entry, max_steps=max_steps)
        self._idx = 0

    def step(self) -> VMFrame | None:
        if self._idx >= len(self._trace):
            return None
        frame = self._trace[self._idx]
        self._idx += 1
        return frame

    def run(self) -> list[VMFrame]:
        if self._idx >= len(self._trace):
            return []
        rem = self._trace[self._idx :]
        self._idx = len(self._trace)
        return rem

    @property
    def result(self) -> VMResult | None:
        return self._result
