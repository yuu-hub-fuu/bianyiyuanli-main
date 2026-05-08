from pathlib import Path

from nexa.backend.llvm_backend import try_emit_object
from nexa.compiler import compile_source
from nexa.frontend.diagnostics import DiagnosticBag
from nexa.frontend.lexer import Lexer
from nexa.frontend.parser import Parser
from nexa.frontend.tokens import TokenKind
from nexa.ir.hir import HIRFunction, HIRInstr, HIRKind
from nexa.opt.passes import const_fold, dce


def test_array_literal_index_read_write_runs_and_emits_runtime_ir():
    src = "fn main() -> i32 { let a = [1, 2, 3]; a[1] = 7; return a[1]; }"
    res = compile_source(src, mode="core", run=True)
    assert all(d.level != "error" for d in res.diagnostics)
    assert res.run_value == 7
    assert "ARRAY_NEW" in "\n".join(res.artifacts.tables["hir_opt"])
    assert "declare i8* @rt_array_new(i32)" in res.artifacts.llvm_ir
    try_emit_object(res.artifacts.llvm_ir)


def test_f64_literal_arithmetic_and_mixed_type_error():
    ok = compile_source("fn main() -> i32 { let x: f64 = 1.5 + 2.5; if x == 4.0 { return 1; } return 0; }", mode="core", run=True)
    assert all(d.level != "error" for d in ok.diagnostics)
    assert ok.run_value == 1
    assert "fadd double" in ok.artifacts.llvm_ir

    bad = compile_source("fn main() -> i32 { let x = 1 + 2.0; return 0; }", mode="core")
    assert any("类型不匹配" in d.message for d in bad.diagnostics)


def test_struct_literal_field_read_write_runs_and_emits_runtime_ir():
    src = "struct Point { x: i32, y: i32 } fn main() -> i32 { let p = Point { x: 1, y: 2 }; p.x = 9; return p.x; }"
    res = compile_source(src, mode="core", run=True)
    assert all(d.level != "error" for d in res.diagnostics)
    assert res.run_value == 9
    assert "FIELD_SET" in "\n".join(res.artifacts.tables["hir_opt"])
    assert "declare i8* @rt_struct_new(i8*)" in res.artifacts.llvm_ir
    try_emit_object(res.artifacts.llvm_ir)


def test_float_token_block_comment_and_else_if_parse():
    src = "fn main() -> i32 { /* block */ let x: f64 = 3.14; if false { return 1; } else if true { return 2; } return 0; }"
    diag = DiagnosticBag()
    tokens = Lexer(src, diag).scan()
    assert any(t.kind == TokenKind.FLOAT for t in tokens)
    module = Parser(tokens, diag).parse()
    assert not diag.has_errors()
    assert module.items


def test_const_fold_and_dce_cover_more_than_const_temps():
    fn = HIRFunction(
        "main",
        [
            HIRInstr(HIRKind.CONST, dst="a", args=["2"], ty="i32"),
            HIRInstr(HIRKind.CONST, dst="b", args=["3"], ty="i32"),
            HIRInstr(HIRKind.BIN, dst="dead", args=["a", "b"], op="+", ty="i32"),
            HIRInstr(HIRKind.BIN, dst="keep", args=["a", "b"], op="<", ty="bool"),
            HIRInstr(HIRKind.RET, args=["keep"], ty="bool"),
        ],
    )
    const_fold(fn)
    assert any(i.kind == HIRKind.CONST and i.dst == "keep" and i.ty == "bool" for i in fn.instrs)
    dce(fn)
    assert not any(i.dst == "dead" for i in fn.instrs)


def test_multifile_import_identifier_and_module_style_call():
    root = Path("_tmp_multifile_tests")
    root.mkdir(exist_ok=True)
    (root / "utils.nx").write_text("fn add(a: i32, b: i32) -> i32 { return a + b; }", encoding="utf-8")
    main = root / "main.nx"
    main.write_text("import utils; fn main() -> i32 { return utils.add(20, 22); }", encoding="utf-8")
    res = compile_source(main.read_text(encoding="utf-8"), mode="full", run=True, source_path=main)
    assert all(d.level != "error" for d in res.diagnostics)
    assert res.run_value == 42


def test_multifile_import_string_path():
    root = Path("_tmp_multifile_tests")
    root.mkdir(exist_ok=True)
    (root / "mathlib.nx").write_text("fn square(x: i32) -> i32 { return x * x; }", encoding="utf-8")
    main = root / "main_string.nx"
    main.write_text('import "mathlib.nx"; fn main() -> i32 { return square(6); }', encoding="utf-8")
    res = compile_source(main.read_text(encoding="utf-8"), mode="full", run=True, source_path=main)
    assert all(d.level != "error" for d in res.diagnostics)
    assert res.run_value == 36


def test_stdlib_math_str_and_array_calls_run():
    src = """
    fn main() -> i32 {
      let nums = [3, 1, 2];
      let sorted = array.sort(nums);
      let pushed = array.push(sorted, 4);
      let text = str.concat("ab", "cd");
      if str.contains(text, "bc") {
        return math.abs(-3) + array.len(pushed) + pushed[0];
      }
      return 0;
    }
    """
    res = compile_source(src, mode="core", run=True)
    assert all(d.level != "error" for d in res.diagnostics)
    assert res.run_value == 8


def test_stdlib_fs_is_limited_to_source_directory():
    root = Path("_tmp_stdlib_tests")
    root.mkdir(exist_ok=True)
    main = root / "main.nx"
    main.write_text(
        """
        fn main() -> i32 {
          fs.write_file("note.txt", "hello");
          fs.append_file("note.txt", "!");
          let text = fs.read_file("note.txt");
          if fs.exists("note.txt") && str.len(text) == 6 {
            return 1;
          }
          return 0;
        }
        """,
        encoding="utf-8",
    )
    res = compile_source(main.read_text(encoding="utf-8"), mode="core", run=True, source_path=main)
    assert all(d.level != "error" for d in res.diagnostics)
    assert res.run_value == 1
    assert (root / "note.txt").read_text(encoding="utf-8") == "hello!"


def test_stdlib_json_time_testing_and_safe_net_placeholder():
    ok = compile_source(
        'fn main() -> i32 { testing.assert_true(str.len(json.stringify(json.parse("{\\"x\\":1}"))) > 0); if str.len(time.format_iso(time.now_ms())) > 0 { return 1; } return 0; }',
        mode="core",
        run=True,
    )
    assert all(d.level != "error" for d in ok.diagnostics)
    assert ok.run_value == 1

    net = compile_source('fn main() -> i32 { let c = net.dial("127.0.0.1", 80); return 0; }', mode="core", run=True)
    assert any("disabled in the safe VM" in d.message for d in net.diagnostics)


def test_enum_match_runs_and_emits_llvm_control_flow():
    src = "enum Option<T> { Some(T), None } fn main() -> i32 { let x = Some(42); match x { Some(v) => return v, None => return 0, } }"
    res = compile_source(src, mode="core", run=True)
    assert all(d.level != "error" for d in res.diagnostics)
    assert res.run_value == 42
    assert "ENUM_NEW" in "\n".join(res.artifacts.tables["hir_opt"])
    assert "rt_enum_new" in res.artifacts.llvm_ir
    assert "br i1" in res.artifacts.llvm_ir
    try_emit_object(res.artifacts.llvm_ir)


def test_lambda_array_map_filter_reduce_and_pipeline_run_with_llvm():
    src = """
    fn main() -> i32 {
      let values = [1, 2, 3, 4]
        |> array.filter(fn(x: i32) => x % 2 == 0)
        |> array.map(fn(x: i32) => x * 10);
      return array.reduce(values, 0, fn(acc: i32, x: i32) => acc + x);
    }
    """
    res = compile_source(src, mode="core", run=True)
    assert all(d.level != "error" for d in res.diagnostics)
    assert res.run_value == 60
    assert "CLOSURE" in "\n".join(res.artifacts.tables["hir_opt"])
    assert "rt_closure_new" in res.artifacts.llvm_ir
    assert "rt_array_map" in res.artifacts.llvm_ir
    try_emit_object(res.artifacts.llvm_ir)


def test_interpolation_range_dict_and_slice_run_with_llvm():
    src = """
    fn main() -> i32 {
      let total: i32 = 0;
      for i in 0..4 { total = total + i; }
      let msg = "sum={total}";
      let arr = [1, 2, 3, 4];
      let part = arr[1..3];
      let dict = {"x": 7};
      return total + part[0] + str.len(msg);
    }
    """
    res = compile_source(src, mode="core", run=True)
    assert all(d.level != "error" for d in res.diagnostics)
    assert res.run_value == 13
    ir = res.artifacts.llvm_ir
    assert "rt_to_str" in ir
    assert "rt_array_slice" in ir
    assert "rt_dict_new" in ir
    try_emit_object(ir)


def test_modern_feature_type_errors_are_reported():
    bad_dict = compile_source('fn main() -> i32 { let d = {"x": 1, "y": false}; return 0; }', mode="core")
    assert any("dict value type mismatch" in d.message for d in bad_dict.diagnostics)

    bad_range = compile_source('fn main() -> i32 { for i in 0.0..3 { return i; } return 0; }', mode="core")
    assert any("range start must be i32" in d.message for d in bad_range.diagnostics)
