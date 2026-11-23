"""Presentation components for the local Streamlit dashboard."""
from __future__ import annotations

import html
import json

import streamlit as st


CSS = """
<style>
:root {--panel:#151c32;--line:#303c58;--dim:#acbcd1;--cyan:#65ddd4;--violet:#b9aaff}
.block-container {max-width:1310px;padding-top:2.85rem;padding-bottom:2.25rem}
header[data-testid=stHeader]{background:#0b1020}
[data-testid=stMainBlockContainer] h1 {padding-top:0;margin:0;line-height:1.12}
[data-testid=stMainBlockContainer] h3 {padding:.3rem 0 .2rem}
h1,h2,h3 {font-family:"Inter",system-ui,sans-serif;letter-spacing:-.04em}
[data-testid=stSidebar] {background:#0f1528;border-right:1px solid #29344a}
[data-testid=stSidebar] [role=radiogroup] {gap:.18rem;align-items:stretch}
[data-testid=stSidebar] label[data-testid=stRadioOption] {width:100%;box-sizing:border-box;border-left:3px solid transparent}
[data-testid=stSidebar] label[data-testid=stRadioOption] p {font-size:.94rem;color:#ccd6e8}
[data-testid=stSidebar] [role=radiogroup] label {padding:.38rem .65rem;border-radius:.5rem}
[data-testid=stSidebar] [role=radiogroup] label:has(input:checked) {background:linear-gradient(90deg,#323656,#242945);border-left-color:#a594ff}
[data-testid=stSidebar] label:has(input:checked) p {color:#f7f5ff;font-weight:680}
[data-testid=stMetricLabel] {color:#b5c2d5}
[data-testid=stBaseButton-primary] p {color:#17152c;font-weight:650}
[data-testid=stMetricValue] {font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:1.6rem}
.identity {display:flex;align-items:center;gap:.65rem;font-size:22px;letter-spacing:-.045em;font-weight:750;margin-bottom:.65rem}
.identity i {display:grid;place-items:center;font:700 17px ui-monospace,monospace;font-style:normal;
height:38px;width:38px;border:1px solid #9280fc;transform:rotate(-6deg);border-radius:9px;
color:#fff;background:linear-gradient(145deg,#8775ed,#5647b0);box-shadow:inset 0 0 0 3px #7566d3}
.hero {display:flex;align-items:center;justify-content:space-between;gap:2rem;overflow:hidden;padding:clamp(1.1rem,2.6vw,2.1rem);
border:1px solid #414b70;border-radius:18px;margin:0 0 .3rem;
background:radial-gradient(ellipse at 87% 28%,#343660 0,transparent 53%),linear-gradient(115deg,#18253b,#1b203e 68%,#212443)}
.hero h2 {padding:.35rem 0 .15rem;font-weight:725;font-size:clamp(1.8rem,3.5vw,3.4rem);line-height:1.06;margin:0 0 .38rem;color:#f4f5ff}
.hero p,.tile p {color:#c5d1e4;line-height:1.5;margin:0;max-width:42rem}
.hero small,.tile small {font:600 .73rem "IBM Plex Mono",ui-monospace,monospace;text-transform:uppercase;
letter-spacing:.11em;color:#79e1d9}
.cards {display:flex;align-items:center;padding:18px 8px 14px;flex-shrink:0;white-space:nowrap}
.cards b {position:relative;display:grid;place-items:center;width:clamp(2.8rem,4vw,4rem);height:clamp(4.1rem,6vw,5.75rem);
font:600 clamp(1.6rem,3vw,2.65rem) Georgia,serif;border-radius:8px;
background:#e7ecfa;color:#211f42;box-shadow:0 5px 14px #07102266;border:2px solid #fff;transform:rotate(-8deg)}
.cards b::before,.cards b::after {content:attr(data-symbol);position:absolute;font:700 .68rem ui-monospace,monospace;opacity:.8}
.cards b::before {top:4px;left:5px}.cards b::after {bottom:4px;right:5px;transform:rotate(180deg)}
.cards b:nth-child(2) {background:#9fdddf;transform:rotate(-2deg);margin-left:-4px}
.cards b:nth-child(3) {background:#cec5fa;transform:rotate(4deg);margin-left:-3px}
.cards b:nth-child(4) {background:#ffbaad;transform:rotate(10deg);margin-left:-2px}
.tile {height:100%;padding:1rem 1.2rem;border-left:2px solid #9c8af5;border-radius:0 9px 9px 0;background:#151d32}
[data-testid=stColumn]:nth-child(2) .tile {border-left-color:#70cfc9}
[data-testid=stColumn]:nth-child(3) .tile {border-left-color:#efa599}
.tile h3 {padding:.1rem 0 !important;font-size:1.15rem;margin:.24rem 0 .36rem}.tile p {font-size:.91rem}
.proof {padding:1.15rem 1.5rem;background:linear-gradient(106deg,#173331,#162a33);border:1px solid #43756a;border-radius:13px;color:#e6fff3}
.proof[data-status="rejected"] {background:#342332;border-color:#865b68;color:#ffe9e4}
.proof small {font:650 .75rem "IBM Plex Mono",ui-monospace,monospace;letter-spacing:.095em;text-transform:uppercase}
.proof .formula {font:600 clamp(1.1rem,2.45vw,2.1rem) "IBM Plex Mono",ui-monospace,monospace;margin:.35rem 0;overflow-wrap:anywhere}
.proof p {font-size:.94rem;color:inherit;margin:0}
@media(min-width:761px) and (max-height:800px) {
[data-testid=stSidebar] [data-testid=stSidebarUserContent] {padding-top:1.1rem}
[data-testid=stMainBlockContainer] {padding:3.35rem 2.8rem 1.5rem}
[data-testid=stMainBlockContainer] [data-testid=stVerticalBlock] {gap:.64rem}
.hero {padding:1.4rem 1.55rem}.tile {padding:.7rem .9rem}
}
@media(max-width:760px){.hero {flex-wrap:wrap;gap:0}.block-container{padding-top:2.5rem}}
</style>
"""


def hero(label: str, title: str, description: str, numbers: tuple | list) -> None:
    cards = "".join(f'<b data-symbol="{symbol}">{int(n)}</b>' for n, symbol in zip(numbers, ("+", "−", "×", "÷")))
    st.markdown(
        '<section class="hero"><div><small>' + html.escape(label) + "</small><h2>"
        + html.escape(title) + "</h2><p>" + html.escape(description)
        + f'</p></div><div class="cards" aria-label="Puzzle cards">{cards}</div></section>',
        unsafe_allow_html=True,
    )


def tile(label: str, title: str, description: str) -> None:
    st.markdown(
        '<div class="tile"><small>' + html.escape(label) + '</small><h3>'
        + html.escape(title) + '</h3><p>' + html.escape(description) + '</p></div>',
        unsafe_allow_html=True,
    )


def certificate(proof: dict) -> None:
    valid = proof.get("valid")
    expression = str(proof.get("expression") or "No candidate")
    expression = expression.translate(str.maketrans({"*": "×", "/": "÷", "-": "−"}))
    value = proof.get("value")
    if value is not None:
        expression += f" = {value}"
    status = "verified" if valid else "rejected"
    st.markdown(
        f'<section class="proof" data-status="{status}"><small>Independent proof · {status}</small>'
        f'<div class="formula">{html.escape(expression)}</div>'
        f'<p>{html.escape(proof.get("message", ""))}</p></section>',
        unsafe_allow_html=True,
    )
    with st.expander("Inspect proof certificate"):
        st.json(proof)


def export(run: dict) -> None:
    from core.proof import audit

    payload = {"origin": st.session_state.run_origin, "run": run,
               "export_audit": audit(run.get("expression") or "", run["puzzle"])}
    st.download_button("Export Evidence", json.dumps(payload, indent=2, default=str),
                       f"game24-{run['run_id']}.json", "application/json")


def trace_tree(branches: list[dict], puzzle: list[int], selected: dict) -> str:
    """Render the focused path and its neighbouring alternatives; bound the viewport."""
    by_id = {str(row["id"]): row for row in branches}
    path: set[str] = set()
    cursor = str(selected["id"])
    while cursor in by_id and cursor not in path:
        path.add(cursor)
        cursor = str(by_id[cursor].get("parent"))
    parent_ids = {str(by_id[key].get("parent")) for key in path}
    visible = [r for r in branches if str(r["id"]) in path]
    # Keep the tree legible at projection size while every node remains selectable.
    for parent_id in sorted(parent_ids):
        siblings = [r for r in branches if str(r["id"]) not in path and str(r.get("parent")) == parent_id]
        siblings.sort(key=lambda r: r.get("decision") != "selected")
        visible.extend(siblings[:2])
    shown = {str(r["id"]) for r in visible}
    q = lambda value: json.dumps(str(value), ensure_ascii=False)
    dot = ['digraph trace {', 'graph [bgcolor="transparent",rankdir=TB,nodesep=.16,ranksep=.33];',
           'node [shape=box,style="rounded,filled",fontname="Helvetica",fontsize=14,margin=".12,.08",fontcolor="#f1f4fd"];',
           'edge [color="#69748f",arrowsize=.55];',
           f'root_card [label={q("Start   " + " · ".join(map(str,puzzle)))},fillcolor="#244b52",color="#62c1ba"];']
    for row in visible:
        node = str(row["id"])
        decision = str(row.get("decision", ""))
        color = "#9a84e4" if node in path else "#46516d"
        fill = "#40375d" if node in path else "#1d273c"
        if "prun" in decision or "reject" in decision:
            fill, color = "#432e39", "#b66f79"
        if "select" in decision or "verif" in decision:
            fill, color = "#264b44", "#69bca9"
        label = f"{row.get('move','')}\n{decision}"
        dot.append(f'{q("b"+node)} [label={q(label)},fillcolor="{fill}",color="{color}"];')
        parent = str(row.get("parent"))
        source = q("b"+parent) if parent in shown else "root_card"
        dot.append(f'{source} -> {q("b"+node)};')
    return "\n".join([*dot, "}"])
