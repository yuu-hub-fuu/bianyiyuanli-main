"""FastAPI + WebSocket IDE server."""

from __future__ import annotations

import asyncio
import json
import threading
import webbrowser
from pathlib import Path
from typing import Any

from nexa.compiler import BuildResult, StageResult, compile_source


HOST = "127.0.0.1"
PORT = 7373
URL = f"http://localhost:{PORT}"


HTML_PAGE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Nexa IDE</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5/css/xterm.css"/>
  <script src="https://cdn.jsdelivr.net/npm/split.js@1.6.5/dist/split.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/xterm@5/lib/xterm.js"></script>
  <style>
    :root {
      --bg:#1e1e1e; --sidebar:#252526; --panel:#2d2d30; --tab-bar:#2d2d30;
      --tab-active:#1e1e1e; --accent:#007acc; --fg:#d4d4d4; --fg-dim:#858585;
      --green:#4ec9b0; --yellow:#dcdcaa; --red:#f44747; --orange:#ce9178;
      --blue:#569cd6; --border:#3c3c3c;
      --font-code:'Cascadia Code','Fira Code',Consolas,monospace;
      --font-ui:-apple-system,'Segoe UI',sans-serif;
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; margin: 0; overflow: hidden; background: var(--bg); color: var(--fg); font-family: var(--font-ui); }
    button, select, input { font: inherit; }
    #app { height: 100vh; display: grid; grid-template-rows: 38px minmax(0, 1fr) 22%; }
    .toolbar { display: flex; align-items: center; gap: 8px; padding: 4px 10px; background: var(--sidebar); border-bottom: 1px solid var(--border); }
    .toolbar button, .toolbar select {
      background: transparent; border: 1px solid var(--border); color: var(--fg); border-radius: 4px; padding: 4px 12px; min-height: 28px;
    }
    .toolbar button:hover, .toolbar select:hover { border-color: var(--accent); }
    #runBtn { background: var(--accent); border-color: var(--accent); color: white; }
    .status { margin-left: auto; color: var(--fg-dim); font-size: 12px; }
    #main { min-height: 0; display: flex; }
    #editorPane, #outputPane { min-width: 0; min-height: 0; }
    #editorPane { background: var(--bg); }
    #outputPane { display: grid; grid-template-rows: 34px minmax(0, 1fr); background: var(--panel); border-left: 1px solid var(--border); }
    .gutter.gutter-horizontal { cursor: col-resize; background: var(--border); }
    .tabbar { display: flex; align-items: stretch; overflow-x: auto; background: var(--tab-bar); border-bottom: 1px solid var(--border); }
    .tab {
      appearance: none; border: 0; border-right: 1px solid var(--border); border-bottom: 2px solid transparent;
      border-radius: 0; background: var(--tab-bar); color: var(--fg-dim); padding: 7px 12px; white-space: nowrap;
    }
    .tab.active { color: var(--fg); background: var(--tab-active); border-bottom-color: var(--accent); }
    #content { min-height: 0; overflow: auto; padding: 12px; background: var(--bg); }
    #diagPane { min-height: 78px; background: var(--panel); border-top: 1px solid var(--border); display: grid; grid-template-rows: 28px minmax(0, 1fr); }
    .diagHead { display: flex; align-items: center; gap: 8px; padding: 4px 10px; background: var(--tab-bar); color: var(--fg-dim); border-bottom: 1px solid var(--border); }
    #diagList { overflow: auto; font-family: var(--font-code); font-size: 12px; }
    .diagRow { border-bottom: 1px solid var(--border); padding: 6px 10px; cursor: pointer; }
    .diagRow:hover { background: #333337; }
    .badge { display: inline-block; min-width: 54px; text-align: center; border-radius: 3px; padding: 1px 5px; margin-right: 8px; color: #111; font-size: 11px; }
    .badge.error { background: var(--red); color: white; }
    .badge.warning { background: var(--yellow); }
    .badge.note { background: var(--fg-dim); color: white; }
    .fix { margin: 5px 5px 0 0; color: var(--fg); background: transparent; border: 1px dashed var(--fg-dim); border-radius: 4px; padding: 2px 8px; }
    table { width: 100%; border-collapse: collapse; font-family: var(--font-code); font-size: 12px; }
    th, td { border-bottom: 1px solid var(--border); padding: 6px 8px; text-align: left; vertical-align: top; }
    th { color: var(--fg-dim); background: var(--panel); position: sticky; top: 0; }
    tr:nth-child(odd) td { background: #252526; }
    tr:nth-child(even) td { background: #2d2d30; }
    pre, .code { margin: 0; font-family: var(--font-code); font-size: 12px; line-height: 1.45; white-space: pre-wrap; }
    details { font-family: var(--font-code); margin-left: 16px; }
    summary { cursor: pointer; padding: 2px 0; }
    .kw, .decl { color: var(--blue); } .lit, .type { color: var(--orange); } .ident, .reg, .ret { color: var(--green); }
    .delim, .comment, .dim { color: var(--fg-dim); } .stmt, .op { color: var(--yellow); } .branch { color: var(--red); }
    .hirLine { display: grid; grid-template-columns: 52px 92px minmax(0, 1fr); gap: 8px; font-family: var(--font-code); padding: 3px 0; border-bottom: 1px solid #292929; }
    .subtabs { display: flex; gap: 6px; margin-bottom: 10px; }
    .subtabs button { background: transparent; color: var(--fg); border: 1px solid var(--border); border-radius: 4px; padding: 3px 10px; }
    .subtabs button.active { border-color: var(--accent); color: white; }
    .timelineRow { display: grid; grid-template-columns: 140px minmax(120px, 1fr) 1.5fr; gap: 10px; align-items: center; margin: 7px 0; }
    .bar { height: 13px; border-radius: 3px; background: var(--fg-dim); }
    .bar.ok { background: var(--green); } .bar.warning { background: var(--yellow); } .bar.failed { background: var(--red); } .bar.skipped { background: #555; }
    svg text { fill: var(--fg); font-family: var(--font-code); font-size: 12px; }
    .cm-editor { height: 100%; background: var(--bg); color: var(--fg); font-family: var(--font-code); }
    .cm-scroller { font-family: var(--font-code) !important; }
    .cm-focused { outline: none !important; }
  </style>
</head>
<body>
  <div id="app">
    <div class="toolbar">
      <button id="runBtn">Run</button>
      <button id="compileBtn">Compile</button>
      <select id="mode"><option value="full">full</option><option value="core">core</option></select>
      <button id="openBtn">Open</button>
      <button id="saveBtn">Save</button>
      <input id="pathInput" placeholder="~/example.nx" style="width:260px;background:var(--bg);border:1px solid var(--border);color:var(--fg);padding:4px 8px;border-radius:4px"/>
      <span id="status" class="status">connecting...</span>
    </div>
    <div id="main">
      <section id="editorPane"><div id="editor"></div></section>
      <section id="outputPane">
        <div id="tabs" class="tabbar"></div>
        <div id="content"></div>
      </section>
    </div>
    <section id="diagPane">
      <div class="diagHead"><strong>Diagnostics</strong><span id="diagCount">0</span></div>
      <div id="diagList"></div>
    </section>
  </div>
  <script type="module">
    import {EditorView, basicSetup} from "https://esm.sh/codemirror@6";
    import {StreamLanguage} from "https://esm.sh/@codemirror/language@6";
    import {syntaxHighlighting, HighlightStyle} from "https://esm.sh/@codemirror/language@6";
    import {tags} from "https://esm.sh/@lezer/highlight@1";

    const state = {stages: [], diagnostics: [], tokens: [], ast: "", symbols: [], hir: {raw: [], opt: []}, cfg: {}, asm: {}, llvm: "", run: null, trace: [], tab: "Tokens", hirTab: "opt"};
    const tabs = ["Tokens","AST","Symbols","HIR","CFG","ASM","LLVM","Timeline","Trace"];
    const status = document.querySelector("#status");
    const content = document.querySelector("#content");
    const diagList = document.querySelector("#diagList");
    const diagCount = document.querySelector("#diagCount");
    let ws, debounceTimer, term;

    const nxMode = StreamLanguage.define({
      token(stream) {
        if (stream.match("//")) { stream.skipToEnd(); return "comment"; }
        if (stream.match(/"(?:[^"\\]|\\.)*"/)) return "string";
        if (stream.match(/\d+/)) return "number";
        if (stream.match(/\b(fn|let|return|if|else|while|struct|macro|spawn|select|recv|send|default|true|false)\b/)) return "keyword";
        if (stream.match(/[+\-*/%=!<>|&]+/)) return "operator";
        if (stream.match(/[()[\]{},;:.]/)) return "bracket";
        stream.next(); return null;
      }
    });
    const highlights = HighlightStyle.define([
      {tag: tags.keyword, color: "var(--blue)"}, {tag: tags.number, color: "var(--orange)"},
      {tag: tags.string, color: "var(--orange)"}, {tag: tags.comment, color: "var(--fg-dim)"},
      {tag: tags.operator, color: "var(--fg)"}, {tag: tags.bracket, color: "var(--fg-dim)"}
    ]);
    const editor = new EditorView({
      doc: "fn main() -> i32 {\n  let a: i32 = 1 + 2 * 3;\n  return a;\n}\n",
      extensions: [basicSetup, nxMode, syntaxHighlighting(highlights), EditorView.updateListener.of(v => { if (v.docChanged) scheduleCompile(); })],
      parent: document.querySelector("#editor")
    });

    Split(["#editorPane", "#outputPane"], {sizes:[42,58], minSize:[260,360], gutterSize:4});
    document.querySelector("#tabs").innerHTML = tabs.map(t => `<button class="tab ${t===state.tab?"active":""}" data-tab="${t}">${t}</button>`).join("");
    document.querySelector("#tabs").addEventListener("click", e => { if (e.target.dataset.tab) { state.tab = e.target.dataset.tab; render(); } });
    document.querySelector("#compileBtn").onclick = () => sendCompile(false);
    document.querySelector("#runBtn").onclick = () => sendCompile(true);
    document.querySelector("#openBtn").onclick = openFile;
    document.querySelector("#saveBtn").onclick = saveFile;

    function connect() {
      ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
      ws.onopen = () => { status.textContent = "ready"; sendCompile(false); };
      ws.onclose = () => { status.textContent = "disconnected; retrying"; setTimeout(connect, 900); };
      ws.onerror = () => status.textContent = "socket error";
      ws.onmessage = ev => handleMessage(JSON.parse(ev.data));
    }
    connect();

    function scheduleCompile() { clearTimeout(debounceTimer); debounceTimer = setTimeout(() => sendCompile(false), 600); }
    function sendCompile(run) {
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      state.stages = []; state.diagnostics = []; status.textContent = run ? "running..." : "compiling...";
      ws.send(JSON.stringify({action:"compile", source: editor.state.doc.toString(), mode: document.querySelector("#mode").value, run, trace: run}));
      render();
    }
    async function openFile() {
      const path = document.querySelector("#pathInput").value.trim();
      if (!path) return;
      const res = await fetch(`/file?path=${encodeURIComponent(path)}`);
      const data = await res.json();
      if (data.ok) { editor.dispatch({changes:{from:0, to:editor.state.doc.length, insert:data.source}}); status.textContent = `opened ${data.path}`; }
      else status.textContent = data.error;
    }
    async function saveFile() {
      const path = document.querySelector("#pathInput").value.trim();
      if (!path) return;
      const res = await fetch("/file", {method:"POST", headers:{"content-type":"application/json"}, body:JSON.stringify({path, source:editor.state.doc.toString()})});
      const data = await res.json(); status.textContent = data.ok ? `saved ${data.path}` : data.error;
    }
    function handleMessage(msg) {
      if (msg.type === "stage") state.stages.push(msg);
      if (msg.type === "diagnostics") state.diagnostics = msg.items || [];
      if (msg.type === "tokens") state.tokens = msg.data || [];
      if (msg.type === "ast") state.ast = msg.data || "";
      if (msg.type === "symbols") state.symbols = msg.data || [];
      if (msg.type === "hir") state.hir = {raw: msg.raw || [], opt: msg.opt || []};
      if (msg.type === "cfg") state.cfg = msg.data || {};
      if (msg.type === "asm") state.asm = msg.data || {};
      if (msg.type === "llvm") state.llvm = msg.data || "";
      if (msg.type === "run") state.run = msg;
      if (msg.type === "trace") state.trace = msg.data || [];
      if (msg.type === "done") status.textContent = state.diagnostics.some(d => d.level === "error") ? "errors" : "done";
      render();
    }
    function esc(v) { return String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }
    function badgeKind(kind) {
      const k = String(kind).toLowerCase();
      const cls = k.includes("fn") || k.includes("let") || k.includes("return") || k.includes("if") || k.includes("while") ? "kw" : k.includes("int") || k.includes("string") || k.includes("true") || k.includes("false") ? "lit" : k.includes("ident") ? "ident" : k.includes("paren") || k.includes("brace") || k.includes("semi") ? "delim" : "";
      return `<span class="${cls}">${esc(kind)}</span>`;
    }
    function renderTable(headers, rows) {
      return `<table><thead><tr>${headers.map(h=>`<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.join("") || `<tr><td colspan="${headers.length}">(empty)</td></tr>`}</tbody></table>`;
    }
    function renderAst() {
      const lines = state.ast.split(/\r?\n/).filter(Boolean);
      let html = "", stack = [];
      for (const line of lines) {
        const indent = (line.match(/^ */)[0].length / 2) | 0;
        while (stack.length > indent) { html += "</details>"; stack.pop(); }
        const name = line.trim();
        const cls = /Stmt|If|While|Return|Let|Assign/.test(name) ? "stmt" : /Expr|Lit|Name|Binary|Unary/.test(name) ? "ident" : "decl";
        html += `<details open><summary><span class="${cls}">${esc(name)}</span></summary>`;
        stack.push(name);
      }
      while (stack.length) { html += "</details>"; stack.pop(); }
      return html || `<pre class="dim">(empty)</pre>`;
    }
    function renderHir() {
      const data = state.hir[state.hirTab] || [];
      const rows = data.map(i => {
        const cls = i.kind === "CONST" ? "lit" : /BIN|UNARY/.test(i.kind) ? "op" : i.kind === "CALL" ? "kw" : /BRANCH/.test(i.kind) ? "branch" : i.kind === "RET" ? "ret" : i.kind === "JUMP" ? "dim" : "";
        return `<div class="hirLine"><span class="dim">${esc(i.fn)}:${i.index}</span><span class="${cls}">${esc(i.kind)}</span><span>${esc(i.text)}</span></div>`;
      }).join("");
      return `<div class="subtabs"><button class="${state.hirTab==="raw"?"active":""}" data-hir="raw">Raw</button><button class="${state.hirTab==="opt"?"active":""}" data-hir="opt">Optimized</button></div><div id="hirRows">${rows || `<pre class="dim">(empty)</pre>`}</div>`;
    }
    function renderCfg() {
      const first = Object.entries(state.cfg)[0];
      if (!first) return `<pre class="dim">(empty)</pre>`;
      const [fn, graph] = first, blocks = graph.blocks || [], edges = graph.edges || [];
      const w = 860, bw = 210, bh = 76, gapY = 120;
      const pos = new Map(blocks.map((b, i) => [b.id, {x: 40 + (i % 3) * 270, y: 48 + Math.floor(i / 3) * gapY}]));
      const rects = blocks.map(b => { const p = pos.get(b.id); return `<rect x="${p.x}" y="${p.y}" width="${bw}" height="${bh}" rx="6" fill="#252526" stroke="var(--border)"/><text x="${p.x+10}" y="${p.y+20}" fill="var(--yellow)">${esc(b.id)}</text><text x="${p.x+10}" y="${p.y+42}">${esc((b.instrs||[])[0]||"")}</text>`; }).join("");
      const es = edges.map(e => { const a = pos.get(e.from), b = pos.get(e.to); if (!a || !b) return ""; const x1=a.x+bw/2,y1=a.y+bh,x2=b.x+bw/2,y2=b.y; const color=e.label==="true"?"var(--green)":e.label==="false"?"var(--red)":"var(--fg-dim)"; return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${color}" marker-end="url(#arrow)"/><text x="${(x1+x2)/2+4}" y="${(y1+y2)/2-4}" fill="${color}">${esc(e.label)}</text>`; }).join("");
      const h = Math.max(260, 80 + Math.ceil(blocks.length / 3) * gapY);
      return `<h3>${esc(fn)}</h3><svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="var(--fg-dim)"/></marker></defs>${es}${rects}</svg>`;
    }
    function hiAsm(text) {
      return esc(text).replace(/^([A-Za-z_.$][\w.$]*:)/gm, '<span class="stmt">$1</span>').replace(/\b(r(?:ax|bx|cx|dx|bp|sp|di|si|1[0-5]|8|9)|e[a-d]x)\b/g, '<span class="reg">$1</span>').replace(/(;.*)$/gm, '<span class="comment">$1</span>');
    }
    function hiLlvm(text) {
      return esc(text).replace(/\b(define|declare|private|constant|ret|br|call)\b/g, '<span class="kw">$1</span>').replace(/%[\w.]+/g, '<span class="reg">$&</span>').replace(/\b(i32|i1|i8\*|void)\b/g, '<span class="type">$1</span>').replace(/\b(add|sub|mul|sdiv|srem|icmp|zext|getelementptr)\b/g, '<span class="op">$1</span>');
    }
    function renderTimeline() {
      return state.stages.map(s => `<div class="timelineRow"><span>${esc(s.name)}</span><div class="bar ${esc(s.status)}"></div><span class="dim">${esc(s.status)} ${esc(s.detail)}</span></div>`).join("") || `<pre class="dim">(empty)</pre>`;
    }
    function renderTrace() {
      setTimeout(() => {
        const host = document.querySelector("#terminal");
        if (!host || !window.Terminal) return;
        host.innerHTML = "";
        term = new Terminal({theme:{background:"#1e1e1e", foreground:"#d4d4d4"}, fontFamily:"Cascadia Code, Consolas, monospace", fontSize:12});
        term.open(host);
        const frames = state.trace.slice(-5000);
        frames.forEach((f, i) => term.writeln(`\x1b[90m#${String(i+1).padStart(4,"0")}\x1b[0m \x1b[36m${f.fn}@${f.ip}\x1b[0m  \x1b[33m${f.instr}\x1b[0m  ${JSON.stringify(f.env)}`));
        if (state.run) term.writeln(`\r\nexit=${state.run.value} stdout=${JSON.stringify(state.run.stdout || [])}`);
      });
      return `<div id="terminal" style="height:100%;min-height:360px"></div>`;
    }
    function renderDiagnostics() {
      diagCount.textContent = state.diagnostics.length;
      diagList.innerHTML = state.diagnostics.map((d, idx) => `<div class="diagRow" data-line="${d.line}" data-col="${d.col}"><span class="badge ${esc(d.level)}">${esc(d.level)}</span>${esc(d.message)} <span class="dim">@ ${d.line}:${d.col}</span>${(d.notes||[]).map(n=>`<div class="dim">note: ${esc(n)}</div>`).join("")}${(d.fixits||[]).map(f=>`<button class="fix" data-fix="${idx}">${esc(f)}</button>`).join("")}</div>`).join("") || `<div class="diagRow dim">No diagnostics</div>`;
    }
    diagList.addEventListener("click", e => {
      const row = e.target.closest(".diagRow");
      if (!row) return;
      const line = Number(row.dataset.line || 1);
      const pos = editor.state.doc.line(Math.max(1, line)).from;
      editor.dispatch({selection:{anchor:pos}, scrollIntoView:true});
      editor.focus();
      if (e.target.dataset.fix !== undefined && /;/.test(e.target.textContent)) editor.dispatch({changes:{from:pos, insert:";"}});
    });
    content.addEventListener("click", e => { if (e.target.dataset.hir) { state.hirTab = e.target.dataset.hir; render(); } });
    function render() {
      document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t.dataset.tab === state.tab));
      if (state.tab === "Tokens") content.innerHTML = renderTable(["#","Kind","Lexeme","Line:Col"], state.tokens.map((t,i)=>`<tr><td>${i+1}</td><td>${badgeKind(t.kind)}</td><td>${esc(t.lexeme)}</td><td>${t.line}:${t.col}</td></tr>`));
      if (state.tab === "AST") content.innerHTML = renderAst();
      if (state.tab === "Symbols") content.innerHTML = renderTable(["Name","Category","Type","Scope","Slot"], state.symbols.map(s=>`<tr><td>${esc(s.name)}</td><td><span class="badge note">${esc(s.category)}</span></td><td>${esc(s.type)}</td><td>${esc(s.scope)}</td><td>${esc(s.slot)}</td></tr>`));
      if (state.tab === "HIR") content.innerHTML = renderHir();
      if (state.tab === "CFG") content.innerHTML = renderCfg();
      if (state.tab === "ASM") content.innerHTML = `<pre>${hiAsm(Object.entries(state.asm).map(([k,v])=>`; ${k}\n${v}`).join("\n"))}</pre>`;
      if (state.tab === "LLVM") content.innerHTML = `<pre>${hiLlvm(state.llvm)}</pre>`;
      if (state.tab === "Timeline") content.innerHTML = renderTimeline();
      if (state.tab === "Trace") content.innerHTML = renderTrace();
      renderDiagnostics();
    }
    render();
  </script>
</body>
</html>
"""


def _stage_message(stage: StageResult) -> dict[str, Any]:
    return {"type": "stage", "name": stage.name, "status": stage.status, "detail": stage.detail}


def _diagnostic_rows(res: BuildResult) -> list[dict[str, Any]]:
    return [
        {
            "level": str(d.level),
            "message": d.message,
            "line": d.span.line,
            "col": d.span.col,
            "notes": list(d.notes),
            "fixits": list(d.fixits),
        }
        for d in res.diagnostics
    ]


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    return repr(value)


def _trace_rows(res: BuildResult) -> list[dict[str, Any]]:
    return [
        {"fn": f.fn, "ip": f.ip, "instr": f.instr, "env": _json_safe(f.env), "stdout": list(f.stdout)}
        for f in res.vm_trace[-5000:]
    ]


def _result_messages(res: BuildResult) -> list[dict[str, Any]]:
    return [
        {"type": "diagnostics", "items": _diagnostic_rows(res)},
        {"type": "tokens", "data": res.artifacts.token_rows},
        {"type": "ast", "data": res.artifacts.ast_text},
        {"type": "symbols", "data": res.artifacts.symbol_rows},
        {"type": "hir", "raw": res.artifacts.hir_raw_structured, "opt": res.artifacts.hir_opt_structured},
        {"type": "cfg", "data": res.artifacts.cfg_structured},
        {"type": "asm", "data": res.artifacts.asm},
        {"type": "llvm", "data": res.artifacts.llvm_ir},
        {"type": "run", "value": res.run_value, "stdout": res.run_stdout},
        {"type": "trace", "data": _trace_rows(res)},
        {"type": "done"},
    ]


def _home_path(raw: str) -> Path:
    home = Path.home().resolve()
    text = raw.strip()
    if text.startswith("~"):
        path = Path(text).expanduser()
    else:
        path = Path(text)
        if not path.is_absolute():
            path = home / path
    resolved = path.resolve()
    if resolved != home and home not in resolved.parents:
        raise ValueError("file access is limited to your home directory")
    return resolved


def create_app():
    try:
        from fastapi import FastAPI, WebSocket, WebSocketDisconnect
        from fastapi.responses import HTMLResponse, JSONResponse
    except ImportError as exc:  # pragma: no cover - exercised by launch smoke tests
        raise RuntimeError("Missing IDE dependencies. Install with: python -m pip install -e .") from exc

    app = FastAPI(title="Nexa IDE")

    @app.get("/")
    async def index():
        return HTMLResponse(HTML_PAGE)

    @app.get("/file")
    async def read_file(path: str):
        try:
            target = _home_path(path)
            return {"ok": True, "path": str(target), "source": target.read_text(encoding="utf-8")}
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

    @app.post("/file")
    async def write_file(payload: dict[str, str]):
        try:
            target = _home_path(payload.get("path", ""))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(payload.get("source", ""), encoding="utf-8")
            return {"ok": True, "path": str(target)}
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws.accept()
        loop = asyncio.get_running_loop()
        try:
            while True:
                payload = json.loads(await ws.receive_text())
                if payload.get("action") != "compile":
                    await ws.send_json({"type": "error", "message": "unknown action"})
                    continue

                def on_stage(stage: StageResult) -> None:
                    fut = asyncio.run_coroutine_threadsafe(ws.send_json(_stage_message(stage)), loop)
                    try:
                        fut.result(timeout=3)
                    except Exception:
                        pass

                res = await loop.run_in_executor(
                    None,
                    lambda: compile_source(
                        payload.get("source", ""),
                        mode=payload.get("mode", "full"),
                        run=bool(payload.get("run")),
                        trace=bool(payload.get("trace")),
                        on_stage=on_stage,
                    ),
                )
                for message in _result_messages(res):
                    await ws.send_json(message)
        except WebSocketDisconnect:
            return

    return app


def main() -> None:
    try:
        import uvicorn

        app = create_app()
    except RuntimeError as exc:
        print(exc)
        return
    except ImportError:
        print("Missing IDE dependencies. Install with: python -m pip install -e .")
        return
    threading.Timer(0.8, lambda: webbrowser.open(URL)).start()
    uvicorn.run(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
