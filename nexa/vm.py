from __future__ import annotations

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
                    return x

            if op == HIRKind.PARAM:
                ip += 1; continue
            if op == HIRKind.CONST and ins.dst and ins.args:
                env[ins.dst] = val(ins.args[0])
            elif op == HIRKind.MOVE and ins.dst and ins.args:
                env[ins.dst] = val(ins.args[0])
            elif op == HIRKind.UNARY and ins.dst and ins.args:
                r = int(val(ins.args[0]))
                env[ins.dst] = -r if ins.op == "-" else (0 if r else 1)
            elif op == HIRKind.BIN and ins.dst and len(ins.args) == 2:
                a, b = val(ins.args[0]), val(ins.args[1])
                sym = ins.op or "+"
                if sym == "+": env[ins.dst] = int(a) + int(b)
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
