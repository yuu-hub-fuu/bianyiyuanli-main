from __future__ import annotations

from dataclasses import dataclass

from nexa.ir.mir import MIRFunction


@dataclass(slots=True)
class Interval:
    vreg: str
    start: int
    end: int


def compute_intervals(fn: MIRFunction) -> list[Interval]:
    pos = 0
    first: dict[str, int] = {}
    last: dict[str, int] = {}
    for label in fn.order:
        block = fn.blocks[label]
        for ins in block.instrs:
            for a in ins.args:
                if a.startswith("t") or a.isidentifier():
                    first.setdefault(a, pos)
                    last[a] = pos
            if ins.dst and (ins.dst.startswith("t") or ins.dst.isidentifier()):
                first.setdefault(ins.dst, pos)
                last[ins.dst] = pos
            pos += 1
    return [Interval(v, first[v], last[v]) for v in first]


def linear_scan(intervals: list[Interval], registers: list[str]) -> dict[str, str | None]:
    active: list[Interval] = []
    alloc: dict[str, str | None] = {}
    free = registers[:]

    def expire(cur: int) -> None:
        nonlocal active
        keep: list[Interval] = []
        for it in active:
            if it.end < cur:
                reg = alloc[it.vreg]
                if reg is not None:
                    free.append(reg)
            else:
                keep.append(it)
        active = sorted(keep, key=lambda x: x.end)

    for cur in sorted(intervals, key=lambda x: x.start):
        expire(cur.start)
        if not free:
            spill = active[-1]
            if spill.end > cur.end:
                alloc[cur.vreg] = alloc[spill.vreg]
                alloc[spill.vreg] = None
                active[-1] = cur
                active.sort(key=lambda x: x.end)
            else:
                alloc[cur.vreg] = None
        else:
            alloc[cur.vreg] = free.pop()
            active.append(cur)
            active.sort(key=lambda x: x.end)
    return alloc
