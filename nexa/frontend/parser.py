from __future__ import annotations

from . import ast
from .diagnostics import DiagnosticBag
from .tokens import Span, Token, TokenKind


PRECEDENCE = {
    TokenKind.OROR: 1,
    TokenKind.ANDAND: 2,
    TokenKind.EQEQ: 3,
    TokenKind.NE: 3,
    TokenKind.LT: 4,
    TokenKind.LE: 4,
    TokenKind.GT: 4,
    TokenKind.GE: 4,
    TokenKind.PLUS: 5,
    TokenKind.MINUS: 5,
    TokenKind.STAR: 6,
    TokenKind.SLASH: 6,
    TokenKind.PERCENT: 6,
}


class Parser:
    def __init__(self, tokens: list[Token], diagnostics: DiagnosticBag | None = None) -> None:
        self.tokens = tokens
        self.i = 0
        self.diag = diagnostics or DiagnosticBag()

    def parse(self) -> ast.Module:
        items = []
        while not self._at(TokenKind.EOF):
            if self._match(TokenKind.FN):
                items.append(self._parse_fn())
            elif self._match(TokenKind.MACRO):
                items.append(self._parse_macro())
            elif self._match(TokenKind.STRUCT):
                items.append(self._parse_struct())
            elif self._match(TokenKind.CLASS):
                items.append(self._parse_class())
            elif self._match(TokenKind.IMPORT):
                items.append(self._parse_import())
            else:
                self._error_here("期望顶层定义 import/fn/macro/struct")
                self._sync_top()
        return ast.Module(self._span_of(0), items)

    def _parse_import(self) -> ast.ImportDecl:
        path = self._expect(TokenKind.STRING, 'import 需要字符串路径，例如 import "math.nx";')
        self._expect(TokenKind.SEMI, "import 缺少分号", fix="在 import 后插入 ';'")
        return ast.ImportDecl(path.span, path.lexeme)

    def _parse_struct(self) -> ast.StructDef:
        name = self._expect(TokenKind.IDENT, "期望结构体名")
        self._expect(TokenKind.LBRACE, "struct 缺少 {")
        fields: list[ast.Field] = []
        while not self._at(TokenKind.RBRACE) and not self._at(TokenKind.EOF):
            fn = self._expect(TokenKind.IDENT, "期望字段名")
            self._expect(TokenKind.COLON, "字段缺少类型注解")
            fty = self._parse_type_ref()
            fields.append(ast.Field(fn.span, fn.lexeme, fty))
            self._match(TokenKind.COMMA)
        self._expect(TokenKind.RBRACE, "struct 缺少 }")
        return ast.StructDef(name.span, name.lexeme, fields)

    def _parse_visibility(self) -> str:
        if self._match(TokenKind.PRIVATE):
            return "private"
        if self._match(TokenKind.PUBLIC):
            return "public"
        return "public"

    def _parse_class(self) -> ast.ClassDef:
        name = self._expect(TokenKind.IDENT, "class expects a name")
        base: str | None = None
        if self._match(TokenKind.EXTENDS):
            base = self._expect(TokenKind.IDENT, "extends expects a base class name").lexeme
        self._expect(TokenKind.LBRACE, "class expects {")
        fields: list[ast.Field] = []
        methods: list[ast.Function] = []
        while not self._at(TokenKind.RBRACE) and not self._at(TokenKind.EOF):
            visibility = self._parse_visibility()
            is_virtual = self._match(TokenKind.VIRTUAL)
            is_override = self._match(TokenKind.OVERRIDE)
            if self._match(TokenKind.CONSTRUCTOR):
                methods.append(self._parse_special_method(name.lexeme, "constructor", name.lexeme, visibility, is_virtual, is_override))
                continue
            if self._match(TokenKind.DESTRUCTOR):
                methods.append(self._parse_special_method(name.lexeme, "destructor", name.lexeme, visibility, is_virtual, is_override))
                continue
            if self._match(TokenKind.FN):
                method = self._parse_fn(owner_class=name.lexeme, visibility=visibility)
                method.is_virtual = is_virtual
                method.is_override = is_override
                method.name = f"{name.lexeme}__{method.name}"
                if not method.params or method.params[0].name != "self":
                    method.params.insert(0, ast.Param(name.span, "self", ast.TypeRef(name.span, name.lexeme)))
                methods.append(method)
                continue
            field_name = self._expect(TokenKind.IDENT, "class expects a field or method")
            self._expect(TokenKind.COLON, "class field expects a type")
            field_ty = self._parse_type_ref()
            fields.append(ast.Field(field_name.span, field_name.lexeme, field_ty, visibility, name.lexeme))
            if not self._match(TokenKind.COMMA):
                self._match(TokenKind.SEMI)
        self._expect(TokenKind.RBRACE, "class expects }")
        return ast.ClassDef(name.span, name.lexeme, fields, methods, base)

    def _parse_special_method(
        self,
        class_name: str,
        kind: str,
        owner_class: str,
        visibility: str,
        is_virtual: bool,
        is_override: bool,
    ) -> ast.Function:
        start = self._peek(-1).span
        self._expect(TokenKind.LPAREN, f"{kind} expects (")
        params: list[ast.Param] = [ast.Param(start, "self", ast.TypeRef(start, class_name))]
        if not self._at(TokenKind.RPAREN):
            while True:
                p_name = self._expect(TokenKind.IDENT, f"{kind} expects parameter name")
                self._expect(TokenKind.COLON, f"{kind} parameter expects type")
                p_ty = self._parse_type_ref()
                params.append(ast.Param(p_name.span, p_name.lexeme, p_ty))
                if not self._match(TokenKind.COMMA):
                    break
        self._expect(TokenKind.RPAREN, f"{kind} expects )")
        body = self._parse_block()
        name = f"{class_name}__{'__init' if kind == 'constructor' else '__drop'}"
        return ast.Function(
            start,
            name,
            params,
            ast.TypeRef(start, "void"),
            body,
            owner_class=owner_class,
            visibility=visibility,
            is_virtual=is_virtual,
            is_override=is_override,
            is_constructor=(kind == "constructor"),
            is_destructor=(kind == "destructor"),
        )

    def _parse_fn(self, owner_class: str | None = None, visibility: str = "public") -> ast.Function:
        name = self._expect(TokenKind.IDENT, "期望函数名")
        generics: list[str] = []
        bounds: dict[str, list[str]] = {}
        if self._match(TokenKind.LBRACKET):
            while not self._at(TokenKind.RBRACKET) and not self._at(TokenKind.EOF):
                gp = self._expect(TokenKind.IDENT, "期望泛型参数")
                generics.append(gp.lexeme)
                b: list[str] = []
                if self._match(TokenKind.COLON):
                    b.append(self._expect(TokenKind.IDENT, "期望 trait 约束").lexeme)
                    while self._match(TokenKind.PLUS):
                        b.append(self._expect(TokenKind.IDENT, "期望 trait 约束").lexeme)
                bounds[gp.lexeme] = b
                if not self._match(TokenKind.COMMA):
                    break
            self._expect(TokenKind.RBRACKET, "缺少 ]")
        self._expect(TokenKind.LPAREN, "缺少 (")
        params: list[ast.Param] = []
        if not self._at(TokenKind.RPAREN):
            while True:
                p_name = self._expect(TokenKind.IDENT, "期望参数名")
                self._expect(TokenKind.COLON, "参数缺少类型注解")
                p_ty = self._parse_type_ref()
                params.append(ast.Param(p_name.span, p_name.lexeme, p_ty))
                if not self._match(TokenKind.COMMA):
                    break
        self._expect(TokenKind.RPAREN, "缺少 )")
        ret = ast.TypeRef(name.span, "void")
        if self._match(TokenKind.ARROW):
            ret = self._parse_type_ref()
        body = self._parse_block()
        return ast.Function(name.span, name.lexeme, params, ret, body, generics, bounds, bool(generics), owner_class, visibility)

    def _parse_macro(self) -> ast.Macro:
        name = self._expect(TokenKind.IDENT, "期望宏名")
        self._expect(TokenKind.LPAREN, "缺少 (")
        params: list[str] = []
        if not self._at(TokenKind.RPAREN):
            while True:
                p = self._expect(TokenKind.IDENT, "期望宏参数")
                params.append(p.lexeme)
                if not self._match(TokenKind.COMMA):
                    break
        self._expect(TokenKind.RPAREN, "缺少 )")
        body = self._parse_block()
        return ast.Macro(name.span, name.lexeme, params, body)

    def _parse_block(self) -> ast.Block:
        lb = self._expect(TokenKind.LBRACE, "缺少 {")
        return self._parse_block_after_lbrace(lb.span)

    def _parse_block_after_lbrace(self, lb_span: Span) -> ast.Block:
        stmts: list[ast.Stmt] = []
        while not self._at(TokenKind.RBRACE) and not self._at(TokenKind.EOF):
            stmts.append(self._parse_stmt())
        self._expect(TokenKind.RBRACE, "缺少 }")
        return ast.Block(lb_span, stmts)

    def _parse_stmt(self) -> ast.Stmt:
        if self._match(TokenKind.LET):
            n = self._expect(TokenKind.IDENT, "期望变量名")
            tr = None
            if self._match(TokenKind.COLON):
                tr = self._parse_type_ref()
            val = None
            if self._match(TokenKind.EQ):
                val = self._parse_expr()
            self._expect(TokenKind.SEMI, "缺少分号", fix="在此处插入 ';'")
            return ast.LetStmt(n.span, n.lexeme, tr, val)
        if self._match(TokenKind.RETURN):
            start = self._peek(-1).span
            v = None if self._at(TokenKind.SEMI) else self._parse_expr()
            self._expect(TokenKind.SEMI, "缺少分号", fix="在 return 语句后插入 ';'")
            return ast.ReturnStmt(start, v)
        if self._match(TokenKind.DELETE):
            start = self._peek(-1).span
            v = self._parse_expr()
            self._expect(TokenKind.SEMI, "delete expects ;")
            return ast.DeleteStmt(start, v)
        if self._match(TokenKind.IF):
            start = self._peek(-1).span
            cond = self._parse_expr()
            tb = self._parse_block()
            eb = self._parse_block() if self._match(TokenKind.ELSE) else None
            return ast.IfStmt(start, cond, tb, eb)
        if self._match(TokenKind.WHILE):
            start = self._peek(-1).span
            cond = self._parse_expr()
            body = self._parse_block()
            return ast.WhileStmt(start, cond, body)
        if self._match(TokenKind.SPAWN):
            start = self._peek(-1).span
            e = self._parse_expr()
            self._expect(TokenKind.SEMI, "缺少分号", fix="在 spawn 后插入 ';'")
            return ast.SpawnStmt(start, e)
        if self._at(TokenKind.LBRACE):
            return self._parse_block()

        e = self._parse_expr()
        if isinstance(e, (ast.NameExpr, ast.FieldAccess, ast.IndexExpr, ast.UnaryExpr)) and self._match(TokenKind.EQ):
            rhs = self._parse_expr()
            self._expect(TokenKind.SEMI, "缺少分号", fix="在赋值语句后插入 ';'")
            return ast.AssignStmt(e.span, e, rhs)
        self._expect(TokenKind.SEMI, "缺少分号", fix="在语句末尾插入 ';'")
        return ast.ExprStmt(e.span, e)

    def _parse_select_expr(self, start: Span) -> ast.SelectExpr:
        self._expect(TokenKind.LBRACE, "select 缺少 {")
        cases: list[ast.SelectCase] = []
        while not self._at(TokenKind.RBRACE) and not self._at(TokenKind.EOF):
            if self._match(TokenKind.RECV):
                self._expect(TokenKind.LPAREN, "recv 缺少 (")
                ch = self._parse_expr(); self._expect(TokenKind.RPAREN, "recv 缺少 )")
                self._expect(TokenKind.FATARROW, "recv 分支缺少 =>")
                cases.append(ast.SelectCase(start, "recv", ch, None, self._parse_block()))
            elif self._match(TokenKind.SEND):
                self._expect(TokenKind.LPAREN, "send 缺少 (")
                ch = self._parse_expr(); self._expect(TokenKind.COMMA, "send 缺少 ,")
                v = self._parse_expr(); self._expect(TokenKind.RPAREN, "send 缺少 )")
                self._expect(TokenKind.FATARROW, "send 分支缺少 =>")
                cases.append(ast.SelectCase(start, "send", ch, v, self._parse_block()))
            elif self._match(TokenKind.DEFAULT):
                self._expect(TokenKind.FATARROW, "default 分支缺少 =>")
                cases.append(ast.SelectCase(start, "default", None, None, self._parse_block()))
            else:
                self._error_here("select 子句非法")
                self._sync_stmt()
        self._expect(TokenKind.RBRACE, "select 缺少 }")
        return ast.SelectExpr(start, None, cases)

    def _parse_type_ref(self) -> ast.TypeRef:
        n = self._expect(TokenKind.IDENT, "期望类型名")
        params: list[ast.TypeRef] = []
        if self._match(TokenKind.LBRACKET):
            while not self._at(TokenKind.RBRACKET) and not self._at(TokenKind.EOF):
                params.append(self._parse_type_ref())
                if not self._match(TokenKind.COMMA):
                    break
            self._expect(TokenKind.RBRACKET, "类型参数缺少 ]")
        return ast.TypeRef(n.span, n.lexeme, params)

    def _parse_expr(self, min_bp: int = 0) -> ast.Expr:
        tok = self._advance()
        if tok.kind == TokenKind.INT:
            lhs: ast.Expr = ast.IntLit(tok.span, None, int(tok.lexeme))
        elif tok.kind == TokenKind.FLOAT:
            lhs = ast.FloatLit(tok.span, None, float(tok.lexeme))
        elif tok.kind == TokenKind.TRUE:
            lhs = ast.BoolLit(tok.span, None, True)
        elif tok.kind == TokenKind.FALSE:
            lhs = ast.BoolLit(tok.span, None, False)
        elif tok.kind == TokenKind.STRING:
            lhs = ast.StrLit(tok.span, None, tok.lexeme)
        elif tok.kind in {TokenKind.IDENT, TokenKind.SEND, TokenKind.RECV}:
            lhs = ast.NameExpr(tok.span, None, tok.lexeme)
        elif tok.kind == TokenKind.SELECT:
            lhs = self._parse_select_expr(tok.span)
        elif tok.kind == TokenKind.NEW:
            ty = self._parse_type_ref()
            self._expect(TokenKind.LPAREN, "new expects (")
            args: list[ast.Expr] = []
            if not self._at(TokenKind.RPAREN):
                while True:
                    args.append(self._parse_expr())
                    if not self._match(TokenKind.COMMA):
                        break
            self._expect(TokenKind.RPAREN, "new expects )")
            lhs = ast.NewExpr(tok.span, None, ty, args)
        elif tok.kind in (TokenKind.NOT, TokenKind.MINUS, TokenKind.AMP, TokenKind.STAR):
            rhs = self._parse_expr(7)
            lhs = ast.UnaryExpr(tok.span, None, tok.lexeme, rhs)
        elif tok.kind == TokenKind.LPAREN:
            lhs = self._parse_expr()
            self._expect(TokenKind.RPAREN, "缺少 )")
        elif tok.kind == TokenKind.LBRACE:
            lhs = ast.BlockExpr(tok.span, None, self._parse_block_after_lbrace(tok.span))
        elif tok.kind == TokenKind.LBRACKET:
            items: list[ast.Expr] = []
            if not self._at(TokenKind.RBRACKET):
                while True:
                    items.append(self._parse_expr())
                    if not self._match(TokenKind.COMMA):
                        break
            self._expect(TokenKind.RBRACKET, "数组字面量缺少 ]")
            lhs = ast.ArrayLit(tok.span, None, items)
        else:
            self.diag.error(tok.span, f"非法表达式起始: {tok.kind.name}")
            lhs = ast.IntLit(tok.span, None, 0)

        while True:
            if (
                isinstance(lhs, ast.NameExpr)
                and self._at(TokenKind.LBRACE)
                and (self._peek(1).kind == TokenKind.RBRACE or (self._peek(1).kind == TokenKind.IDENT and self._peek(2).kind == TokenKind.COLON))
            ):
                self._advance()
                fields: list[ast.FieldInit] = []
                while not self._at(TokenKind.RBRACE) and not self._at(TokenKind.EOF):
                    name = self._expect(TokenKind.IDENT, "期望字段名")
                    self._expect(TokenKind.COLON, "字段初始化缺少 ':'")
                    value = self._parse_expr()
                    fields.append(ast.FieldInit(name.span, name.lexeme, value))
                    if not self._match(TokenKind.COMMA):
                        break
                self._expect(TokenKind.RBRACE, "结构体字面量缺少 }")
                lhs = ast.StructLit(tok.span, None, lhs.name, fields)
                continue
            if self._at(TokenKind.DOT):
                dot = self._advance()
                field = self._expect(TokenKind.IDENT, "期望字段名")
                lhs = ast.FieldAccess(dot.span, None, lhs, field.lexeme)
                continue
            if self._at(TokenKind.LBRACKET):
                lb = self._advance()
                index = self._parse_expr()
                self._expect(TokenKind.RBRACKET, "索引表达式缺少 ]")
                lhs = ast.IndexExpr(lb.span, None, lhs, index)
                continue
            if self._at(TokenKind.LPAREN):
                self._advance()
                args: list[ast.Expr] = []
                if not self._at(TokenKind.RPAREN):
                    while True:
                        args.append(self._parse_expr())
                        if not self._match(TokenKind.COMMA):
                            break
                rp = self._expect(TokenKind.RPAREN, "缺少 )")
                lhs = ast.CallExpr(rp.span, None, lhs, args)
                continue
            op = self._peek().kind
            if op not in PRECEDENCE:
                break
            bp = PRECEDENCE[op]
            if bp < min_bp:
                break
            op_tok = self._advance()
            rhs = self._parse_expr(bp + 1)
            lhs = ast.BinaryExpr(op_tok.span, None, op_tok.lexeme, lhs, rhs)
        return lhs

    def _peek(self, off: int = 0) -> Token:
        idx = self.i + off
        if idx < 0:
            idx = 0
        if idx >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[idx]

    def _advance(self) -> Token:
        t = self._peek()
        self.i = min(self.i + 1, len(self.tokens) - 1)
        return t

    def _at(self, kind: TokenKind) -> bool:
        return self._peek().kind == kind

    def _match(self, kind: TokenKind) -> bool:
        if self._at(kind):
            self._advance()
            return True
        return False

    def _expect(self, kind: TokenKind, msg: str, fix: str | None = None) -> Token:
        if self._at(kind):
            return self._advance()
        self.diag.error(self._peek().span, msg, fixits=[fix] if fix else None)
        return Token(kind, "", self._peek().span)

    def _error_here(self, msg: str) -> None:
        self.diag.error(self._peek().span, msg)

    def _sync_stmt(self) -> None:
        sync = {TokenKind.SEMI, TokenKind.RBRACE, TokenKind.EOF}
        while self._peek().kind not in sync:
            self._advance()
        if self._at(TokenKind.SEMI):
            self._advance()

    def _sync_top(self) -> None:
        while self._peek().kind not in {TokenKind.IMPORT, TokenKind.FN, TokenKind.MACRO, TokenKind.STRUCT, TokenKind.CLASS, TokenKind.EOF}:
            self._advance()

    def _span_of(self, idx: int) -> Span:
        if not self.tokens:
            return Span(0, 0, 1, 1)
        return self.tokens[min(idx, len(self.tokens) - 1)].span
