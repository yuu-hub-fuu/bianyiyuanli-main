from __future__ import annotations

import json
import math
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from nexa.ir.hir import HIRKind, HIRModule
from nexa.runtime import rt_core


@dataclass(slots=True)
class VMResult:
    return_value: object
    stdout: list[str]


@dataclass(slots=True)
class VMFrame:
    fn: str
    ip: int
    instr: str
    env: dict[str, object]
    stdout: list[str]


class HIRVM:
    def __init__(self, module: HIRModule, runtime_root: str | Path | None = None, argv: list[str] | None = None, allow_process_exit: bool = False) -> None:
        self.module = {f.name: f for f in module.functions}
        self.output: list[str] = []
        self.runtime_root = Path(runtime_root or Path.cwd()).resolve()
        self.argv = list(argv or [])
        self.allow_process_exit = allow_process_exit
        self.exit_code: int | None = None

    def run(self, entry: str = "main") -> VMResult:
        ret = self._call(entry, [])
        return VMResult(ret if ret is not None else 0, self.output)

    def run_with_trace(self, entry: str = "main", max_steps: int = 10000) -> tuple[VMResult, list[VMFrame]]:
        trace: list[VMFrame] = []
        ret = self._call(entry, [], trace, max_steps)
        return VMResult(ret if ret is not None else 0, self.output), trace

    def _safe_path(self, raw: object) -> Path:
        path = Path(str(raw))
        if not path.is_absolute():
            path = self.runtime_root / path
        path = path.resolve()
        try:
            path.relative_to(self.runtime_root)
        except ValueError as exc:
            raise RuntimeError(f"path escapes runtime root: {path}") from exc
        return path

    def _stdlib_call(self, name: str, args: list[object]) -> object:
        if name in {"fs.read_file", "io.read_file"}:
            return self._safe_path(args[0]).read_text(encoding="utf-8")
        if name in {"fs.write_file", "io.write_file"}:
            path = self._safe_path(args[0])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(args[1]), encoding="utf-8")
            return 0
        if name in {"fs.append_file", "io.append_file"}:
            path = self._safe_path(args[0])
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(str(args[1]))
            return 0
        if name in {"fs.exists", "io.exists"}:
            return int(self._safe_path(args[0]).exists())
        if name in {"fs.is_dir", "io.is_dir"}:
            return int(self._safe_path(args[0]).is_dir())
        if name in {"fs.mkdir", "io.mkdir"}:
            self._safe_path(args[0]).mkdir(parents=True, exist_ok=True)
            return 0
        if name in {"fs.read_dir", "io.read_dir"}:
            return sorted(p.name for p in self._safe_path(args[0]).iterdir())
        if name in {"fs.remove", "io.remove"}:
            path = self._safe_path(args[0])
            if path.is_dir():
                path.rmdir()
            elif path.exists():
                path.unlink()
            return 0

        if name == "os.getenv":
            return os.environ.get(str(args[0]), "")
        if name == "os.setenv":
            os.environ[str(args[0])] = str(args[1])
            return 0
        if name == "os.exit":
            code = int(args[0])
            self.exit_code = code
            if self.allow_process_exit:
                raise SystemExit(code)
            return 0
        if name in {"os.sleep", "time.sleep"}:
            time.sleep(min(max(int(args[0]), 0), 10000) / 1000.0)
            return 0
        if name == "os.args":
            return list(self.argv)
        if name == "os.getcwd":
            return str(self.runtime_root)
        if name == "os.chdir":
            path = self._safe_path(args[0])
            if not path.is_dir():
                raise RuntimeError(f"not a directory: {path}")
            self.runtime_root = path
            return 0

        if name == "math.abs":
            return abs(int(args[0]))
        if name == "math.max":
            return max(int(args[0]), int(args[1]))
        if name == "math.min":
            return min(int(args[0]), int(args[1]))
        if name == "math.pow":
            return math.pow(float(args[0]), float(args[1]))
        if name == "math.sqrt":
            return math.sqrt(float(args[0]))
        if name == "math.sin":
            return math.sin(float(args[0]))
        if name == "math.cos":
            return math.cos(float(args[0]))
        if name == "math.floor":
            return math.floor(float(args[0]))
        if name == "math.ceil":
            return math.ceil(float(args[0]))
        if name == "math.random":
            return random.random()

        if name == "str.len":
            return len(str(args[0]))
        if name == "str.concat":
            return str(args[0]) + str(args[1])
        if name == "str.contains":
            return int(str(args[1]) in str(args[0]))
        if name == "str.starts_with":
            return int(str(args[0]).startswith(str(args[1])))
        if name == "str.ends_with":
            return int(str(args[0]).endswith(str(args[1])))
        if name == "str.split":
            return str(args[0]).split(str(args[1]))
        if name == "str.join":
            return str(args[1]).join(str(x) for x in args[0])
        if name == "str.replace":
            return str(args[0]).replace(str(args[1]), str(args[2]))
        if name == "str.substr":
            start = int(args[1])
            end = start + int(args[2])
            return str(args[0])[start:end]
        if name == "str.trim":
            return str(args[0]).strip()
        if name == "str.to_upper":
            return str(args[0]).upper()
        if name == "str.to_lower":
            return str(args[0]).lower()
        if name == "str.parse_i32":
            return int(str(args[0]))
        if name == "str.parse_f64":
            return float(str(args[0]))
        if name == "str.format_i32":
            return str(int(args[0]))
        if name == "str.format_f64":
            return str(float(args[0]))

        if name in {"array.len", "collections.len"}:
            return len(args[0]) if isinstance(args[0], list) else 0
        if name in {"array.push", "collections.push"}:
            return list(args[0]) + [args[1]] if isinstance(args[0], list) else [args[1]]
        if name in {"array.pop", "collections.pop"}:
            if not isinstance(args[0], list) or not args[0]:
                raise RuntimeError("pop from empty array")
            return args[0][-1]
        if name in {"array.index_of", "collections.index_of"}:
            if not isinstance(args[0], list):
                return -1
            try:
                return args[0].index(args[1])
            except ValueError:
                return -1
        if name in {"array.contains", "collections.contains"}:
            return int(isinstance(args[0], list) and args[1] in args[0])
        if name in {"array.sort", "collections.sort"}:
            return sorted(args[0]) if isinstance(args[0], list) else []
        if name in {"array.reverse", "collections.reverse"}:
            return list(reversed(args[0])) if isinstance(args[0], list) else []
        if name in {"array.slice", "collections.slice"}:
            return list(args[0])[int(args[1]) : int(args[2])] if isinstance(args[0], list) else []
        if name in {"array.map", "collections.map"}:
            arr = list(args[0]) if isinstance(args[0], list) else []
            return [self._call_value(args[1], [item]) for item in arr]
        if name in {"array.filter", "collections.filter"}:
            arr = list(args[0]) if isinstance(args[0], list) else []
            return [item for item in arr if self._call_value(args[1], [item])]
        if name in {"array.reduce", "collections.reduce"}:
            arr = list(args[0]) if isinstance(args[0], list) else []
            acc = args[1]
            for item in arr:
                acc = self._call_value(args[2], [acc, item])
            return acc

        if name == "time.now_ms":
            return time.time_ns() // 1_000_000
        if name == "time.now_ns":
            return time.time_ns()
        if name == "time.format_iso":
            return datetime.fromtimestamp(int(args[0]) / 1000.0, tz=timezone.utc).isoformat()

        if name == "json.parse":
            return json.loads(str(args[0]))
        if name == "json.stringify":
            return json.dumps(args[0], ensure_ascii=False, separators=(",", ":"))

        if name.startswith("net."):
            raise RuntimeError(f"{name} is disabled in the safe VM")

        if name == "testing.assert_eq":
            if args[0] != args[1]:
                raise AssertionError(f"assert_eq failed: {args[0]} != {args[1]}")
            return 0
        if name == "testing.assert_true":
            if not bool(args[0]):
                raise AssertionError("assert_true failed")
            return 0
        if name == "testing.assert_false":
            if bool(args[0]):
                raise AssertionError("assert_false failed")
            return 0
        if name == "testing.assert_panic":
            raise RuntimeError("assert_panic needs function values, which are not implemented yet")

        raise KeyError(name)

    def _call_value(self, value: object, args: list[object], trace: list[VMFrame] | None = None, max_steps: int = 10000) -> object:
        if isinstance(value, dict) and value.get("__closure"):
            return self._call(str(value["fn"]), list(value.get("captures", [])) + args, trace, max_steps)
        if isinstance(value, str):
            return self._call(value, args, trace, max_steps)
        raise RuntimeError(f"not callable: {value!r}")

    def _call(self, name: str, args: list[object], trace: list[VMFrame] | None = None, max_steps: int = 10000) -> object:
        if name == "print":
            self.output.append(str(args[0]))
            return 0
        if name == "panic":
            raise RuntimeError(str(args[0]))
        if name == "chan":
            return rt_core.rt_chan_new(int(args[0]))
        if name == "send":
            rt_core.rt_chan_send(args[0], args[1]); return 0
        if name == "recv":
            return rt_core.rt_chan_recv(args[0])
        if name == "select_recv":
            return rt_core.rt_select_recv([args[0]], default=args[1])

        try:
            return self._stdlib_call(name, args)
        except KeyError:
            pass

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
                if x in {"true", "True"}:
                    return 1
                if x in {"false", "False"}:
                    return 0
                try:
                    return int(x)
                except Exception:
                    try:
                        return float(x)
                    except Exception:
                        return x

            if op == HIRKind.PARAM:
                ip += 1; continue
            if op == HIRKind.CONST and ins.dst and ins.args:
                if ins.ty == "f64":
                    env[ins.dst] = float(ins.args[0])
                elif ins.ty == "bool":
                    env[ins.dst] = 0 if ins.args[0] in {"0", "false", "False"} else 1
                else:
                    env[ins.dst] = val(ins.args[0])
            elif op == HIRKind.MOVE and ins.dst and ins.args:
                env[ins.dst] = val(ins.args[0])
            elif op == HIRKind.UNARY and ins.dst and ins.args:
                r = val(ins.args[0])
                env[ins.dst] = -float(r) if ins.ty == "f64" and ins.op == "-" else (-int(r) if ins.op == "-" else (0 if r else 1))
            elif op == HIRKind.BIN and ins.dst and len(ins.args) == 2:
                a, b = val(ins.args[0]), val(ins.args[1])
                sym = ins.op or "+"
                if ins.ty == "f64":
                    fa, fb = float(a), float(b)
                    if sym == "+": env[ins.dst] = fa + fb
                    elif sym == "-": env[ins.dst] = fa - fb
                    elif sym == "*": env[ins.dst] = fa * fb
                    elif sym == "/": env[ins.dst] = fa / fb
                    elif sym == "==": env[ins.dst] = int(fa == fb)
                    elif sym == "!=": env[ins.dst] = int(fa != fb)
                    elif sym == "<": env[ins.dst] = int(fa < fb)
                    elif sym == "<=": env[ins.dst] = int(fa <= fb)
                    elif sym == ">": env[ins.dst] = int(fa > fb)
                    elif sym == ">=": env[ins.dst] = int(fa >= fb)
                elif sym == "+" and (isinstance(a, str) or isinstance(b, str)):
                    env[ins.dst] = str(a) + str(b)
                elif sym == "+": env[ins.dst] = int(a) + int(b)
                elif sym == "-": env[ins.dst] = int(a) - int(b)
                elif sym == "*": env[ins.dst] = int(a) * int(b)
                elif sym == "/": env[ins.dst] = int(a) // int(b)
                elif sym == "%": env[ins.dst] = int(a) % int(b)
                elif sym == "==": env[ins.dst] = int(a == b)
                elif sym == "!=": env[ins.dst] = int(a != b)
                elif sym == "<": env[ins.dst] = int(int(a) < int(b))
                elif sym == "<=": env[ins.dst] = int(int(a) <= int(b))
                elif sym == ">": env[ins.dst] = int(int(a) > int(b))
                elif sym == ">=": env[ins.dst] = int(int(a) >= int(b))
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
            elif op == HIRKind.ARRAY_NEW and ins.dst:
                env[ins.dst] = [val(a) for a in ins.args]
            elif op == HIRKind.ARRAY_GET and ins.dst and len(ins.args) == 2:
                arr = val(ins.args[0])
                idx = int(val(ins.args[1]))
                env[ins.dst] = arr[idx] if isinstance(arr, list) else 0
            elif op == HIRKind.ARRAY_SET and len(ins.args) == 3:
                arr = val(ins.args[0])
                idx = int(val(ins.args[1]))
                if isinstance(arr, list):
                    arr[idx] = val(ins.args[2])
            elif op == HIRKind.STRUCT_NEW and ins.dst and ins.args:
                obj: dict[str, object] = {"__type": ins.args[0]}
                pairs = ins.args[1:]
                for i in range(0, len(pairs), 2):
                    if i + 1 < len(pairs):
                        obj[pairs[i]] = val(pairs[i + 1])
                env[ins.dst] = obj
            elif op == HIRKind.FIELD_GET and ins.dst and len(ins.args) == 2:
                obj = val(ins.args[0])
                env[ins.dst] = obj.get(ins.args[1], 0) if isinstance(obj, dict) else 0
            elif op == HIRKind.FIELD_SET and len(ins.args) == 3:
                obj = val(ins.args[0])
                if isinstance(obj, dict):
                    obj[ins.args[1]] = val(ins.args[2])
            elif op == HIRKind.ENUM_NEW and ins.dst and ins.args:
                env[ins.dst] = {"tag": ins.args[0], "payload": [val(a) for a in ins.args[1:]]}
            elif op == HIRKind.ENUM_TAG and ins.dst and ins.args:
                obj = val(ins.args[0])
                env[ins.dst] = obj.get("tag", "") if isinstance(obj, dict) else ""
            elif op == HIRKind.ENUM_GET and ins.dst and ins.args:
                obj = val(ins.args[0])
                idx = int(val(ins.args[1] if len(ins.args) > 1 else "0"))
                payload = obj.get("payload", []) if isinstance(obj, dict) else []
                env[ins.dst] = payload[idx] if idx < len(payload) else 0
            elif op == HIRKind.CLOSURE and ins.dst and ins.op:
                env[ins.dst] = {"__closure": True, "fn": ins.op, "captures": [val(a) for a in ins.args]}
            elif op == HIRKind.CALL_VALUE and ins.dst and ins.args:
                env[ins.dst] = self._call_value(val(ins.args[0]), [val(a) for a in ins.args[1:]], trace, max_steps)
            elif op == HIRKind.TO_STR and ins.dst and ins.args:
                env[ins.dst] = str(val(ins.args[0]))
            elif op == HIRKind.DICT_NEW and ins.dst:
                d: dict[object, object] = {}
                for i in range(0, len(ins.args), 2):
                    if i + 1 < len(ins.args):
                        d[val(ins.args[i])] = val(ins.args[i + 1])
                env[ins.dst] = d
            elif op == HIRKind.DICT_GET and ins.dst and len(ins.args) == 2:
                obj = val(ins.args[0])
                env[ins.dst] = obj.get(val(ins.args[1]), 0) if isinstance(obj, dict) else 0
            elif op == HIRKind.RANGE_NEW and ins.dst and len(ins.args) >= 3:
                env[ins.dst] = (int(val(ins.args[0])), int(val(ins.args[1])), bool(int(val(ins.args[2]))))
            elif op == HIRKind.ARRAY_SLICE and ins.dst and len(ins.args) >= 2:
                arr = val(ins.args[0])
                start = int(val(ins.args[1])) if ins.args[1] else 0
                end = int(val(ins.args[2])) if len(ins.args) > 2 and ins.args[2] else None
                env[ins.dst] = arr[start:end] if isinstance(arr, list) else []
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
