from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class TokenKind(Enum):
    IDENT = auto()
    INT = auto()
    FLOAT = auto()
    STRING = auto()
    TRUE = auto()
    FALSE = auto()
    FN = auto()
    LET = auto()
    RETURN = auto()
    IF = auto()
    ELSE = auto()
    WHILE = auto()
    STRUCT = auto()
    MACRO = auto()
    SPAWN = auto()
    SELECT = auto()
    RECV = auto()
    SEND = auto()
    DEFAULT = auto()
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()
    EQ = auto()
    EQEQ = auto()
    NE = auto()
    LT = auto()
    LE = auto()
    GT = auto()
    GE = auto()
    ANDAND = auto()
    OROR = auto()
    NOT = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACE = auto()
    RBRACE = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    COLON = auto()
    SEMI = auto()
    COMMA = auto()
    DOT = auto()
    ARROW = auto()      # ->
    FATARROW = auto()   # =>
    EOF = auto()


KEYWORDS = {
    "fn": TokenKind.FN,
    "let": TokenKind.LET,
    "return": TokenKind.RETURN,
    "if": TokenKind.IF,
    "else": TokenKind.ELSE,
    "while": TokenKind.WHILE,
    "struct": TokenKind.STRUCT,
    "macro": TokenKind.MACRO,
    "spawn": TokenKind.SPAWN,
    "select": TokenKind.SELECT,
    "recv": TokenKind.RECV,
    "send": TokenKind.SEND,
    "default": TokenKind.DEFAULT,
    "true": TokenKind.TRUE,
    "false": TokenKind.FALSE,
}

DELIMITERS = {
    "(": TokenKind.LPAREN,
    ")": TokenKind.RPAREN,
    "{": TokenKind.LBRACE,
    "}": TokenKind.RBRACE,
    "[": TokenKind.LBRACKET,
    "]": TokenKind.RBRACKET,
    ",": TokenKind.COMMA,
    ";": TokenKind.SEMI,
    ":": TokenKind.COLON,
    ".": TokenKind.DOT,
}


@dataclass(slots=True, frozen=True)
class Span:
    start: int
    end: int
    line: int
    col: int


@dataclass(slots=True, frozen=True)
class Token:
    kind: TokenKind
    lexeme: str
    span: Span
