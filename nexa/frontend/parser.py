from __future__ import annotations

from . import ast
from .diagnostics import DiagnosticBag
from .tokens import Span, Token, TokenKind


PRECEDENCE = {
    TokenKind.PIPEGT: 0,
    TokenKind.OROR: 1,
    TokenKind.ANDAND: 2,
    TokenKind.EQEQ: 3,
    TokenKind.NE: 3,
    TokenKind.LT: 4,
    TokenKind.LE: 4,
    TokenKind.GT: 4,
    TokenKind.GE: 4,
    TokenKind.DOTDOT: 4,
    TokenKind.DOTDOTEQ: 4,
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
            if self._match(TokenKind.IMPORT):
                items.append(self._parse_import())
            elif self._match(TokenKind.FN):
                items.append(self._parse_fn())
            elif self._match(TokenKind.MACRO):
                items.append(self._parse_macro())
            elif self._match(TokenKind.STRUCT):
                items.append(self._parse_struct())
            elif self._match(TokenKind.ENUM):
                items.append(self._parse_enum())
            else:
                self._error_here("期望顶层定义 import/fn/macro/struct")
                self._sync_top()
        return ast.Module(self._span_of(0), items)

    def _parse_import(self) -> ast.ImportDecl:
        token = self._advance()
        if token.kind == TokenKind.STRING:
            path = token.lexeme
            alias = path.replace("\\", "/").rsplit("/", 1)[-1].removesuffix(".nx")
        elif token.kind == TokenKind.IDENT:
            path = token.lexeme
            alias = token.lexeme
        else:
            self.diag.error(token.span, "import 需要模块名或字符串路径", code="E005")
            path = ""
            alias = None
        self._expect(TokenKind.SEMI, "import 缺少分号", fix="在 import 后插入 ';'", code="E001")
        return ast.ImportDecl(token.span, path, alias)

    def _parse_struct(self) -> ast.StructDef:
        name = self._expect(TokenKind.IDENT, "期望结构体名")
        self._expect(TokenKind.LBRACE, "struct 缺少 {", code="E004")
        fields: list[ast.Field] = []
        while not self._at(TokenKind.RBRACE) and not self._at(TokenKind.EOF):
            field_name = self._expect(TokenKind.IDENT, "期望字段名")
            self._expect(TokenKind.COLON, "字段缺少类型注解")
            fields.append(ast.Field(field_name.span, field_name.lexeme, self._parse_type_ref()))
            self._match(TokenKind.COMMA)
        self._expect(TokenKind.RBRACE, "struct 缺少 }", code="E004")
        return ast.StructDef(name.span, name.lexeme, fields)

    def _parse_enum(self) -> ast.EnumDef:
        name = self._expect(TokenKind.IDENT, "expected enum name")
        generics = self._parse_generic_names()
        self._expect(TokenKind.LBRACE, "enum missing {", code="E004")
        variants: list[ast.EnumVariant] = []
        while not self._at(TokenKind.RBRACE) and not self._at(TokenKind.EOF):
            variant = self._expect(TokenKind.IDENT, "expected enum variant")
            payload = None
            if self._match(TokenKind.LPAREN):
                if not self._at(TokenKind.RPAREN):
                    payload = self._parse_type_ref()
                    while self._match(TokenKind.COMMA):
                        self._parse_type_ref()
                self._expect(TokenKind.RPAREN, "enum variant missing )", code="E004")
            variants.append(ast.EnumVariant(variant.span, variant.lexeme, payload))
            self._match(TokenKind.COMMA)
        self._expect(TokenKind.RBRACE, "enum missing }", code="E004")
        return ast.EnumDef(name.span, name.lexeme, variants, generics)

    def _parse_generic_names(self) -> list[str]:
        generics: list[str] = []
        end = None
        if self._match(TokenKind.LBRACKET):
            end = TokenKind.RBRACKET
        elif self._match(TokenKind.LT):
            end = TokenKind.GT
        if end is None:
            return generics
        while not self._at(end) and not self._at(TokenKind.EOF):
            generics.append(self._expect(TokenKind.IDENT, "expected generic parameter").lexeme)
            if not self._match(TokenKind.COMMA):
                break
        self._expect(end, "generic parameter list is not closed", code="E004")
        return generics

    def _parse_fn(self) -> ast.Function:
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
            self._expect(TokenKind.RBRACKET, "缺少 ]", code="E004")
        self._expect(TokenKind.LPAREN, "缺少 (")
        params: list[ast.Param] = []
        if not self._at(TokenKind.RPAREN):
            while True:
                p_name = self._expect(TokenKind.IDENT, "期望参数名")
                self._expect(TokenKind.COLON, "参数缺少类型注解")
                params.append(ast.Param(p_name.span, p_name.lexeme, self._parse_type_ref()))
                if not self._match(TokenKind.COMMA):
                    break
        self._expect(TokenKind.RPAREN, "缺少 )", code="E004")
        ret = ast.TypeRef(name.span, "void")
        if self._match(TokenKind.ARROW):
            ret = self._parse_type_ref()
        body = self._parse_block()
        return ast.Function(name.span, name.lexeme, params, ret, body, generics, bounds, bool(generics))

    def _parse_macro(self) -> ast.Macro:
        name = self._expect(TokenKind.IDENT, "期望宏名")
        self._expect(TokenKind.LPAREN, "缺少 (")
        params: list[str] = []
        if not self._at(TokenKind.RPAREN):
            while True:
                params.append(self._expect(TokenKind.IDENT, "期望宏参数").lexeme)
                if not self._match(TokenKind.COMMA):
                    break
        self._expect(TokenKind.RPAREN, "缺少 )", code="E004")
        return ast.Macro(name.span, name.lexeme, params, self._parse_block())

    def _parse_block(self) -> ast.Block:
        lb = self._expect(TokenKind.LBRACE, "缺少 {", code="E004")
        return self._parse_block_after_lbrace(lb.span)

    def _parse_block_after_lbrace(self, lb_span: Span) -> ast.Block:
        stmts: list[ast.Stmt] = []
        while not self._at(TokenKind.RBRACE) and not self._at(TokenKind.EOF):
            stmts.append(self._parse_stmt())
        self._expect(TokenKind.RBRACE, "缺少 }", code="E004")
        return ast.Block(lb_span, stmts)

    def _parse_stmt(self) -> ast.Stmt:
        if self._match(TokenKind.LET):
            stmt = self._parse_let_after_keyword()
            self._expect(TokenKind.SEMI, "缺少分号", fix="在此处插入 ';'", code="E001")
            return stmt
        if self._match(TokenKind.RETURN):
            start = self._peek(-1).span
            value = None if self._at(TokenKind.SEMI) else self._parse_expr()
            self._expect(TokenKind.SEMI, "缺少分号", fix="在 return 语句后插入 ';'", code="E001")
            return ast.ReturnStmt(start, value)
        if self._match(TokenKind.IF):
            start = self._peek(-1).span
            cond = self._parse_expr()
            then_block = self._parse_block()
            else_block = None
            if self._match(TokenKind.ELSE):
                if self._match(TokenKind.IF):
                    nested = self._parse_if_after_keyword(self._peek(-1).span)
                    else_block = ast.Block(nested.span, [nested])
                else:
                    else_block = self._parse_block()
            return ast.IfStmt(start, cond, then_block, else_block)
        if self._match(TokenKind.WHILE):
            start = self._peek(-1).span
            return ast.WhileStmt(start, self._parse_expr(), self._parse_block())
        if self._match(TokenKind.FOR):
            start = self._peek(-1).span
            if self._peek().kind == TokenKind.IDENT and self._peek(1).kind == TokenKind.IN:
                name = self._advance()
                self._advance()
                iterable = self._parse_expr()
                return ast.ForInStmt(start, name.lexeme, iterable, self._parse_block())
            return self._parse_for_stmt(start)
        if self._match(TokenKind.BREAK):
            start = self._peek(-1).span
            self._expect(TokenKind.SEMI, "break 缺少分号", fix="在 break 后插入 ';'", code="E001")
            return ast.BreakStmt(start)
        if self._match(TokenKind.CONTINUE):
            start = self._peek(-1).span
            self._expect(TokenKind.SEMI, "continue 缺少分号", fix="在 continue 后插入 ';'", code="E001")
            return ast.ContinueStmt(start)
        if self._match(TokenKind.SPAWN):
            start = self._peek(-1).span
            expr = self._parse_expr()
            self._expect(TokenKind.SEMI, "缺少分号", fix="在 spawn 后插入 ';'", code="E001")
            return ast.SpawnStmt(start, expr)
        if self._at(TokenKind.LBRACE):
            return self._parse_block()
        if self._at(TokenKind.MATCH):
            expr = self._parse_expr()
            self._match(TokenKind.SEMI)
            return ast.ExprStmt(expr.span, expr)

        expr = self._parse_expr()
        if self._match(TokenKind.EQ):
            rhs = self._parse_expr()
            self._expect(TokenKind.SEMI, "缺少分号", fix="在赋值语句后插入 ';'", code="E001")
            return ast.AssignStmt(expr.span, expr, rhs)
        self._expect(TokenKind.SEMI, "缺少分号", fix="在语句末尾插入 ';'", code="E001")
        if isinstance(expr, ast.MatchExpr) and not self._at(TokenKind.SEMI):
            return ast.ExprStmt(expr.span, expr)
        return ast.ExprStmt(expr.span, expr)

    def _parse_if_after_keyword(self, start: Span) -> ast.IfStmt:
        cond = self._parse_expr()
        then_block = self._parse_block()
        else_block = None
        if self._match(TokenKind.ELSE):
            if self._match(TokenKind.IF):
                nested = self._parse_if_after_keyword(self._peek(-1).span)
                else_block = ast.Block(nested.span, [nested])
            else:
                else_block = self._parse_block()
        return ast.IfStmt(start, cond, then_block, else_block)

    def _parse_for_stmt(self, start: Span) -> ast.ForStmt:
        init: ast.Stmt | None = None
        cond: ast.Expr | None = None
        step: ast.Stmt | None = None
        if self._match(TokenKind.SEMI):
            init = None
        elif self._match(TokenKind.LET):
            init = self._parse_let_after_keyword()
            self._expect(TokenKind.SEMI, "for init 缺少分号", fix="在 for init 后插入 ';'", code="E001")
        else:
            init = self._parse_simple_stmt_no_semi()
            self._expect(TokenKind.SEMI, "for init 缺少分号", fix="在 for init 后插入 ';'", code="E001")
        if not self._at(TokenKind.SEMI):
            cond = self._parse_expr()
        self._expect(TokenKind.SEMI, "for 条件后缺少分号", fix="在 for 条件后插入 ';'", code="E001")
        if not self._at(TokenKind.LBRACE) and not self._at(TokenKind.EOF):
            step = self._parse_simple_stmt_no_semi()
        return ast.ForStmt(start, init, cond, step, self._parse_block())

    def _parse_let_after_keyword(self) -> ast.LetStmt:
        name = self._expect(TokenKind.IDENT, "期望变量名")
        type_ref = None
        if self._match(TokenKind.COLON):
            type_ref = self._parse_type_ref()
        value = None
        if self._match(TokenKind.EQ):
            value = self._parse_expr()
        return ast.LetStmt(name.span, name.lexeme, type_ref, value)

    def _parse_simple_stmt_no_semi(self) -> ast.Stmt:
        expr = self._parse_expr()
        if self._match(TokenKind.EQ):
            return ast.AssignStmt(expr.span, expr, self._parse_expr())
        return ast.ExprStmt(expr.span, expr)

    def _parse_select_expr(self, start: Span) -> ast.SelectExpr:
        self._expect(TokenKind.LBRACE, "select 缺少 {", code="E004")
        cases: list[ast.SelectCase] = []
        while not self._at(TokenKind.RBRACE) and not self._at(TokenKind.EOF):
            if self._match(TokenKind.RECV):
                self._expect(TokenKind.LPAREN, "recv 缺少 (")
                ch = self._parse_expr()
                self._expect(TokenKind.RPAREN, "recv 缺少 )", code="E004")
                self._expect(TokenKind.FATARROW, "recv 分支缺少 =>")
                cases.append(ast.SelectCase(start, "recv", ch, None, self._parse_block()))
            elif self._match(TokenKind.SEND):
                self._expect(TokenKind.LPAREN, "send 缺少 (")
                ch = self._parse_expr()
                self._expect(TokenKind.COMMA, "send 缺少 ,")
                v = self._parse_expr()
                self._expect(TokenKind.RPAREN, "send 缺少 )", code="E004")
                self._expect(TokenKind.FATARROW, "send 分支缺少 =>")
                cases.append(ast.SelectCase(start, "send", ch, v, self._parse_block()))
            elif self._match(TokenKind.DEFAULT):
                self._expect(TokenKind.FATARROW, "default 分支缺少 =>")
                cases.append(ast.SelectCase(start, "default", None, None, self._parse_block()))
            else:
                self._error_here("select 子句非法")
                self._sync_stmt()
        self._expect(TokenKind.RBRACE, "select 缺少 }", code="E004")
        return ast.SelectExpr(start, None, cases)

    def _parse_type_ref(self) -> ast.TypeRef:
        name = self._expect(TokenKind.IDENT, "期望类型名")
        params: list[ast.TypeRef] = []
        if self._match(TokenKind.LBRACKET):
            while not self._at(TokenKind.RBRACKET) and not self._at(TokenKind.EOF):
                params.append(self._parse_type_ref())
                if not self._match(TokenKind.COMMA):
                    break
            self._expect(TokenKind.RBRACKET, "类型参数缺少 ]", code="E004")
        return ast.TypeRef(name.span, name.lexeme, params)

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
            lhs = self._parse_interpolated_string(tok) if self._has_interpolation(tok.lexeme) else ast.StrLit(tok.span, None, tok.lexeme)
        elif tok.kind in {TokenKind.IDENT, TokenKind.SEND, TokenKind.RECV}:
            lhs = ast.NameExpr(tok.span, None, tok.lexeme)
            if isinstance(lhs, ast.NameExpr) and lhs.name[:1].isupper() and self._at(TokenKind.LBRACE):
                lhs = self._parse_struct_lit(lhs)
        elif tok.kind == TokenKind.SELECT:
            lhs = self._parse_select_expr(tok.span)
        elif tok.kind == TokenKind.MATCH:
            lhs = self._parse_match_expr(tok.span)
        elif tok.kind == TokenKind.FN:
            lhs = self._parse_lambda_expr(tok.span)
        elif tok.kind in (TokenKind.NOT, TokenKind.MINUS):
            lhs = ast.UnaryExpr(tok.span, None, tok.lexeme, self._parse_expr(7))
        elif tok.kind == TokenKind.LPAREN:
            lhs = self._parse_expr()
            self._expect(TokenKind.RPAREN, "缺少 )", code="E004")
        elif tok.kind == TokenKind.LBRACE:
            lhs = self._parse_dict_lit(tok.span) if self._looks_like_dict_lit() else ast.BlockExpr(tok.span, None, self._parse_block_after_lbrace(tok.span))
        elif tok.kind == TokenKind.LBRACKET:
            elements: list[ast.Expr] = []
            if not self._at(TokenKind.RBRACKET):
                while True:
                    elements.append(self._parse_expr())
                    if not self._match(TokenKind.COMMA):
                        break
            self._expect(TokenKind.RBRACKET, "数组字面量缺少 ]", code="E004")
            lhs = ast.ArrayLit(tok.span, None, elements)
        else:
            self.diag.error(tok.span, f"非法表达式起始: {tok.kind.name}", code="E005")
            lhs = ast.IntLit(tok.span, None, 0)

        while True:
            if self._at(TokenKind.LPAREN):
                self._advance()
                args: list[ast.Expr] = []
                if not self._at(TokenKind.RPAREN):
                    while True:
                        args.append(self._parse_expr())
                        if not self._match(TokenKind.COMMA):
                            break
                rp = self._expect(TokenKind.RPAREN, "缺少 )", code="E004")
                lhs = ast.CallExpr(rp.span, None, lhs, args)
                continue
            if self._match(TokenKind.LBRACKET):
                start_expr = None
                if not self._at(TokenKind.DOTDOT) and not self._at(TokenKind.DOTDOTEQ):
                    start_expr = self._parse_expr(PRECEDENCE[TokenKind.DOTDOT] + 1)
                if self._at(TokenKind.DOTDOT) or self._at(TokenKind.DOTDOTEQ):
                    inclusive = self._advance().kind == TokenKind.DOTDOTEQ
                    end_expr = None if self._at(TokenKind.RBRACKET) else self._parse_expr()
                    rb = self._expect(TokenKind.RBRACKET, "slice missing ]", code="E004")
                    lhs = ast.SliceExpr(rb.span, None, lhs, start_expr, end_expr, inclusive)
                    continue
                index = start_expr or ast.IntLit(self._peek().span, None, 0)
                rb = self._expect(TokenKind.RBRACKET, "索引访问缺少 ]", code="E004")
                lhs = ast.IndexExpr(rb.span, None, lhs, index)
                continue
            if self._match(TokenKind.DOT):
                field = self._expect(TokenKind.IDENT, "字段访问缺少字段名")
                lhs = ast.FieldAccess(field.span, None, lhs, field.lexeme)
                continue
            op = self._peek().kind
            if op not in PRECEDENCE:
                break
            bp = PRECEDENCE[op]
            if bp < min_bp:
                break
            op_tok = self._advance()
            rhs = self._parse_expr(bp + 1)
            if op_tok.kind == TokenKind.PIPEGT:
                if isinstance(rhs, ast.CallExpr):
                    rhs.args.insert(0, lhs)
                    lhs = rhs
                else:
                    lhs = ast.CallExpr(op_tok.span, None, rhs, [lhs])
            elif op_tok.kind in {TokenKind.DOTDOT, TokenKind.DOTDOTEQ}:
                lhs = ast.RangeExpr(op_tok.span, None, lhs, rhs, op_tok.kind == TokenKind.DOTDOTEQ)
            else:
                lhs = ast.BinaryExpr(op_tok.span, None, op_tok.lexeme, lhs, rhs)
        return lhs

    def _has_interpolation(self, text: str) -> bool:
        i = 0
        while i < len(text):
            if text[i] == "{" and i + 1 < len(text) and text[i + 1] != "{":
                j = i + 1
                while j < len(text) and text[j].isspace():
                    j += 1
                return j < len(text) and (text[j].isalpha() or text[j].isdigit() or text[j] in "(_-!")
            i += 1
        return False

    def _parse_interpolated_string(self, token: Token) -> ast.InterpolatedString:
        parts: list[str | ast.Expr] = []
        text = token.lexeme
        buf: list[str] = []
        i = 0
        while i < len(text):
            if text[i] == "{" and i + 1 < len(text) and text[i + 1] != "{":
                if buf:
                    parts.append("".join(buf))
                    buf = []
                depth = 1
                j = i + 1
                while j < len(text) and depth:
                    if text[j] == "{":
                        depth += 1
                    elif text[j] == "}":
                        depth -= 1
                    j += 1
                expr_src = text[i + 1 : j - 1].strip()
                if expr_src:
                    from .lexer import Lexer

                    inner_tokens = Lexer(expr_src, self.diag).scan()
                    parts.append(Parser(inner_tokens, self.diag)._parse_expr())
                i = j
                continue
            if text[i] == "{" and i + 1 < len(text) and text[i + 1] == "{":
                buf.append("{")
                i += 2
                continue
            if text[i] == "}" and i + 1 < len(text) and text[i + 1] == "}":
                buf.append("}")
                i += 2
                continue
            buf.append(text[i])
            i += 1
        if buf:
            parts.append("".join(buf))
        return ast.InterpolatedString(token.span, None, parts)

    def _parse_lambda_expr(self, start: Span) -> ast.LambdaExpr:
        self._expect(TokenKind.LPAREN, "lambda missing (", code="E004")
        params: list[ast.LambdaParam] = []
        if not self._at(TokenKind.RPAREN):
            while True:
                name = self._expect(TokenKind.IDENT, "expected lambda parameter")
                type_ref = None
                if self._match(TokenKind.COLON):
                    type_ref = self._parse_type_ref()
                params.append(ast.LambdaParam(name.span, name.lexeme, type_ref))
                if not self._match(TokenKind.COMMA):
                    break
        self._expect(TokenKind.RPAREN, "lambda missing )", code="E004")
        self._expect(TokenKind.FATARROW, "lambda missing =>", code="E004")
        body: ast.Expr | ast.Block
        if self._at(TokenKind.LBRACE):
            body = self._parse_block()
        else:
            body = self._parse_expr()
        return ast.LambdaExpr(start, None, params, body)

    def _parse_match_expr(self, start: Span) -> ast.MatchExpr:
        value = self._parse_expr()
        self._expect(TokenKind.LBRACE, "match missing {", code="E004")
        arms: list[ast.MatchArm] = []
        while not self._at(TokenKind.RBRACE) and not self._at(TokenKind.EOF):
            pat_name = self._expect(TokenKind.IDENT, "expected match pattern")
            binding = None
            if self._match(TokenKind.LPAREN):
                if not self._at(TokenKind.RPAREN):
                    binding = self._expect(TokenKind.IDENT, "expected pattern binding").lexeme
                    while self._match(TokenKind.COMMA):
                        self._expect(TokenKind.IDENT, "expected pattern binding")
                self._expect(TokenKind.RPAREN, "pattern missing )", code="E004")
            self._expect(TokenKind.FATARROW, "match arm missing =>", code="E004")
            if self._at(TokenKind.LBRACE):
                body = self._parse_block()
            elif self._at(TokenKind.RETURN):
                ret_tok = self._advance()
                ret_value = None if self._at(TokenKind.COMMA) or self._at(TokenKind.RBRACE) else self._parse_expr()
                self._match(TokenKind.SEMI)
                body = ast.Block(pat_name.span, [ast.ReturnStmt(ret_tok.span, ret_value)])
            else:
                expr = self._parse_expr()
                body = ast.Block(expr.span, [ast.ExprStmt(expr.span, expr)])
            arms.append(ast.MatchArm(pat_name.span, ast.Pattern(pat_name.span, pat_name.lexeme, binding), body))
            self._match(TokenKind.COMMA)
        self._expect(TokenKind.RBRACE, "match missing }", code="E004")
        return ast.MatchExpr(start, None, value, arms)

    def _looks_like_dict_lit(self) -> bool:
        if self._at(TokenKind.RBRACE):
            return True
        return self._peek().kind in {TokenKind.STRING, TokenKind.IDENT} and self._peek(1).kind == TokenKind.COLON

    def _parse_dict_lit(self, start: Span) -> ast.DictLit:
        entries: list[tuple[ast.Expr, ast.Expr]] = []
        while not self._at(TokenKind.RBRACE) and not self._at(TokenKind.EOF):
            key = self._parse_expr()
            self._expect(TokenKind.COLON, "dict entry missing :", code="E004")
            value = self._parse_expr()
            entries.append((key, value))
            if not self._match(TokenKind.COMMA):
                break
        self._expect(TokenKind.RBRACE, "dict missing }", code="E004")
        return ast.DictLit(start, None, entries)

    def _parse_struct_lit(self, name_expr: ast.NameExpr) -> ast.StructLit:
        self._expect(TokenKind.LBRACE, "结构体字面量缺少 {", code="E004")
        fields: dict[str, ast.Expr] = {}
        while not self._at(TokenKind.RBRACE) and not self._at(TokenKind.EOF):
            field = self._expect(TokenKind.IDENT, "期望字段名")
            self._expect(TokenKind.COLON, "字段初始化缺少 :")
            fields[field.lexeme] = self._parse_expr()
            if not self._match(TokenKind.COMMA):
                break
        self._expect(TokenKind.RBRACE, "结构体字面量缺少 }", code="E004")
        return ast.StructLit(name_expr.span, None, name_expr.name, fields)

    def _parse_type_ref(self) -> ast.TypeRef:
        if self._match(TokenKind.LBRACKET):
            start = self._peek(-1).span
            inner = self._parse_type_ref()
            self._expect(TokenKind.RBRACKET, "array type missing ]", code="E004")
            return ast.TypeRef(start, "Array", [inner, ast.TypeRef(start, "*")])
        name = self._expect(TokenKind.IDENT, "expected type name")
        params: list[ast.TypeRef] = []
        end = None
        if self._match(TokenKind.LBRACKET):
            end = TokenKind.RBRACKET
        elif self._match(TokenKind.LT):
            end = TokenKind.GT
        if end is not None:
            while not self._at(end) and not self._at(TokenKind.EOF):
                params.append(self._parse_type_ref())
                if not self._match(TokenKind.COMMA):
                    break
            self._expect(end, "type parameters are not closed", code="E004")
        return ast.TypeRef(name.span, name.lexeme, params)

    def _peek(self, off: int = 0) -> Token:
        idx = max(self.i + off, 0)
        if idx >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[idx]

    def _advance(self) -> Token:
        token = self._peek()
        self.i = min(self.i + 1, len(self.tokens) - 1)
        return token

    def _at(self, kind: TokenKind) -> bool:
        return self._peek().kind == kind

    def _match(self, kind: TokenKind) -> bool:
        if self._at(kind):
            self._advance()
            return True
        return False

    def _expect(self, kind: TokenKind, msg: str, fix: str | None = None, code: str | None = None) -> Token:
        if self._at(kind):
            return self._advance()
        self.diag.error(self._peek().span, msg, fixits=[fix] if fix else None, code=code)
        return Token(kind, "", self._peek().span)

    def _error_here(self, msg: str) -> None:
        self.diag.error(self._peek().span, msg)

    def _sync_stmt(self) -> None:
        while self._peek().kind not in {TokenKind.SEMI, TokenKind.RBRACE, TokenKind.EOF}:
            self._advance()
        if self._at(TokenKind.SEMI):
            self._advance()

    def _sync_top(self) -> None:
        while self._peek().kind not in {TokenKind.IMPORT, TokenKind.FN, TokenKind.MACRO, TokenKind.STRUCT, TokenKind.ENUM, TokenKind.EOF}:
            self._advance()

    def _span_of(self, idx: int) -> Span:
        if not self.tokens:
            return Span(0, 0, 1, 1)
        return self.tokens[min(idx, len(self.tokens) - 1)].span
