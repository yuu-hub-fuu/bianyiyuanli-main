from nexa.backend.llvm_backend import try_emit_object
from nexa.compiler import compile_source


def test_for_loop_sum_runs():
    src = '''
fn main() -> i32 {
  let s: i32 = 0;
  for let i: i32 = 0; i < 4; i = i + 1 {
    s = s + i;
  }
  return s;
}
'''
    res = compile_source(src, mode='core', run=True)
    assert all(d.level != 'error' for d in res.diagnostics)
    assert res.run_value == 6


def test_for_break_exits_nearest_loop():
    src = '''
fn main() -> i32 {
  let s: i32 = 0;
  for let i: i32 = 0; i < 5; i = i + 1 {
    if i == 3 { break; }
    s = s + 1;
  }
  return s;
}
'''
    res = compile_source(src, mode='core', run=True)
    assert all(d.level != 'error' for d in res.diagnostics)
    assert res.run_value == 3


def test_for_continue_runs_step_then_next_iteration():
    src = '''
fn main() -> i32 {
  let s: i32 = 0;
  for let i: i32 = 0; i < 5; i = i + 1 {
    if i == 3 { continue; }
    s = s + 1;
  }
  return s;
}
'''
    res = compile_source(src, mode='core', run=True)
    assert all(d.level != 'error' for d in res.diagnostics)
    assert res.run_value == 4


def test_nested_break_only_exits_inner_loop():
    src = '''
fn main() -> i32 {
  let s: i32 = 0;
  for let i: i32 = 0; i < 3; i = i + 1 {
    for let j: i32 = 0; j < 3; j = j + 1 {
      break;
    }
    s = s + 1;
  }
  return s;
}
'''
    res = compile_source(src, mode='core', run=True)
    assert all(d.level != 'error' for d in res.diagnostics)
    assert res.run_value == 3


def test_break_continue_outside_loop_are_errors():
    res_break = compile_source('fn main() -> i32 { break; return 0; }', mode='core')
    res_continue = compile_source('fn main() -> i32 { continue; return 0; }', mode='core')
    assert any('break 只能出现在循环内部' in d.message for d in res_break.diagnostics)
    assert any('continue 只能出现在循环内部' in d.message for d in res_continue.diagnostics)


def test_for_condition_must_be_bool():
    src = 'fn main() -> i32 { for let i: i32 = 0; 1; i = i + 1 { break; } return 0; }'
    res = compile_source(src, mode='core')
    assert any('for 条件必须是 bool' in d.message for d in res.diagnostics)


def test_empty_for_condition_and_llvm_backend():
    src = 'fn main() -> i32 { for ;; { break; } return 7; }'
    res = compile_source(src, mode='core', run=True)
    assert all(d.level != 'error' for d in res.diagnostics)
    assert res.run_value == 7
    assert 'JUMP' in '\n'.join(res.artifacts.tables['hir_opt'])
    assert 'br label' in res.artifacts.llvm_ir
    try_emit_object(res.artifacts.llvm_ir)
