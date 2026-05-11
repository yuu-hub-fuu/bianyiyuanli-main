"""End-to-end checks for the real Win64 backend.

These tests exercise the full pipeline:
    Nexa source -> HIR -> MIR -> .s -> .o -> .exe -> CPU run

They are skipped automatically if `gcc` is not on PATH, so the suite
remains green on machines without a host toolchain.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from nexa.compiler import compile_source


pytestmark = pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc toolchain not available")


def _compile_and_run(src: str, tmp_path: Path, stem: str = "prog"):
    res = compile_source(src, mode="full", build=True, run_exe=True, build_dir=str(tmp_path), source_stem=stem)
    assert all(d.level != "error" for d in res.diagnostics), [d.message for d in res.diagnostics]
    assert res.build is not None
    assert res.build.exe_path.exists()
    return res


def test_native_arithmetic_and_print(tmp_path: Path):
    src = "fn main() -> i32 { let a: i32 = 3; let b: i32 = 4; print(a + b * 2); return a + b; }"
    res = _compile_and_run(src, tmp_path, "arith")
    assert "11" in res.exe_stdout
    assert res.exe_exit_code == 7


def test_native_factorial_while(tmp_path: Path):
    src = """
fn fact(n: i32) -> i32 {
    let r: i32 = 1;
    let i: i32 = 2;
    while i <= n { r = r * i; i = i + 1; }
    return r;
}
fn main() -> i32 { return fact(6) % 100; }
"""
    res = _compile_and_run(src, tmp_path, "fact")
    assert res.exe_exit_code == 20


def test_native_struct_array_call_and_generic(tmp_path: Path):
    src = """
struct Pair { x: i32, y: i32 }
fn add(a: i32, b: i32) -> i32 { return a + b; }
fn max[T: Ord](a: T, b: T) -> T { if a > b { return a; } return b; }
fn main() -> i32 {
    let p: Pair = Pair { x: 10, y: 20 };
    p.x = p.x + 5;
    let xs: Array[i32] = [1, 2, 3, 4];
    xs[2] = xs[0] + xs[3];
    print(xs[2]);
    return add(max(p.x, p.y), xs[2]);
}
"""
    res = _compile_and_run(src, tmp_path, "complex")
    assert "5" in res.exe_stdout.splitlines()
    assert res.exe_exit_code == 25


def test_native_panic_terminates_with_message(tmp_path: Path):
    src = 'fn main() -> i32 { panic("boom"); return 0; }'
    res = _compile_and_run(src, tmp_path, "panic")
    assert res.exe_exit_code == 1
    assert "boom" in res.exe_stderr


def test_native_emits_real_intel_syntax_asm(tmp_path: Path):
    src = "fn main() -> i32 { return 0; }"
    res = _compile_and_run(src, tmp_path, "minimal")
    text = res.build.asm_text
    assert ".intel_syntax noprefix" in text
    assert "nx_user_main:" in text
    assert "push rbp" in text
    assert "mov rbp, rsp" in text
    assert "ret" in text


def test_native_f64_arithmetic_and_polymorphic_print(tmp_path: Path):
    src = """
fn quad(a: f64, b: f64, c: f64) -> f64 { return a * b + c; }
fn main() -> i32 {
    let x: f64 = 1.5 + 2.25;
    print(x);
    let y: f64 = quad(2.0, 3.5, 0.5);
    print(y);
    if x > 3.0 { print(1); } else { print(0); }
    if y == 7.5 { return 42; }
    return 7;
}
"""
    res = _compile_and_run(src, tmp_path, "f64demo")
    # Real x86 asm uses xmm registers and sse mnemonics, not the cpu int path.
    assert "addsd" in res.build.asm_text
    assert "mulsd" in res.build.asm_text
    assert "ucomisd" in res.build.asm_text
    assert "xmm0" in res.build.asm_text
    assert "nx_print_f64" in res.build.asm_text
    assert ".double 1.5" in res.build.asm_text
    out_lines = [ln.strip() for ln in res.exe_stdout.splitlines() if ln.strip()]
    assert out_lines[:3] == ["3.75", "7.5", "1"]
    assert res.exe_exit_code == 42


def test_native_len_and_print_str(tmp_path: Path):
    src = """
fn main() -> i32 {
    let xs: Array[i32] = [10, 20, 30, 40];
    print("hello native");
    return len(xs);
}
"""
    res = _compile_and_run(src, tmp_path, "lenstr")
    assert "hello native" in res.exe_stdout
    assert res.exe_exit_code == 4
    assert "nx_array_len" in res.build.asm_text
    assert "nx_print_str" in res.build.asm_text
