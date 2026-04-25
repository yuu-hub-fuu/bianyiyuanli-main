from nexa.backend.llvm_backend import emit_llvm_ir
from nexa.compiler import compile_source
from nexa.frontend.diagnostics import DiagnosticBag
from nexa.frontend.lexer import Lexer
from nexa.frontend.parser import Parser
from nexa.ir.lower import Lowerer


PROGRAM = '''
macro unless(cond, body) {
  if !cond { body; }
}

fn max[T: Ord](a: T, b: T) -> T {
  if a > b { return a; }
  return b;
}

fn main() -> i32 {
    let x: i32 = max(20, 22);
    unless(x == 22, panic("bad"));
    return x;
}
'''


def test_compile_pipeline_tables_and_cfg():
    res = compile_source(PROGRAM, mode='full')
    assert all(d.level != 'error' for d in res.diagnostics)
    assert res.artifacts.tables['keywords']
    assert res.artifacts.tables['symbols']
    assert any('BRANCH_TRUE' in ln for ln in res.artifacts.tables['hir_opt'])
    assert 'main' in res.artifacts.cfg


def test_if_while_nested_scope_type_error_fixit():
    src = '''
fn main() -> i32 {
  let a: i32 = 0;
  while a < 2 {
    if a == 1 { let a: bool = true; }
    a = a + 1;
  }
  let x: bool = 1;
  return a;
}
'''
    res = compile_source(src, mode='core')
    assert any('类型不匹配' in d.message for d in res.diagnostics)
    assert any(d.fixits for d in res.diagnostics)


def test_llvm_ir_contains_params_and_call_shape():
    src = 'fn add(a: i32, b: i32) -> i32 { return a + b; }'
    diag = DiagnosticBag()
    module = Parser(Lexer(src, diag).scan(), diag).parse()
    hir = Lowerer().lower_module(module)
    ir = emit_llvm_ir(hir)
    assert 'define i32 @add(i32 %a, i32 %b)' in ir


def test_llvm_ir_emits_channel_runtime_calls():
    src = '''
fn main() -> i32 {
  let ch: Chan[i32] = chan(1);
  send(ch, 7);
  let x: i32 = select { recv(ch) => { 3; } default => { 0; } };
  return x;
}
'''
    res = compile_source(src, mode='full')
    assert 'declare i8* @rt_chan_new(i32)' in res.artifacts.llvm_ir
    assert 'call i8* @rt_chan_new' in res.artifacts.llvm_ir
    assert 'call void @rt_chan_send' in res.artifacts.llvm_ir
    assert 'call i32 @rt_chan_recv' in res.artifacts.llvm_ir
    assert 'call i1 @rt_chan_ready' in res.artifacts.llvm_ir
