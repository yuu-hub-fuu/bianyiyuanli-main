from nexa.compiler import compile_source
from nexa.ir.hir import HIRFunction, HIRInstr, HIRKind, HIRModule
from nexa.opt.passes import run_optimizations


def _main(instrs):
    return HIRModule([HIRFunction("main", instrs)])


def test_common_subexpression_elimination_reuses_duplicate_bin():
    mod = _main(
        [
            HIRInstr(HIRKind.PARAM, dst="a", ty="i32"),
            HIRInstr(HIRKind.PARAM, dst="b", ty="i32"),
            HIRInstr(HIRKind.BIN, dst="t1", args=["a", "b"], op="+", ty="i32"),
            HIRInstr(HIRKind.BIN, dst="t2", args=["a", "b"], op="+", ty="i32"),
            HIRInstr(HIRKind.BIN, dst="t3", args=["t1", "t2"], op="+", ty="i32"),
            HIRInstr(HIRKind.RET, args=["t3"], ty="i32"),
        ]
    )
    run_optimizations(mod)
    bins = [i for i in mod.functions[0].instrs if i.kind == HIRKind.BIN and i.op == "+"]
    assert sum(i.args == ["a", "b"] for i in bins) == 1


def test_loop_invariant_code_motion_hoists_safe_temp_before_loop_header():
    instrs = [
        HIRInstr(HIRKind.PARAM, dst="a", ty="i32"),
        HIRInstr(HIRKind.PARAM, dst="b", ty="i32"),
        HIRInstr(HIRKind.CONST, dst="i", args=["0"], ty="i32"),
        HIRInstr(HIRKind.LABEL, target="loop", ty="void"),
        HIRInstr(HIRKind.CONST, dst="t_limit", args=["3"], ty="i32"),
        HIRInstr(HIRKind.BIN, dst="t_cond", args=["i", "t_limit"], op="<", ty="bool"),
        HIRInstr(HIRKind.BRANCH_TRUE, args=["t_cond"], target="body", ty="bool"),
        HIRInstr(HIRKind.JUMP, target="end", ty="void"),
        HIRInstr(HIRKind.LABEL, target="body", ty="void"),
        HIRInstr(HIRKind.BIN, dst="t_inv", args=["a", "b"], op="+", ty="i32"),
        HIRInstr(HIRKind.MOVE, dst="c", args=["t_inv"], ty="i32"),
        HIRInstr(HIRKind.CONST, dst="t_one", args=["1"], ty="i32"),
        HIRInstr(HIRKind.BIN, dst="t_next", args=["i", "t_one"], op="+", ty="i32"),
        HIRInstr(HIRKind.MOVE, dst="i", args=["t_next"], ty="i32"),
        HIRInstr(HIRKind.JUMP, target="loop", ty="void"),
        HIRInstr(HIRKind.LABEL, target="end", ty="void"),
        HIRInstr(HIRKind.RET, args=["c"], ty="i32"),
    ]
    mod = _main(instrs)
    run_optimizations(mod)
    optimized = mod.functions[0].instrs
    loop_idx = next(i for i, ins in enumerate(optimized) if ins.kind == HIRKind.LABEL and ins.target == "loop")
    inv_idx = next(i for i, ins in enumerate(optimized) if ins.dst == "t_inv")
    assert inv_idx < loop_idx


def test_strength_reduction_algebra_and_unreachable_code():
    mod = _main(
        [
            HIRInstr(HIRKind.PARAM, dst="x", ty="i32"),
            HIRInstr(HIRKind.CONST, dst="t0", args=["0"], ty="i32"),
            HIRInstr(HIRKind.BIN, dst="t1", args=["x", "t0"], op="+", ty="i32"),
            HIRInstr(HIRKind.CONST, dst="t2", args=["2"], ty="i32"),
            HIRInstr(HIRKind.BIN, dst="t3", args=["t1", "t2"], op="*", ty="i32"),
            HIRInstr(HIRKind.RET, args=["t3"], ty="i32"),
            HIRInstr(HIRKind.CONST, dst="t_dead", args=["99"], ty="i32"),
        ]
    )
    run_optimizations(mod)
    instrs = mod.functions[0].instrs
    assert not any(i.dst == "t_dead" for i in instrs)
    assert any(i.kind == HIRKind.BIN and i.op == "+" and i.args == ["x", "x"] for i in instrs)


def test_small_function_inlining_removes_call_from_caller_hir():
    src = """
fn inc(x: i32) -> i32 { return x + 1; }
fn main() -> i32 { let y: i32 = inc(41); return y; }
"""
    res = compile_source(src, mode="core", run=True)
    assert all(d.level != "error" for d in res.diagnostics)
    assert res.run_value == 42
    main = next(fn for fn in res.artifacts.hir_opt.functions if fn.name == "main")
    assert not any(i.kind == HIRKind.CALL and i.op == "inc" for i in main.instrs)


def test_x86_backend_uses_lea_shift_test_and_zeroing_idioms():
    src = """
fn scale(x: i32) -> i32 {
  let y: i32 = x * 8;
  if y != 0 { return y + 3; }
  return 0;
}
"""
    res = compile_source(src, mode="core")
    assert all(d.level != "error" for d in res.diagnostics)
    asm = res.artifacts.asm["scale"]
    assert "shl rax, 3" in asm
    assert "lea rax, [rax+3]" in asm
    assert "test rax, rax" in asm
    assert "xor rax, rax" in asm
