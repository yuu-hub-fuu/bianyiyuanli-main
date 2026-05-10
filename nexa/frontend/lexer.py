from __future__ import annotations

from dataclasses import dataclass, field

from .diagnostics import DiagnosticBag
from .tokens import DELIMITERS, KEYWORDS, Span, Token, TokenKind


@dataclass(slots=True)
class LexTables:
    keyword_table: set[str] = field(default_factory=set)
    delimiter_table: set[str] = field(default_factory=set)
    identifier_table: set[str] = field(default_factory=set)
    constant_table: set[str] = field(default_factory=set)


class Lexer:
    def __init__(self, source: str, diagnostics: DiagnosticBag | None = None) -> None:
        self.source = source
        self.i = 0
        self.line = 1
        self.col = 1
        self.diag = diagnostics or DiagnosticBag()
        self.tables = LexTables()

    def _peek(self, off: int = 0) -> str:
        p = self.i + off
        return self.source[p] if p < len(self.source) else "\0"

    def _advance(self) -> str:
        ch = self._peek()
        self.i += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def _span(self, s: int, e: int, line: int, col: int) -> Span:
        return Span(s, e, line, col)

    def scan(self) -> list[Token]:
        out: list[Token] = []
        while self._peek() != "\0":
            ch = self._peek()
            if ch in " \t\r\n":
                self._advance()
                continue
            if ch == "/" and self._peek(1) == "/":
                while self._peek() not in ("\n", "\0"):
                    self._advance()
                continue
            start, line, col = self.i, self.line, self.col
            if ch.isalpha() or ch == "_":
                lex = self._scan_ident()
                kind = KEYWORDS.get(lex, TokenKind.IDENT)
                if kind == TokenKind.IDENT:
                    self.tables.identifier_table.add(lex)
                else:
                    self.tables.keyword_table.add(lex)
                out.append(Token(kind, lex, self._span(start, self.i, line, col)))
                continue
            if ch.isdigit():
                lex = self._scan_number()
                self.tables.constant_table.add(lex)
                kind = TokenKind.FLOAT if "." in lex else TokenKind.INT
                out.append(Token(kind, lex, self._span(start, self.i, line, col)))
                continue
            if ch == '"':
                tok = self._scan_string(start, line, col)
                self.tables.constant_table.add(repr(tok.lexeme))
                out.append(tok)
                continue
            tok = self._scan_punct(start, line, col)
            if tok:
                out.append(tok)
            else:
                bad = self._advance()
                self.diag.error(self._span(start, self.i, line, col), f"非法字符: {bad!r}")
        out.append(Token(TokenKind.EOF, "", self._span(self.i, self.i, self.line, self.col)))
        return out

    def _scan_ident(self) -> str:
        s = self.i
        while self._peek().isalnum() or self._peek() == "_":
            self._advance()
        return self.source[s:self.i]

    def _scan_number(self) -> str:
        s = self.i
        while self._peek().isdigit():
            self._advance()
        if self._peek() == "." and self._peek(1).isdigit():
            self._advance()
            while self._peek().isdigit():
                self._advance()
        return self.source[s:self.i]

    def _scan_string(self, start: int, line: int, col: int) -> Token:
        self._advance()
        chars: list[str] = []
        while self._peek() not in ('"', "\0"):
            if self._peek() == "\\":
                self._advance()
                esc = self._advance()
                chars.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(esc, esc))
            else:
                chars.append(self._advance())
        if self._peek() != '"':
            self.diag.error(self._span(start, self.i, line, col), "字符串未闭合")
            return Token(TokenKind.STRING, "".join(chars), self._span(start, self.i, line, col))
        self._advance()
        return Token(TokenKind.STRING, "".join(chars), self._span(start, self.i, line, col))

    def _scan_punct(self, start: int, line: int, col: int) -> Token | None:
        two = self._peek() + self._peek(1)
        pair = {
            "==": TokenKind.EQEQ,
            "!=": TokenKind.NE,
            "<=": TokenKind.LE,
            ">=": TokenKind.GE,
            "&&": TokenKind.ANDAND,
            "||": TokenKind.OROR,
            "->": TokenKind.ARROW,
            "=>": TokenKind.FATARROW,
        }
        if two in pair:
            self._advance(); self._advance()
            self.tables.delimiter_table.add(two)
            return Token(pair[two], two, self._span(start, self.i, line, col))
        single = {
            "+": TokenKind.PLUS,
            "-": TokenKind.MINUS,
            "*": TokenKind.STAR,
            "/": TokenKind.SLASH,
            "%": TokenKind.PERCENT,
            "=": TokenKind.EQ,
            "<": TokenKind.LT,
            ">": TokenKind.GT,
            "!": TokenKind.NOT,
            **DELIMITERS,
        }
        ch = self._peek()
        if ch in single:
            self._advance()
            if ch in DELIMITERS:
                self.tables.delimiter_table.add(ch)
            return Token(single[ch], ch, self._span(start, self.i, line, col))
        return None
