from __future__ import annotations

import html
from pathlib import Path

# ─── CSS ────────────────────────────────────────────────────────────────────
_CSS = """
:root{
  --bg:#1e1e1e;--bg-card:#252526;--bg-code:#2d2d30;
  --border:#3c3c3c;--text:#d4d4d4;--dim:#858585;
  --blue:#569cd6;--green:#4ec9b0;--yellow:#dcdcaa;
  --orange:#ce9178;--red:#f44747;--purple:#c586c0;
  --accent:#0078d4;--accent-h:#1f8ad4;
  --font-code:'Cascadia Code','Fira Code',Consolas,monospace;
  --font-ui:'Segoe UI',system-ui,sans-serif;
  --r:6px;--tr:.15s ease;
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--text);font-family:var(--font-ui);
  font-size:14px;line-height:1.6;display:flex;min-height:100vh}

/* ── Sidebar ── */
nav{width:210px;min-width:210px;background:var(--bg-card);
  border-right:1px solid var(--border);position:sticky;top:0;height:100vh;
  overflow-y:auto;padding:20px 0;flex-shrink:0;display:flex;flex-direction:column}
.nav-logo{padding:0 18px 18px;border-bottom:1px solid var(--border);margin-bottom:10px}
.nav-logo span{font-size:16px;font-weight:700;color:var(--text)}
.nav-logo sub{font-size:10px;color:var(--dim);display:block;margin-top:2px}
nav h2{font-size:10px;font-weight:700;letter-spacing:.1em;color:var(--dim);
  text-transform:uppercase;padding:12px 18px 6px}
nav a{display:flex;align-items:center;gap:8px;padding:6px 18px;color:var(--dim);
  text-decoration:none;font-size:13px;border-left:2px solid transparent;
  transition:all var(--tr)}
nav a:hover{color:var(--text);background:rgba(255,255,255,.05)}
nav a.active{color:var(--blue);border-left-color:var(--blue);background:rgba(86,156,214,.08)}
.nav-icon{font-size:14px;width:18px;text-align:center}
.nav-badge{margin-left:auto;background:rgba(255,255,255,.1);color:var(--dim);
  padding:1px 6px;border-radius:10px;font-size:10px}
.nav-badge.err{background:rgba(244,71,71,.2);color:var(--red)}
.nav-badge.ok{background:rgba(78,201,176,.2);color:var(--green)}

/* ── Main ── */
main{flex:1;padding:32px 44px;overflow-x:hidden;max-width:1280px}
.page-header{display:flex;align-items:center;justify-content:space-between;
  margin-bottom:28px;padding-bottom:20px;border-bottom:1px solid var(--border)}
.page-header h1{font-size:20px;font-weight:600}
.page-header h1 span{color:var(--blue)}
.status-pill{padding:5px 14px;border-radius:20px;font-size:12px;font-weight:600;
  background:rgba(78,201,176,.15);color:var(--green);border:1px solid rgba(78,201,176,.3)}
.status-pill.err{background:rgba(244,71,71,.15);color:var(--red);border-color:rgba(244,71,71,.3)}

/* ── Stats Grid ── */
.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:14px;margin-bottom:28px}
.stat{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r);
  padding:18px 20px;transition:border-color var(--tr)}
.stat:hover{border-color:var(--accent)}
.stat-val{font-size:26px;font-weight:700;font-family:var(--font-code);color:var(--blue)}
.stat.s-ok .stat-val{color:var(--green)}
.stat.s-err .stat-val{color:var(--red)}
.stat.s-warn .stat-val{color:var(--yellow)}
.stat-lbl{font-size:11px;color:var(--dim);margin-top:4px;text-transform:uppercase;
  letter-spacing:.06em}

/* ── Sections ── */
section{margin-bottom:20px}
details{background:var(--bg-card);border:1px solid var(--border);
  border-radius:var(--r);overflow:hidden}
details+details{margin-top:12px}
summary{padding:13px 18px;cursor:pointer;user-select:none;display:flex;
  align-items:center;gap:10px;font-weight:600;font-size:13px;
  list-style:none;transition:background var(--tr)}
summary::-webkit-details-marker{display:none}
summary:hover{background:rgba(255,255,255,.03)}
details[open] summary{border-bottom:1px solid var(--border)}
.sum-icon{font-size:13px;transition:transform var(--tr)}
details[open] .sum-icon{transform:rotate(90deg)}
.sum-count{margin-left:auto;background:rgba(255,255,255,.08);color:var(--dim);
  padding:2px 8px;border-radius:10px;font-size:11px}

/* ── Tables ── */
.tbl-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:13px}
th{background:rgba(255,255,255,.04);color:var(--dim);font-weight:600;
  font-size:10px;text-transform:uppercase;letter-spacing:.07em;
  padding:10px 14px;text-align:left}
td{padding:8px 14px;border-top:1px solid rgba(255,255,255,.04);vertical-align:top}
tr:hover td{background:rgba(255,255,255,.02)}
.tag-ok{color:var(--green);font-weight:600}
.tag-warn{color:var(--yellow);font-weight:600}
.tag-err{color:var(--red);font-weight:600}
.tag-skip{color:var(--dim)}
.tag-note{color:var(--blue)}
td code{background:rgba(255,255,255,.07);padding:1px 5px;border-radius:3px;
  font-family:var(--font-code);font-size:12px}

/* ── Code Blocks ── */
.code-wrap{position:relative}
.code-wrap pre{font-family:var(--font-code);font-size:12.5px;line-height:1.65;
  padding:16px 20px;overflow-x:auto;color:var(--text);
  background:var(--bg-code);counter-reset:line}
.copy-btn{position:absolute;top:8px;right:8px;background:rgba(255,255,255,.1);
  border:1px solid rgba(255,255,255,.15);color:var(--dim);padding:3px 10px;
  border-radius:4px;font-size:11px;cursor:pointer;opacity:0;
  transition:opacity var(--tr);font-family:var(--font-ui)}
.code-wrap:hover .copy-btn{opacity:1}
.copy-btn:hover{background:rgba(255,255,255,.2);color:var(--text)}

/* ── Timeline ── */
.timeline{padding:6px 0}
.tl-row{display:flex;align-items:center;gap:12px;padding:8px 18px;
  border-bottom:1px solid rgba(255,255,255,.04);font-size:13px;transition:background var(--tr)}
.tl-row:last-child{border-bottom:none}
.tl-row:hover{background:rgba(255,255,255,.02)}
.tl-stage{width:140px;font-weight:500}
.tl-status{width:70px}
.tl-detail{color:var(--dim);flex:1;font-family:var(--font-code);font-size:12px}
.tl-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.dot-ok{background:var(--green)}
.dot-err{background:var(--red)}
.dot-warn{background:var(--yellow)}
.dot-skip{background:var(--dim)}

/* ── Graph Images ── */
.graph-img{max-width:100%;border:1px solid var(--border);border-radius:var(--r);
  display:block;margin:16px 20px}

/* ── Print ── */
@media print{
  :root{--bg:#fff;--bg-card:#f8f8f8;--bg-code:#f0f0f0;
    --border:#ddd;--text:#1a1a1a;--dim:#555}
  nav{display:none}
  main{padding:20px;max-width:100%}
  details{border:1px solid #ddd}
  details[open] summary{background:#f0f0f0}
}
/* Scrollbar */
::-webkit-scrollbar{width:7px;height:7px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:#444;border-radius:4px}
::-webkit-scrollbar-thumb:hover{background:#666}
"""

_JS = """
// Active nav link tracking
const sections = document.querySelectorAll('section[id]');
const navLinks = document.querySelectorAll('nav a[href^="#"]');
const io = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      navLinks.forEach(a => a.classList.remove('active'));
      const a = document.querySelector('nav a[href="#'+e.target.id+'"]');
      if (a) a.classList.add('active');
    }
  });
}, {threshold: 0.25, rootMargin: '-60px 0px -60% 0px'});
sections.forEach(s => io.observe(s));

// Copy buttons
document.querySelectorAll('.copy-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const text = btn.closest('.code-wrap').querySelector('pre').textContent;
    navigator.clipboard.writeText(text).then(() => {
      const orig = btn.textContent;
      btn.textContent = '✓ 已复制';
      btn.style.color = '#4ec9b0';
      setTimeout(() => { btn.textContent = orig; btn.style.color = ''; }, 1800);
    });
  });
});

// Open first details by default
document.querySelectorAll('details:first-of-type').forEach(d => d.open = true);
"""


def _esc(s: str) -> str:
    return html.escape(str(s))


def _tag_class(status: str) -> str:
    s = str(status).lower()
    if s in ("ok", "success", "pass"):
        return "tag-ok"
    if s in ("error", "failed", "fail"):
        return "tag-err"
    if s in ("warning", "warn"):
        return "tag-warn"
    if s in ("skipped", "skip"):
        return "tag-skip"
    if s in ("note", "info"):
        return "tag-note"
    return ""


def _dot_class(status: str) -> str:
    s = str(status).lower()
    if s in ("ok", "success", "pass"):
        return "dot-ok"
    if s in ("error", "failed", "fail"):
        return "dot-err"
    if s in ("warning", "warn"):
        return "dot-warn"
    return "dot-skip"


def _table(headers: list[str], rows: list[list[str]], status_col: int = -1) -> str:
    if not rows:
        return '<p style="color:var(--dim);padding:14px 18px;font-size:13px"><em>(无数据)</em></p>'
    th = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    body_rows = []
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            cls = _tag_class(cell) if i == status_col else ""
            tag = f'<span class="{cls}">{_esc(cell)}</span>' if cls else _esc(cell)
            cells.append(f"<td>{tag}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    return (
        f'<div class="tbl-wrap"><table>'
        f"<thead><tr>{th}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        f"</table></div>"
    )


def _code_block(content: str) -> str:
    if not content.strip():
        return '<p style="color:var(--dim);padding:14px 18px;font-size:13px"><em>(空)</em></p>'
    return (
        f'<div class="code-wrap">'
        f'<button class="copy-btn">复制</button>'
        f"<pre>{_esc(content)}</pre>"
        f"</div>"
    )


def _section(sec_id: str, icon: str, title: str, content: str, count: str = "") -> str:
    cnt_html = f'<span class="sum-count">{_esc(count)}</span>' if count else ""
    return (
        f'<section id="{sec_id}">'
        f"<details>"
        f'<summary><span class="sum-icon">▶</span>'
        f'<span class="nav-icon">{icon}</span>{_esc(title)}{cnt_html}</summary>'
        f"{content}"
        f"</details>"
        f"</section>"
    )


def write_html_report(path: Path, res) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    t = res.artifacts.tables

    # ── Counts ──────────────────────────────────────────────────────────────
    token_rows_raw = t.get("tokens", []) or res.artifacts.token_rows
    n_tokens = len(res.artifacts.token_rows) if hasattr(res.artifacts, "token_rows") else len(t.get("identifiers", []))
    n_symbols = len(res.artifacts.symbol_rows) if hasattr(res.artifacts, "symbol_rows") else 0
    n_err = sum(1 for d in res.diagnostics if str(d.level).lower() == "error")
    n_warn = sum(1 for d in res.diagnostics if str(d.level).lower() == "warning")
    compile_ok = n_err == 0

    # ── Section: Timeline ───────────────────────────────────────────────────
    tl_rows_html = []
    for stage in res.timeline:
        dc = _dot_class(stage.status)
        tc = _tag_class(stage.status)
        tl_rows_html.append(
            f'<div class="tl-row">'
            f'<div class="tl-dot {dc}"></div>'
            f'<div class="tl-stage">{_esc(stage.name)}</div>'
            f'<div class="tl-status"><span class="{tc}">{_esc(stage.status)}</span></div>'
            f'<div class="tl-detail">{_esc(stage.detail)}</div>'
            f"</div>"
        )
    tl_content = f'<div class="timeline">{"".join(tl_rows_html)}</div>'
    sec_timeline = _section("timeline", "⏱", "编译流水线 Timeline",
                             tl_content, str(len(res.timeline)))

    # ── Section: Lexical Tables ──────────────────────────────────────────────
    kw_table = _table(["关键字"], [[k] for k in t.get("keywords", [])])
    dl_table = _table(["分隔符"], [[d] for d in t.get("delimiters", [])])
    id_table = _table(["标识符"], [[i] for i in t.get("identifiers", [])])
    cn_table = _table(["常量"], [[c] for c in t.get("constants", [])])
    lex_content = (
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:0">'
        f'<div><div style="padding:10px 18px 4px;font-size:11px;color:var(--dim);'
        f'font-weight:600;text-transform:uppercase">关键字</div>{kw_table}</div>'
        f'<div><div style="padding:10px 18px 4px;font-size:11px;color:var(--dim);'
        f'font-weight:600;text-transform:uppercase">分隔符</div>{dl_table}</div>'
        f'<div><div style="padding:10px 18px 4px;font-size:11px;color:var(--dim);'
        f'font-weight:600;text-transform:uppercase">标识符</div>{id_table}</div>'
        f'<div><div style="padding:10px 18px 4px;font-size:11px;color:var(--dim);'
        f'font-weight:600;text-transform:uppercase">常量</div>{cn_table}</div>'
        '</div>'
    )
    total_lex = (len(t.get("keywords", [])) + len(t.get("identifiers", [])) +
                 len(t.get("constants", [])) + len(t.get("delimiters", [])))
    sec_lex = _section("lexical", "🔤", "词法表 Lexical Tables", lex_content, str(total_lex))

    # ── Section: Token List ─────────────────────────────────────────────────
    tok_rows = [
        (str(i + 1), r["kind"], r["lexeme"], f'{r["line"]}:{r["col"]}')
        for i, r in enumerate(res.artifacts.token_rows)
    ] if hasattr(res.artifacts, "token_rows") else []
    sec_tokens = _section("tokens", "📋", "Token 序列", _table(["#", "类型", "词素", "位置"], tok_rows), str(len(tok_rows)))

    # ── Section: Symbol Table ───────────────────────────────────────────────
    symbol_rows = [s.split("|") for s in t.get("symbols", []) if "|" in s]
    if not symbol_rows and hasattr(res.artifacts, "symbol_rows"):
        symbol_rows = [(r["name"], r["category"], r["type"], r["scope"], str(r.get("slot", "")))
                       for r in res.artifacts.symbol_rows]
    sec_symbols = _section("symbols", "🗂", "符号表 Symbol Table",
                            _table(["名称", "类别", "类型", "作用域", "槽"], symbol_rows),
                            str(len(symbol_rows)))

    # ── Section: HIR ────────────────────────────────────────────────────────
    quad_rows = t.get("quadruples", [])
    hir_text = ""
    if hasattr(res.artifacts, "hir_raw_structured"):
        def _fmt_hir(rows):
            return "\n".join(f"{r['fn']:<14} {r['index']:>3}  {r['kind']:<13} {r['text']}" for r in rows)
        hir_text = "=== RAW HIR ===\n" + _fmt_hir(res.artifacts.hir_raw_structured)
        hir_text += "\n\n=== OPTIMIZED HIR ===\n" + _fmt_hir(res.artifacts.hir_opt_structured)
    elif quad_rows:
        hir_text = "\n".join(quad_rows)
    sec_hir = _section("hir", "📝", "中间表示 HIR", _code_block(hir_text), str(len(quad_rows) or ""))

    # ── Section: CFG ────────────────────────────────────────────────────────
    cfg_lines: list[str] = []
    for fn, lines in res.artifacts.cfg.items():
        cfg_lines.append(f"── {fn} ──")
        cfg_lines.extend(f"  {ln}" for ln in lines)
        cfg_lines.append("")
    sec_cfg = _section("cfg", "🔀", "控制流图 CFG", _code_block("\n".join(cfg_lines)))

    # ── Section: ASM / LLVM ─────────────────────────────────────────────────
    asm_text = ""
    if hasattr(res.artifacts, "asm") and res.artifacts.asm:
        asm_text = "\n\n".join(f"── {name} ──\n{txt}" for name, txt in res.artifacts.asm.items())
    sec_asm = _section("asm", "⚡", "汇编输出 ASM", _code_block(asm_text))

    llvm_text = res.artifacts.llvm_ir if hasattr(res.artifacts, "llvm_ir") else ""
    sec_llvm = _section("llvm", "🔷", "LLVM IR", _code_block(llvm_text))

    # ── Section: Run Output ─────────────────────────────────────────────────
    run_lines = list(res.run_stdout)
    if res.run_value is not None:
        run_lines.append(f"exit = {res.run_value}")
    run_content = _code_block("\n".join(run_lines) if run_lines else "(未运行)")
    sec_run = _section("run", "▶", "运行输出 Run", run_content)

    # ── Section: Diagnostics ────────────────────────────────────────────────
    diag_rows = [(str(d.level), d.message, f"{d.span.line}:{d.span.col}",
                  (d.fixits[0] if d.fixits else ""))
                 for d in res.diagnostics]
    sec_diag = _section("diagnostics", "🔍", "诊断信息 Diagnostics",
                         _table(["级别", "消息", "位置", "建议修复"], diag_rows, status_col=0),
                         str(len(diag_rows)))

    # ── Section: Graphs ─────────────────────────────────────────────────────
    ast_svg = path.parent / "ast.svg"
    cfg_svgs = sorted(path.parent.glob("cfg_*.svg"))
    graph_items = []
    if ast_svg.exists():
        graph_items.append(f'<p style="padding:12px 18px 4px;color:var(--dim);font-size:12px">AST</p>'
                           f'<img class="graph-img" src="{_esc(ast_svg.name)}" alt="AST"/>')
    for svg in cfg_svgs:
        graph_items.append(f'<p style="padding:12px 18px 4px;color:var(--dim);font-size:12px">'
                           f'CFG: {_esc(svg.name)}</p>'
                           f'<img class="graph-img" src="{_esc(svg.name)}" alt="CFG"/>')
    graph_html = "".join(graph_items) if graph_items else (
        '<p style="padding:14px 18px;color:var(--dim);font-size:13px">'
        '<em>未找到 AST/CFG SVG 图像（需要 Graphviz）</em></p>')
    sec_graphs = _section("graphs", "🌳", "图形化表示 Graphs", graph_html)

    # ── Stats grid ──────────────────────────────────────────────────────────
    stats_html = (
        '<div class="stats-grid">'
        f'<div class="stat"><div class="stat-val">{n_tokens}</div><div class="stat-lbl">Tokens</div></div>'
        f'<div class="stat"><div class="stat-val">{n_symbols}</div><div class="stat-lbl">符号</div></div>'
        f'<div class="stat s-err"><div class="stat-val">{n_err}</div><div class="stat-lbl">错误</div></div>'
        f'<div class="stat s-warn"><div class="stat-val">{n_warn}</div><div class="stat-lbl">警告</div></div>'
        f'<div class="stat s-ok"><div class="stat-val">{len(res.timeline)}</div><div class="stat-lbl">编译阶段</div></div>'
        f'<div class="stat"><div class="stat-val">{len(res.vm_trace)}</div><div class="stat-lbl">跟踪步骤</div></div>'
        '</div>'
    )

    # ── Nav badges ──────────────────────────────────────────────────────────
    err_badge = (f'<span class="nav-badge err">{n_err}</span>' if n_err
                 else f'<span class="nav-badge ok">✓</span>')
    pill_cls = "" if compile_ok else " err"
    pill_txt = "编译成功" if compile_ok else f"{n_err} 个错误"

    # ── Full document ────────────────────────────────────────────────────────
    doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Nexa 编译报告</title>
<style>{_CSS}</style>
</head>
<body>

<nav>
  <div class="nav-logo">
    <span>Nexa Studio</span>
    <sub>编译报告</sub>
  </div>
  <h2>概览</h2>
  <a href="#stats" class="nav-icon-link"><span class="nav-icon">📊</span>统计数据</a>
  <h2>编译产物</h2>
  <a href="#timeline"><span class="nav-icon">⏱</span>流水线</a>
  <a href="#lexical"><span class="nav-icon">🔤</span>词法表</a>
  <a href="#tokens"><span class="nav-icon">📋</span>Tokens</a>
  <a href="#symbols"><span class="nav-icon">🗂</span>符号表</a>
  <a href="#hir"><span class="nav-icon">📝</span>HIR</a>
  <a href="#cfg"><span class="nav-icon">🔀</span>CFG</a>
  <a href="#asm"><span class="nav-icon">⚡</span>ASM</a>
  <a href="#llvm"><span class="nav-icon">🔷</span>LLVM IR</a>
  <h2>输出</h2>
  <a href="#run"><span class="nav-icon">▶</span>运行输出</a>
  <a href="#diagnostics"><span class="nav-icon">🔍</span>诊断 {err_badge}</a>
  <a href="#graphs"><span class="nav-icon">🌳</span>图形</a>
</nav>

<main>
  <div class="page-header">
    <h1>Nexa <span>编译报告</span></h1>
    <span class="status-pill{pill_cls}">{pill_txt}</span>
  </div>

  <section id="stats">
    {stats_html}
  </section>

  {sec_timeline}
  {sec_lex}
  {sec_tokens}
  {sec_symbols}
  {sec_hir}
  {sec_cfg}
  {sec_asm}
  {sec_llvm}
  {sec_run}
  {sec_diag}
  {sec_graphs}
</main>

<script>{_JS}</script>
</body>
</html>"""

    path.write_text(doc, encoding="utf-8")
