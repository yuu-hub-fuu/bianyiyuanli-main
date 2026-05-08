from nexa.frontend.diagnostics import DiagnosticBag
from nexa.frontend.lexer import Lexer
from nexa.frontend.parser import Parser
from nexa.frontend.tokens import TokenKind


def test_lexer_tables_and_tokens():
    src = 'fn main() -> i32 { let a: i32 = 1 + 2; return a; }'
    diag = DiagnosticBag()
    lexer = Lexer(src, diag)
    tokens = lexer.scan()
    assert not diag.has_errors()
    assert any(t.lexeme == 'main' for t in tokens)
    assert 'fn' in lexer.tables.keyword_table
    assert ';' in lexer.tables.delimiter_table
    assert 'a' in lexer.tables.identifier_table
    assert '1' in lexer.tables.constant_table


def test_parser_struct_select_expr_and_default_fatarrow():
    src = '''
struct Pair { x: i32, y: i32 }
fn main() -> i32 {
  let ch: Chan[i32] = chan(1);
  let a: i32 = select { recv(ch) => { 1; } default => { 0; } };
  return a;
}
'''
    diag = DiagnosticBag()
    tokens = Lexer(src, diag).scan()
    assert any(t.kind == TokenKind.FATARROW for t in tokens)
    module = Parser(tokens, diag).parse()
    assert not diag.has_errors()
    assert any(type(i).__name__ == 'StructDef' for i in module.items)


def test_parser_error_recovery_missing_semi():
    src = 'fn main() -> i32 { let a: i32 = 1 return a; }'
    diag = DiagnosticBag()
    Parser(Lexer(src, diag).scan(), diag).parse()
    assert any('缺少分号' in d.message for d in diag.items)


def test_lexer_parser_for_break_continue():
    src = '''
fn main() -> i32 {
  let s: i32 = 0;
  for let i: i32 = 0; i < 3; i = i + 1 {
    if i == 2 { break; }
    continue;
  }
  return s;
}
'''
    diag = DiagnosticBag()
    tokens = Lexer(src, diag).scan()
    kinds = {t.kind for t in tokens}
    assert TokenKind.FOR in kinds
    assert TokenKind.BREAK in kinds
    assert TokenKind.CONTINUE in kinds
    module = Parser(tokens, diag).parse()
    assert not diag.has_errors()
    fn = module.items[0]
    assert any(type(stmt).__name__ == 'ForStmt' for stmt in fn.body.stmts)
