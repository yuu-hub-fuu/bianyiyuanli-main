from pathlib import Path

from nexa.compiler import compile_source
from nexa.ide import app as ide_app
from nexa.report.html_report import write_html_report


def test_select_default_nonblocking_with_vm_run_and_default_body_effect():
    src = '''
fn main() -> i32 {
  let ch: Chan[i32] = chan(1);
  let x: i32 = select { recv(ch) => { 1; } default => { print(0); 7; } };
  return x;
}
'''
    res = compile_source(src, mode='full', run=True)
    assert all(d.level != 'error' for d in res.diagnostics)
    assert res.run_value == 7
    assert '0' in res.run_stdout


def test_select_recv_body_value_overrides_received_value():
    src = '''
fn main() -> i32 {
  let ch: Chan[i32] = chan(1);
  send(ch, 42);
  let x: i32 = select { recv(ch) => { 99; } default => { 0; } };
  return x;
}
'''
    res = compile_source(src, mode='full', run=True)
    assert all(d.level != 'error' for d in res.diagnostics)
    assert res.run_value == 99


def test_macro_gensym_avoids_capture_nested_let():
    src = '''
macro make_tmp(v) { if true { let x: i32 = v; } }
fn main() -> i32 {
  let x: i32 = 1;
  make_tmp(2);
  return x;
}
'''
    res = compile_source(src, mode='full', run=True)
    assert all(d.level != 'error' for d in res.diagnostics)
    assert res.run_value == 1


def test_generic_conflict_reports_error():
    src = '''
fn same[T](a: T, b: T) -> T { return a; }
fn main() -> i32 { let x: i32 = same(1, true); return x; }
'''
    res = compile_source(src, mode='full')
    assert any('泛型实参冲突' in d.message or '参数类型不匹配' in d.message for d in res.diagnostics)


def test_cfg_has_true_and_false_paths():
    src = 'fn main() -> i32 { let a: i32 = 1; if a > 0 { a = a + 1; } else { a = a + 2; } return a; }'
    res = compile_source(src, mode='core')
    rows = '\n'.join(res.artifacts.cfg['main'])
    assert 'succs=' in rows
    assert 'BRANCH_TRUE' in rows


def test_parser_recovery_continues_after_missing_semi():
    src = 'fn main() -> i32 { let a: i32 = 1 let b: i32 = 2; return b; }'
    res = compile_source(src, mode='core')
    assert any('缺少分号' in d.message for d in res.diagnostics)
    status = {s.name: s.status for s in res.timeline}
    assert status['Parser'] == 'failed'
    assert status['HIR'] == 'skipped'


def test_runtime_errors_are_reported_not_crash():
    src = 'fn main() -> i32 { let a: i32 = 1 / 0; return a; }'
    res = compile_source(src, mode='core', run=True)
    assert any('运行时错误' in d.message for d in res.diagnostics)
    assert any('runtime error' in line for line in res.run_stdout)


def test_vm_trace_available_when_enabled():
    src = 'fn main() -> i32 { let a: i32 = 1 + 2; return a; }'
    res = compile_source(src, mode='core', run=True, trace=True)
    assert res.run_value == 3
    assert len(res.vm_trace) > 0
    assert any(fr.instr == 'RET' for fr in res.vm_trace)


def test_html_report_writer(tmp_path):
    src = 'fn main() -> i32 { return 0; }'
    res = compile_source(src, mode='core')
    out = tmp_path / 'report.html'
    write_html_report(out, res)
    txt = out.read_text(encoding='utf-8')
    assert 'Nexa 编译课程报告' in txt
    assert 'Timeline' in txt


def test_stage_skipping_after_sema_failure():
    src = 'fn main() -> i32 { return bad; }'
    res = compile_source(src, mode='core')
    status = {s.name: s.status for s in res.timeline}
    assert status['Sema'] == 'failed'
    assert status['HIR'] == 'skipped'
    assert status['MIR'] == 'skipped'
    assert status['Backend'] == 'skipped'
    assert res.artifacts.hir_opt is None


def test_typed_hir_kind_driven():
    src = 'fn main() -> i32 { let a: i32 = 1 + 2; return a; }'
    res = compile_source(src, mode='core')
    assert res.artifacts.hir_opt is not None
    kinds = {i.kind.name for i in res.artifacts.hir_opt.functions[0].instrs}
    assert 'CONST' in kinds
    assert 'MOVE' in kinds


def test_struct_literal_field_access_and_assignment_run_in_vm():
    src = '''
struct Pair { x: i32, y: i32 }
fn main() -> i32 {
  let p: Pair = Pair { x: 1, y: 2 };
  p.x = p.x + 4;
  return p.x + p.y;
}
'''
    res = compile_source(src, mode='core', run=True)
    assert all(d.level != 'error' for d in res.diagnostics)
    assert res.run_value == 7
    assert res.artifacts.hir_opt is not None
    kinds = {i.kind.name for i in res.artifacts.hir_opt.functions[0].instrs}
    assert {'STRUCT_NEW', 'FIELD_GET', 'FIELD_SET'} <= kinds


def test_struct_literal_reports_missing_and_unknown_fields():
    src = 'struct Pair { x: i32, y: i32 } fn main() -> i32 { let p: Pair = Pair { x: 1, z: 2 }; return 0; }'
    res = compile_source(src, mode='core')
    messages = '\n'.join(d.message for d in res.diagnostics)
    assert '没有字段 z' in messages
    assert '缺少字段 y' in messages


def test_float_arithmetic_runs_in_vm():
    src = 'fn main() -> i32 { let x: f64 = 1.5 + 2.25; if x > 3.0 { return 1; } return 0; }'
    res = compile_source(src, mode='core', run=True)
    assert all(d.level != 'error' for d in res.diagnostics)
    assert res.run_value == 1


def test_array_literal_index_and_assignment_run_in_vm():
    src = '''
fn main() -> i32 {
  let xs: Array[i32] = [1, 2, 3];
  xs[1] = xs[0] + xs[2];
  return xs[1];
}
'''
    res = compile_source(src, mode='core', run=True)
    assert all(d.level != 'error' for d in res.diagnostics)
    assert res.run_value == 4
    assert res.artifacts.hir_opt is not None
    kinds = {i.kind.name for i in res.artifacts.hir_opt.functions[0].instrs}
    assert {'ARRAY_NEW', 'ARRAY_GET', 'ARRAY_SET'} <= kinds


def test_array_literal_rejects_mixed_element_types():
    src = 'fn main() -> i32 { let xs: Array[i32] = [1, true]; return 0; }'
    res = compile_source(src, mode='core')
    assert any('数组元素类型必须一致' in d.message for d in res.diagnostics)


def test_len_print_str_and_read_builtins_run_in_vm(monkeypatch):
    values = iter(["7", "2.5"])
    monkeypatch.setattr("builtins.input", lambda: next(values))
    src = '''
fn main() -> i32 {
  let xs: Array[i32] = [1, 2, 3];
  print("hello");
  let a: i32 = read_i32();
  let b: f64 = read_f64();
  if b > 2.0 { return len(xs) + a; }
  return 0;
}
'''
    res = compile_source(src, mode='core', run=True)
    assert all(d.level != 'error' for d in res.diagnostics)
    assert res.run_value == 10
    assert 'hello' in res.run_stdout


def test_len_rejects_non_array_argument():
    src = 'fn main() -> i32 { return len(1); }'
    res = compile_source(src, mode='core')
    assert any('len 参数必须是 Array' in d.message for d in res.diagnostics)


def test_import_string_path_allows_cross_file_vm_call(tmp_path):
    lib = tmp_path / "math.nx"
    lib.write_text("fn add(a: i32, b: i32) -> i32 { return a + b; }", encoding="utf-8")
    main = tmp_path / "main.nx"
    src = 'import "math.nx"; fn main() -> i32 { return add(2, 5); }'
    main.write_text(src, encoding="utf-8")
    res = compile_source(src, mode='core', run=True, source_path=str(main))
    assert all(d.level != 'error' for d in res.diagnostics)
    assert res.run_value == 7
    assert "math__add" in res.artifacts.asm_module


def test_llvm_emits_if_control_flow():
    src = 'fn main() -> i32 { let a: i32 = 1; if a > 0 { a = 2; } return a; }'
    res = compile_source(src, mode='core')
    assert not any('LLVM backend rejects control-flow instruction' in d.message for d in res.diagnostics)
    assert 'br i1' in res.artifacts.llvm_ir
    assert 'label %' in res.artifacts.llvm_ir


def test_llvm_emits_while_control_flow():
    src = 'fn main() -> i32 { let a: i32 = 0; while a < 2 { a = a + 1; } return a; }'
    res = compile_source(src, mode='core')
    assert not any('LLVM backend rejects control-flow instruction' in d.message for d in res.diagnostics)
    assert 'br i1' in res.artifacts.llvm_ir
    assert 'br label %' in res.artifacts.llvm_ir


def test_compile_source_stage_callback_and_structured_artifacts():
    seen = []
    src = 'fn main() -> i32 { let a: i32 = 1 + 2; return a; }'
    res = compile_source(src, mode='core', on_stage=lambda stage: seen.append(stage.name))
    assert seen[:2] == ['Lexer', 'Parser']
    assert seen == [s.name for s in res.timeline]
    assert res.artifacts.token_rows
    assert res.artifacts.symbol_rows
    assert res.artifacts.hir_opt_structured
    assert 'main' in res.artifacts.cfg_structured


def test_artifacts_always_present_for_gui():
    src = 'fn main() -> i32 { let a: i32 = ; return 0; }'
    res = compile_source(src, mode='core')
    assert isinstance(res.artifacts.tokens, list)
    assert isinstance(res.artifacts.tables, dict)
    assert isinstance(res.artifacts.cfg, dict)
    assert isinstance(res.artifacts.token_rows, list)
    assert isinstance(res.artifacts.symbol_rows, list)
    assert isinstance(res.artifacts.cfg_structured, dict)


def test_report_contains_symbols_quads_and_run_result(tmp_path):
    src = 'fn main() -> i32 { let a: i32 = 1 + 2; return a; }'
    res = compile_source(src, mode='core', run=True, trace=True)
    out = tmp_path / 'report.html'
    write_html_report(out, res)
    text = out.read_text(encoding='utf-8')
    assert 'Symbol Table' in text
    assert 'Quadruple Table' in text
    assert 'VM Run Result' in text


def test_asm_backend_uses_kind_dispatch():
    txt = Path('nexa/backend/asm_x64.py').read_text(encoding='utf-8')
    assert 'ins.kind ==' in txt
    assert 'startswith("bin.' not in txt


def test_ide_main_uses_tkinter_studio(monkeypatch):
    calls = []

    class DummyStudio:
        def __init__(self):
            calls.append("init")

        def mainloop(self):
            calls.append("mainloop")

    monkeypatch.setattr(ide_app, "NexaStudio", DummyStudio)
    ide_app.main()
    assert calls == ["init", "mainloop"]
