"""Inline stylesheet of the standalone HTML report (light/dark via prefers-color-scheme, printable)."""
from __future__ import annotations

_LIGHT = """
  --bg: #f6f7f9; --surface: #ffffff; --surface-2: #f0f2f5; --fg: #1b1f24; --muted: #5b6470; --border: #d9dee5;
  --pass: #1a7f37; --pass-bg: #dcf5e3; --fail: #c62828; --fail-bg: #fde4e4; --warn: #9a6700; --warn-bg: #fff3cd;
  --info: #0b62c4; --info-bg: #e1efff; --bonus: #7b3fbf; --bonus-bg: #efe4fb; --skip: #5b6470; --skip-bg: #eceff3;
  --del-bg: #ffd7d5; --del-fg: #8e1111; --ins-bg: #ccf2d6; --ins-fg: #0f5323; --ws: #9aa4b1; --code-bg: #f3f4f6;
"""

_DARK = """
  --bg: #0f1216; --surface: #171b21; --surface-2: #1f252d; --fg: #e6e9ee; --muted: #9aa4b1; --border: #2c333d;
  --pass: #4cc06d; --pass-bg: #123222; --fail: #ff6b6b; --fail-bg: #3a1618; --warn: #e3b341; --warn-bg: #3a2e10;
  --info: #6cb6ff; --info-bg: #10263f; --bonus: #c39bff; --bonus-bg: #2a1d40; --skip: #9aa4b1; --skip-bg: #232a33;
  --del-bg: #5c1d22; --del-fg: #ffd2d2; --ins-bg: #18432a; --ins-fg: #d4f8dc; --ws: #6b7685; --code-bg: #12161b;
"""

CSS = f"""
:root {{ color-scheme: light dark; {_LIGHT} }}
@media (prefers-color-scheme: dark) {{ :root {{ {_DARK} }} }}
* {{ box-sizing: border-box; }}
html {{ -webkit-text-size-adjust: 100%; }}
body {{ margin: 0; background: var(--bg); color: var(--fg);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, Ubuntu, sans-serif; }}
.page {{ max-width: 1080px; margin: 0 auto; padding: 24px 16px 48px; }}
h1 {{ font-size: 1.6rem; margin: 4px 0 6px; line-height: 1.25; }}
h2 {{ font-size: 1.2rem; margin: 32px 0 12px; padding-bottom: 6px; border-bottom: 1px solid var(--border); }}
h3 {{ font-size: 1rem; margin: 20px 0 8px; word-break: break-all; }}
h4 {{ font-size: .98rem; margin: 0; }}
code, pre, .mono {{ font-family: ui-monospace, "Cascadia Mono", Consolas, "DejaVu Sans Mono", monospace; font-size: .86em; }}
code {{ background: var(--code-bg); padding: 1px 5px; border-radius: 4px; word-break: break-all; }}
pre {{ background: var(--code-bg); border: 1px solid var(--border); border-radius: 6px; padding: 10px 12px;
  overflow-x: auto; margin: 8px 0; white-space: pre; }}
.muted {{ color: var(--muted); }}
.brand {{ font-weight: 700; letter-spacing: .04em; color: var(--muted); text-transform: uppercase; font-size: .78rem; }}
.meta {{ color: var(--muted); margin: 0; }}
section {{ margin-top: 8px; }}

.verdict {{ margin: 20px 0 12px; padding: 18px 20px; border-radius: 10px; border: 2px solid; background: var(--surface); }}
.verdict-ready {{ border-color: var(--pass); }}
.verdict-not_ready {{ border-color: var(--fail); }}
.verdict-title {{ font-size: 1.5rem; font-weight: 800; letter-spacing: .03em; }}
.verdict-ready .verdict-title {{ color: var(--pass); }}
.verdict-not_ready .verdict-title {{ color: var(--fail); }}
.verdict-msg {{ margin: 4px 0 14px; }}
.kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }}
.kpi {{ background: var(--surface-2); border-radius: 8px; padding: 10px 12px; }}
.kpi-value {{ display: block; font-size: 1.35rem; font-weight: 700; }}
.kpi-label {{ color: var(--muted); font-size: .82rem; }}
.reasons {{ margin: 12px 0 0; padding-left: 18px; color: var(--muted); font-size: .9rem; }}
.disclaimer {{ font-size: .88rem; color: var(--muted); border-left: 3px solid var(--border); padding: 4px 10px; margin: 8px 0; }}

.bars {{ display: grid; gap: 8px; }}
.bar-row {{ display: grid; grid-template-columns: minmax(110px, 180px) 1fr minmax(90px, auto); gap: 10px; align-items: center; }}
.bar {{ height: 12px; background: var(--surface-2); border: 1px solid var(--border); border-radius: 999px; overflow: hidden; }}
.bar-fill {{ display: block; height: 100%; border-radius: 999px; }}
.fill-good {{ background: var(--pass); }} .fill-mid {{ background: var(--warn); }} .fill-bad {{ background: var(--fail); }}
.bar-value {{ font-variant-numeric: tabular-nums; color: var(--muted); font-size: .88rem; text-align: right; }}

.table-wrap {{ overflow-x: auto; }}
table.grid {{ width: 100%; border-collapse: collapse; background: var(--surface); font-size: .9rem; }}
table.grid th, table.grid td {{ border: 1px solid var(--border); padding: 6px 8px; text-align: left; vertical-align: top; }}
table.grid th {{ background: var(--surface-2); font-weight: 600; }}
dl.kv {{ display: grid; grid-template-columns: max-content 1fr; gap: 4px 12px; margin: 8px 0; }}
dl.kv dt {{ color: var(--muted); }} dl.kv dd {{ margin: 0; min-width: 0; word-break: break-word; }}

.badge {{ display: inline-block; font-size: .72rem; font-weight: 700; letter-spacing: .04em; padding: 2px 7px;
  border-radius: 999px; white-space: nowrap; }}
.b-pass {{ color: var(--pass); background: var(--pass-bg); }} .b-fail {{ color: var(--fail); background: var(--fail-bg); }}
.b-warning, .b-partial {{ color: var(--warn); background: var(--warn-bg); }} .b-info {{ color: var(--info); background: var(--info-bg); }}
.b-bonus, .b-not_implemented {{ color: var(--bonus); background: var(--bonus-bg); }}
.b-skipped {{ color: var(--skip); background: var(--skip-bg); }} .b-missing {{ color: var(--fail); background: var(--fail-bg); }}
.sev {{ font-size: .75rem; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }}
.sev-critical {{ color: var(--fail); font-weight: 700; }}
.prov {{ font-size: .78rem; padding: 1px 6px; border-radius: 4px; background: var(--surface-2); }}
.prov-heuristic, .prov-ai_extracted {{ color: var(--warn); background: var(--warn-bg); }}

.file-group {{ margin-bottom: 18px; }}
.card {{ background: var(--surface); border: 1px solid var(--border); border-left: 4px solid var(--border);
  border-radius: 8px; padding: 12px 14px; margin: 10px 0; }}
.card.s-fail {{ border-left-color: var(--fail); }} .card.s-skipped {{ border-left-color: var(--skip); }}
.card.s-warning {{ border-left-color: var(--warn); }} .card.s-bonus {{ border-left-color: var(--bonus); }}
.card-head {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
.card-meta {{ margin-top: 4px; font-size: .84rem; color: var(--muted); display: flex; flex-wrap: wrap; gap: 6px 10px; }}
.msg {{ margin: 8px 0; }}

.diff-block {{ margin: 10px 0; }}
.diff-title {{ font-weight: 600; font-size: .9rem; margin-bottom: 4px; }}
.diff-scroll {{ overflow-x: auto; border: 1px solid var(--border); border-radius: 6px; }}
table.diff {{ border-collapse: collapse; width: 100%; font-family: ui-monospace, "Cascadia Mono", Consolas, monospace; font-size: .84rem; }}
table.diff td {{ padding: 1px 8px; vertical-align: top; white-space: pre; }}
table.diff td.sign {{ width: 1.4em; text-align: center; color: var(--muted); user-select: none; }}
table.diff td.ln {{ width: 3em; text-align: right; color: var(--muted); user-select: none; }}
table.diff td.note {{ white-space: normal; font-family: system-ui, sans-serif; font-size: .8rem; color: var(--muted); }}
tr.row-del {{ background: color-mix(in srgb, var(--del-bg) 45%, transparent); }}
tr.row-ins {{ background: color-mix(in srgb, var(--ins-bg) 45%, transparent); }}
mark.hl-del {{ background: var(--del-bg); color: var(--del-fg); border-radius: 2px; }}
mark.hl-ins {{ background: var(--ins-bg); color: var(--ins-fg); border-radius: 2px; }}
.ws {{ color: var(--ws); }}
.eol {{ color: var(--ws); }}
.eol-changed {{ color: var(--fail); font-weight: 700; }}
.legend {{ font-size: .82rem; color: var(--muted); }}

pre.code .hl-line {{ background: var(--warn-bg); display: inline-block; min-width: 100%; }}
.fix {{ margin-top: 10px; border: 1px dashed var(--border); border-radius: 6px; padding: 8px 12px; background: var(--surface-2); }}
.fix-title {{ font-weight: 600; font-size: .9rem; }}
pre.patch .p-add {{ color: var(--pass); }} pre.patch .p-del {{ color: var(--fail); }} pre.patch .p-hunk {{ color: var(--info); }}
footer {{ margin-top: 40px; color: var(--muted); font-size: .85rem; }}

@media (max-width: 640px) {{
  .bar-row {{ grid-template-columns: 1fr; gap: 2px; }}
  .bar-value {{ text-align: left; }}
}}
@media print {{
  :root {{ {_LIGHT} }}
  body {{ background: #fff; font-size: 11pt; }}
  .page {{ max-width: none; padding: 0; }}
  .card, .bar-row, tr {{ break-inside: avoid; }}
  h2, h3 {{ break-after: avoid; }}
  * {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  pre, table.diff td {{ white-space: pre-wrap; word-break: break-all; }}
}}
"""
