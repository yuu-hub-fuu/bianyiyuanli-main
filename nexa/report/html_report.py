from __future__ import annotations

import html
from pathlib import Path


def _table(title: str, headers: list[str], rows: list[list[str]]) -> str:
    th = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    if not rows:
        body = f"<tr><td colspan='{len(headers)}'><i>(empty)</i></td></tr>"
    else:
        body = "".join(
            "<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in row) + "</tr>"
            for row in rows
        )
    return f"<h2>{html.escape(title)}</h2><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"


def _diagnostics_table(res) -> str:
    if not res.diagnostics:
        return "<h2>Diagnostics</h2><p><i>(empty)</i></p>"
    rows = []
    for d in res.diagnostics:
        level = str(d.level)
        code = getattr(d, "code", "") or ""
        rows.append(
            f"<tr class='diag-{html.escape(level)}'>"
            f"<td>{html.escape(level)}</td>"
            f"<td>{html.escape(code)}</td>"
            f"<td>{html.escape(d.message)}</td>"
            f"<td>{d.span.line}:{d.span.col}</td>"
            "</tr>"
        )
    return "<h2>Diagnostics</h2><table><thead><tr><th>level</th><th>code</th><th>message</th><th>location</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def _single_col(title: str, rows: list[str], col: str = "value") -> str:
    return _table(title, [col], [[r] for r in rows])


def write_html_report(path: Path, res) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    t = res.artifacts.tables
    symbol_rows = [s.split("|") for s in t.get("symbols", []) if "|" in s]
    quad_rows = [[q] for q in t.get("quadruples", [])]

    cfg_rows: list[list[str]] = []
    for fn, lines in res.artifacts.cfg.items():
        for ln in lines:
            cfg_rows.append([fn, ln])
    timeline_rows = [[s.name, s.status, s.detail] for s in res.timeline]

    ast_svg = path.parent / "ast.svg"
    cfg_svgs = sorted(path.parent.glob("cfg_*.svg"))
    embeds = []
    if ast_svg.exists():
        embeds.append(f"<h2>AST SVG</h2><img src='{html.escape(ast_svg.name)}' alt='ast svg'/>")
    for svg in cfg_svgs:
        embeds.append(f"<h2>CFG SVG: {html.escape(svg.name)}</h2><img src='{html.escape(svg.name)}' alt='{html.escape(svg.name)}'/>")

    html_doc = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"/><title>Nexa Course Report</title>
<style>
body{{font-family:Arial,sans-serif;padding:20px;line-height:1.4}}
table{{border-collapse:collapse;width:100%;margin:10px 0 18px}}
th,td{{border:1px solid #ccc;padding:6px 8px;text-align:left;vertical-align:top}}
th{{background:#f2f2f2}} h1,h2{{margin:10px 0 6px}} code{{background:#f5f5f5;padding:1px 4px}}
img{{max-width:100%;border:1px solid #ddd;margin:8px 0 14px}}
.diag-error td{{background:#fff1f1;color:#8a1f1f}}
.diag-warning td{{background:#fff8db;color:#6f5600}}
.diag-note td{{background:#eef6ff;color:#174a7c}}
</style></head><body>
<h1>Nexa Compiler Report</h1>
{_table("Pipeline Timeline", ["Stage", "Status", "Detail"], timeline_rows)}
{_single_col("Keyword Table", t.get("keywords", []), "keyword")}
{_single_col("Delimiter Table", t.get("delimiters", []), "delimiter")}
{_single_col("Identifier Table", t.get("identifiers", []), "identifier")}
{_single_col("Constant Table", t.get("constants", []), "constant")}
{_table("Symbol Table", ["name", "category", "type", "scope", "slot"], symbol_rows)}
{_table("Quadruple Table", ["quadruple"], quad_rows)}
{_table("CFG Section", ["function", "line"], cfg_rows)}
{_table("VM Run Result", ["field", "value"], [["exit", str(res.run_value)], ["stdout", "\\n".join(res.run_stdout)], ["trace_steps", str(len(res.vm_trace))]])}
{_diagnostics_table(res)}
{''.join(embeds) if embeds else '<h2>Embedded SVG</h2><p><i>No AST/CFG SVG found next to report.</i></p>'}
</body></html>"""
    path.write_text(html_doc, encoding="utf-8")
