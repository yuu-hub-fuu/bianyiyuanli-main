from pathlib import Path

from nexa.backend.regalloc import Interval, linear_scan
from nexa.compiler import compile_source
from nexa.runtime.rt_core import rt_chan_new, rt_chan_recv, rt_chan_send


def test_linear_scan_with_spill():
    intervals = [Interval('a', 0, 10), Interval('b', 1, 9), Interval('c', 2, 8)]
    alloc = linear_scan(intervals, ['r1', 'r2'])
    assert sum(v is None for v in alloc.values()) >= 1


def test_channel_send_recv():
    ch = rt_chan_new(1)
    rt_chan_send(ch, 42)
    assert rt_chan_recv(ch) == 42


def test_core_and_full_mode_and_graph_export(tmp_path: Path):
    src = 'fn main() -> i32 { let a: i32 = 1 + 2 * 3; return a; }'
    core = compile_source(src, mode='core', export_dir=str(tmp_path))
    full = compile_source(src, mode='full', export_dir=str(tmp_path))
    assert any(s.name == 'MacroExpand' for s in core.timeline)
    assert any(s.name == 'Backend' for s in full.timeline)
    assert (tmp_path / 'ast.dot').exists()
    assert any(p.name.startswith('cfg_') and p.suffix == '.dot' for p in tmp_path.iterdir())
