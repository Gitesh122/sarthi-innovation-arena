"""Shared UI: brand CSS, KPI cards, leaderboard tables, helpers."""
from __future__ import annotations

import html
from datetime import datetime

import streamlit as st

from . import config, db

E = html.escape

# Registered st.Page objects (filled by app.py) for st.switch_page
PAGES: dict = {}

CSS = """
<style>
:root{--c-lav:#8a86a0;--c-olive:#9e9230;--c-sage:#86a04e;--c-teal:#3bb5a8;--c-teal-d:#2a9186;
--grad:linear-gradient(90deg,#8a86a0 0%,#9e9230 47%,#86a04e 64%,#3bb5a8 100%);--grad-d:linear-gradient(135deg,#6c6886 0%,#7e7424 50%,#2a9186 100%);
--ink:#1f2433;--muted:#6b7183;--line:#e7e8ee;}
html,body,[class*="css"]{font-family:'Inter',system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;}
.block-container{padding-top:2.6rem;padding-bottom:3rem;max-width:1400px;animation:siaFade .3s ease}
h1,h2,h3{letter-spacing:-.3px}
#MainMenu,footer{visibility:hidden}
[data-testid="stMainMenu"],[data-testid="stAppDeployButton"],[data-testid="stDecoration"]{display:none!important}
[data-testid="stHeader"]{background:transparent}
/* Sidebar */
[data-testid="stSidebar"]{background:#1e2230}
[data-testid="stSidebar"] *{color:#c9ccd6}
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]{border-radius:10px;margin:1px 6px;padding:6px 10px}
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:hover{background:rgba(255,255,255,.06)}
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"]{background:var(--grad);box-shadow:0 6px 16px rgba(59,181,168,.25)}
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] *{color:#fff!important;font-weight:600}
[data-testid="stSidebar"] [data-testid="stNavSectionHeader"], [data-testid="stSidebar"] header{color:#7d8296!important;letter-spacing:1.3px;font-size:11px;font-weight:700;text-transform:uppercase}
[data-testid="stSidebar"] .stButton button{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12)}
[data-testid="stSidebar"] .stButton button p{color:#fff}
/* Buttons */
.stButton button[kind="primary"],.stFormSubmitButton button[kind="primary"],.stDownloadButton button[kind="primary"]{background:var(--grad);border:0;color:#fff;font-weight:600;box-shadow:0 4px 14px rgba(59,181,168,.25)}
.stButton button[kind="primary"]:hover,.stFormSubmitButton button[kind="primary"]:hover{filter:brightness(.95);color:#fff}
.stButton button,.stFormSubmitButton button,.stDownloadButton button{border-radius:10px}
/* Cards */
.sia-kpi{border-radius:14px;color:#fff;padding:16px 18px;display:flex;gap:14px;align-items:center;min-height:100px;position:relative;overflow:hidden;box-shadow:0 6px 20px rgba(31,36,51,.08);margin-bottom:6px}
.sia-kpi::after{content:"";position:absolute;right:-30px;top:-30px;width:110px;height:110px;border-radius:50%;background:rgba(255,255,255,.10)}
.sia-kpi .ic{width:50px;height:50px;border-radius:50%;background:rgba(255,255,255,.2);display:grid;place-items:center;font-size:22px;flex:0 0 auto}
.sia-kpi .lb{font-size:11.5px;font-weight:700;letter-spacing:.6px;text-transform:uppercase;opacity:.93}
.sia-kpi .vl{font-size:29px;font-weight:800;line-height:1.1}
.sia-kpi .sb{font-size:12px;opacity:.9}
.k-lav{background:linear-gradient(135deg,#8a86a0,#67628a)}.k-olive{background:linear-gradient(135deg,#a89b34,#7e7424)}
.k-sage{background:linear-gradient(135deg,#8fa956,#5f8239)}.k-teal{background:linear-gradient(135deg,#3fbcae,#23877d)}.k-mix{background:var(--grad-d)}
.sia-card{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px 20px;box-shadow:0 6px 20px rgba(31,36,51,.05);margin-bottom:12px}
.sec-title{margin:0 0 8px;font-size:14.5px;font-weight:800;letter-spacing:.4px;text-transform:uppercase;color:#2a3042}
.sia-card h4{margin:0 0 8px;font-size:14px;font-weight:800;letter-spacing:.4px;text-transform:uppercase;color:#2a3042}
.sia-hero{background:radial-gradient(1000px 360px at 90% -20%,rgba(59,181,168,.45),transparent 60%),radial-gradient(800px 360px at 0% 120%,rgba(158,146,48,.45),transparent 60%),#1e2230;color:#fff;border-radius:18px;padding:34px 32px;margin-bottom:16px;position:relative;overflow:hidden}
.sia-hero .eb{color:#3bb5a8;font-weight:700;letter-spacing:2px;font-size:12px}
.sia-hero h1{color:#fff;font-size:clamp(26px,4vw,44px);font-weight:800;margin:6px 0 8px;line-height:1.1}
.sia-hero p{color:#c9ccd6;margin:0;max-width:720px}
.sia-bar{height:5px;background:var(--grad);border-radius:4px;margin-bottom:14px}
.sia-ptitle{display:flex;align-items:flex-end;justify-content:space-between;gap:10px;margin-bottom:14px;flex-wrap:wrap}
.sia-ptitle h2{margin:0;font-size:24px;font-weight:800;text-transform:uppercase;letter-spacing:.3px}
.sia-ptitle .sub{color:var(--muted);font-size:13.5px}
/* Tables */
.sia-table{width:100%;border-collapse:separate;border-spacing:0;font-size:14px}
.sia-table th{background:#2a3042;color:#fff;font-size:11.5px;text-transform:uppercase;letter-spacing:.5px;padding:10px 12px;text-align:left;font-weight:700}
.sia-table th:first-child{border-top-left-radius:10px}.sia-table th:last-child{border-top-right-radius:10px}
.sia-table td{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:middle}
.sia-table tr:hover td{background:#f8faf9}
.sia-table .r{text-align:right}.sia-table .c{text-align:center}
.rank{width:30px;height:30px;border-radius:50%;display:inline-grid;place-items:center;font-weight:800;font-size:13px;background:#eef0f4;color:#2a3042}
.rank-1{background:linear-gradient(135deg,#f6d365,#c99a1e);color:#fff}.rank-2{background:linear-gradient(135deg,#d7dbe2,#9aa1ad);color:#fff}.rank-3{background:linear-gradient(135deg,#e7b48a,#b4733f);color:#fff}
.score{font-weight:800;color:#2a9186;font-size:18px}.muted{color:var(--muted);font-size:12.5px}
.chip{font-family:ui-monospace,Menlo,monospace;font-size:12px;background:#f0f2f6;border-radius:6px;padding:2px 7px;color:#444b5c;white-space:nowrap}
.pbar{height:6px;border-radius:6px;background:#eceef3;overflow:hidden}.pbar>div{height:100%;background:var(--grad)}
.badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:11.5px;font-weight:700}
.b-pending{background:#fff3cd;color:#8a6d00}.b-approved{background:#d1f2e4;color:#11704a}.b-rejected{background:#fde2e1;color:#a52a2a}
.b-active{background:#d1f2e4;color:#11704a}.b-inactive{background:#eceef3;color:#555}.b-closed{background:#2a3042;color:#fff}
.theme-card{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px 18px 16px 22px;position:relative;margin-bottom:12px;box-shadow:0 6px 20px rgba(31,36,51,.05)}
.theme-card::before{content:"";position:absolute;left:0;top:0;bottom:0;width:6px;border-radius:14px 0 0 14px}
.t1::before{background:#8a86a0}.t2::before{background:#9e9230}.t3::before{background:#86a04e}.t4::before{background:#3bb5a8}
.round-no{width:42px;height:42px;border-radius:12px;background:var(--grad);color:#fff;font-weight:800;display:inline-grid;place-items:center}
.ticker{background:var(--grad);color:#fff;font-weight:600;padding:9px 16px;border-radius:12px;margin-bottom:14px}
.live{display:inline-block;width:9px;height:9px;border-radius:50%;background:#22c55e;box-shadow:0 0 0 0 rgba(34,197,94,.6);animation:pulse 1.6s infinite;margin-right:6px}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(34,197,94,.6)}70%{box-shadow:0 0 0 9px rgba(34,197,94,0)}100%{box-shadow:0 0 0 0 rgba(34,197,94,0)}}
.jury-top{border-radius:14px 14px 0 0;padding:16px;color:#fff}
.jc0{background:linear-gradient(135deg,#8a86a0,#5f5a7e)}.jc1{background:linear-gradient(135deg,#a89b34,#74691f)}.jc2{background:linear-gradient(135deg,#3fbcae,#1f7a71)}.jc3{background:linear-gradient(135deg,#8fa956,#57782f)}
.jury-av{width:50px;height:50px;border-radius:14px;background:rgba(255,255,255,.22);border:2px solid rgba(255,255,255,.45);display:grid;place-items:center;font-weight:800;font-size:18px}
.total-box{background:var(--grad);color:#fff;border-radius:14px;padding:16px;text-align:center}
.total-box .tv{font-size:40px;font-weight:800;line-height:1}
.podium{display:grid;grid-template-columns:1fr 1.15fr 1fr;gap:12px;align-items:end;margin-bottom:14px}
.pod{border-radius:16px;padding:16px;text-align:center;color:#fff}.pod .pr{font-size:30px;font-weight:800}.pod .ps{font-size:24px;font-weight:800}
.p1{background:linear-gradient(160deg,#c9a227,#7e7424);min-height:200px}.p2{background:linear-gradient(160deg,#8a86a0,#55516f);min-height:170px}.p3{background:linear-gradient(160deg,#3bb5a8,#23736b);min-height:150px}
div[data-testid="stForm"]{border:1px solid var(--line);border-radius:14px;background:#fff;padding:18px}
div[data-testid="stExpander"]{border-radius:12px}
[data-testid="stMetric"]{background:#fff;border:1px solid var(--line);border-radius:12px;padding:10px 14px}

/* ===== Always-visible sidebar toggle (mobile + laptop) ===== */
[data-testid="stExpandSidebarButton"],[data-testid="stSidebarCollapsedControl"],[data-testid="collapsedControl"]{visibility:visible!important;opacity:1!important;background:var(--grad)!important;border-radius:12px!important;min-width:42px;min-height:42px;box-shadow:0 6px 16px rgba(59,181,168,.35);margin:4px 6px}
[data-testid="stExpandSidebarButton"] *,[data-testid="stSidebarCollapsedControl"] *,[data-testid="collapsedControl"] *{color:#fff!important;fill:#fff!important}
[data-testid="stSidebarCollapseButton"] button,[data-testid="stSidebarCollapseButton"] *{color:#fff!important}
/* ===== Quick navigation bar (phones, tablets, or whenever the sidebar is collapsed) ===== */
.st-key-qnav{display:none;margin:0 0 12px;padding:6px 0 4px;border-bottom:1px solid var(--line)}
.stApp:has([data-testid="stSidebar"][aria-expanded="false"]) .st-key-qnav{display:block}
.st-key-qnav [data-testid="stButtonGroup"],.st-key-qnav [role="group"]{flex-wrap:nowrap!important;overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch;padding-bottom:4px}
.st-key-qnav [data-testid="stButtonGroup"]::-webkit-scrollbar{display:none}
.st-key-qnav button{white-space:nowrap;flex:0 0 auto;border-radius:999px!important;font-weight:600;min-height:40px;padding:0 14px}
.st-key-qnav button[data-testid="stBaseButton-pillsActive"],.st-key-qnav button[aria-checked="true"],.st-key-qnav button[aria-pressed="true"]{background:var(--grad)!important;color:#fff!important;border-color:transparent!important;box-shadow:0 4px 12px rgba(59,181,168,.3)}
.st-key-qnav button[data-testid="stBaseButton-pillsActive"] *{color:#fff!important}
.sia-login-hero{min-height:540px;display:flex;flex-direction:column;justify-content:center;padding:44px}
.sia-login-gap{height:70px}
@keyframes siaFade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.sia-kpi,.theme-card{transition:transform .18s ease,box-shadow .18s ease}
.sia-kpi:hover,.theme-card:hover{transform:translateY(-3px);box-shadow:0 12px 26px rgba(31,36,51,.14)}
.sia-error{border:1px solid #f3c7c4;background:#fff6f5;border-radius:14px;padding:20px 22px;margin:12px 0}
.sia-error h3{margin:0 0 6px;color:#a52a2a}
button:focus-visible,a:focus-visible,input:focus-visible{outline:3px solid rgba(59,181,168,.55)!important;outline-offset:2px}
/* ===== Tablet & phone ===== */
@media (max-width:992px){
  .block-container{padding-left:1rem;padding-right:1rem}
  .sia-hero{padding:26px 20px}
}
@media (max-width:768px){
  .st-key-qnav{display:block}
  .block-container{padding-top:3.4rem;padding-left:.8rem;padding-right:.8rem;padding-bottom:4rem}
  [data-testid="stHeader"]{background:rgba(244,245,248,.96);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
  [data-testid="stHeader"]::after{content:"SARTHI ARENA 2027";position:absolute;left:64px;top:15px;font-weight:800;font-size:14px;letter-spacing:.8px;background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent;pointer-events:none}
  .sia-hero{padding:22px 16px;border-radius:14px}
  .sia-login-hero{min-height:0;padding:22px 16px}
  .sia-login-gap{height:6px}
  .sia-hero p{font-size:14px}
  .sia-ptitle h2{font-size:19px}
  .sia-card,.theme-card{padding:14px 14px}
  .sia-kpi{min-height:84px;padding:12px 12px;gap:10px}
  .sia-kpi .ic{width:40px;height:40px;font-size:18px}
  .sia-kpi .vl{font-size:23px}
  .sia-table{font-size:12.5px}
  .sia-table th,.sia-table td{padding:8px 7px}
  .rank{width:26px;height:26px;font-size:12px}
  .score{font-size:16px}
  .podium{gap:6px}.pod{padding:10px 6px;border-radius:12px}.pod .pr{font-size:22px}.pod .ps{font-size:18px}
  .p1{min-height:150px}.p2{min-height:125px}.p3{min-height:110px}
  .stButton button,.stFormSubmitButton button,.stDownloadButton button{min-height:46px;font-size:15px}
  input,textarea,select,[data-baseweb="select"] *{font-size:16px!important}
  div[data-testid="stForm"]{padding:12px}
  [data-testid="stHorizontalBlock"]:has(.sia-kpi){flex-wrap:wrap!important;gap:8px!important}
  [data-testid="stHorizontalBlock"]:has(.sia-kpi)>[data-testid="stColumn"]{flex:1 1 calc(50% - 8px)!important;min-width:calc(50% - 8px)!important;width:calc(50% - 8px)!important}
  [data-testid="stTabs"] [role="tablist"]{overflow-x:auto;scrollbar-width:none}
}
@media (max-width:420px){
  .sia-hero h1{font-size:24px}
  .sia-kpi .lb{font-size:10px}
}
@media print{[data-testid="stSidebar"],header,.stButton,.stDownloadButton{display:none!important}}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def quick_nav(nav, pages: dict, user: dict | None, on_signout) -> None:
    """Touch-friendly navigation strip: always reachable even when the sidebar is collapsed."""
    items, seen = [], set()
    for sec in pages.values():
        for pg in sec:
            if getattr(pg, "visibility", "visible") == "hidden" or pg.title in seen:
                continue
            seen.add(pg.title)
            items.append(pg)
    if len(items) < 2 and not user:
        return
    cur = nav.url_path
    idx = next((i for i, pg in enumerate(items) if pg.url_path == cur), None)
    opts = list(range(len(items))) + (["out"] if user else [])

    def label(o):
        return "\U0001F6AA Sign out" if o == "out" else f"{items[o].icon} {items[o].title}"

    with st.container(key="qnav"):
        sel = st.pills("Navigate", opts, format_func=label, default=idx, selection_mode="single",
                       key=f"qnav_{cur or 'root'}", label_visibility="collapsed")
    if sel == "out":
        on_signout()
    elif sel is not None and sel != idx:
        st.switch_page(items[sel])


def page_title(title: str, sub: str = "", live: bool = False) -> None:
    live_html = '<span class="muted"><span class="live"></span>Live · auto-refresh</span>' if live else ""
    st.markdown(f'<div class="sia-ptitle"><div><h2>{E(title)}</h2><div class="sub">{E(sub)}</div></div>{live_html}</div>',
                unsafe_allow_html=True)


def kpi(label: str, value, sub: str = "", icon: str = "📊", tone: str = "lav") -> str:
    return (f'<div class="sia-kpi k-{tone}"><div class="ic">{icon}</div><div><div class="lb">{E(label)}</div>'
            f'<div class="vl">{E(str(value))}</div><div class="sb">{E(sub)}</div></div></div>')


def kpi_row(items: list[tuple]) -> None:
    cols = st.columns(len(items))
    for col, it in zip(cols, items):
        col.markdown(kpi(*it), unsafe_allow_html=True)


def badge(status: str) -> str:
    return f'<span class="badge b-{E(status)}">{E(status.capitalize())}</span>'


def fmt(n) -> str:
    n = float(n or 0)
    return f"{int(n)}" if n == int(n) else f"{n:.2f}".rstrip("0").rstrip(".")


def rank_badge(r) -> str:
    cls = f"rank-{r}" if isinstance(r, int) and r <= 3 else ""
    return f'<span class="rank {cls}">{E(str(r))}</span>'


def team_table(rows: list[dict], field: str = "total", limit: int | None = None, show_theme: bool = True) -> str:
    if not rows:
        return '<div class="muted" style="padding:30px;text-align:center">🏆 No approved teams yet.</div>'
    out = []
    for t in rows[: limit or len(rows)]:
        jj = f'{t["judges"]}/{t["assigned_judges"]} judges' if t.get("assigned_judges") else (f'{t["judges"]} judges' if t["judges"] else "")
        theme = f'<td class="muted">T{t["theme_num"] or "-"} · {E((t["theme"] or "").split("–")[0])}</td>' if show_theme else ""
        out.append(f'<tr><td>{rank_badge(t["rank"])}</td>'
                   f'<td><b>{E(t["name"])}</b><div class="muted">{E(t["school"])} · <span class="chip">{E(t["code"])}</span></div></td>{theme}'
                   f'<td class="c">{fmt(t["qr"])}<span class="muted">/50</span></td>'
                   f'<td class="c">{fmt(t["jury"])}<span class="muted">/100</span><div class="muted">{jj}</div></td>'
                   f'<td class="r"><span class="score">{fmt(t["total"])}</span><span class="muted">/150</span></td></tr>')
    th = "<th>Theme</th>" if show_theme else ""
    return (f'<div style="overflow-x:auto"><table class="sia-table"><thead><tr><th style="width:56px">Rank</th><th>Team / School</th>{th}'
            f'<th class="c">QR</th><th class="c">Jury</th><th class="r">Total</th></tr></thead><tbody>{"".join(out)}</tbody></table></div>')


def school_table(rows: list[dict], limit: int | None = None, compact: bool = False) -> str:
    if not rows:
        return '<div class="muted" style="padding:30px;text-align:center">🏫 No approved schools yet.</div>'
    out = []
    for s in rows[: limit or len(rows)]:
        pct = min(100, s["total"] / 300 * 100)
        bar = f'<div class="pbar"><div style="width:{pct:.0f}%"></div></div>'
        if compact:
            out.append(f'<tr><td>{rank_badge(s["rank"])}</td><td><b>{E(s["school"])}</b><div class="muted">{E(s["code"])} · {E(s["city"] or "")}</div>{bar}</td>'
                       f'<td class="r"><span class="score">{fmt(s["total"])}</span></td></tr>')
        else:
            out.append(f'<tr><td>{rank_badge(s["rank"])}</td><td><b>{E(s["school"])}</b><div class="muted"><span class="chip">{E(s["code"])}</span> '
                       f'{E(s["city"] or "")} · {E(" & ".join(s["teams"]))}</div></td><td style="min-width:130px">{bar}</td>'
                       f'<td class="c">{fmt(s["qr"])}</td><td class="c">{fmt(s["jury"])}</td>'
                       f'<td class="r"><span class="score">{fmt(s["total"])}</span><span class="muted">/300</span></td></tr>')
    head = ('<th style="width:50px">#</th><th>School</th><th class="r">/300</th>' if compact else
            '<th style="width:56px">Rank</th><th>School</th><th>Progress</th><th class="c">QR</th><th class="c">Jury</th><th class="r">Combined</th>')
    return f'<div style="overflow-x:auto"><table class="sia-table"><thead><tr>{head}</tr></thead><tbody>{"".join(out)}</tbody></table></div>'


def html_table(headers: list[str], rows: list[list[str]], aligns: list[str] | None = None) -> str:
    aligns = aligns or [""] * len(headers)
    th = "".join(f'<th class="{a}">{h}</th>' for h, a in zip(headers, aligns))
    body = "".join("<tr>" + "".join(f'<td class="{a}">{c}</td>' for c, a in zip(r, aligns)) + "</tr>" for r in rows)
    if not rows:
        body = f'<tr><td colspan="{len(headers)}" class="c muted" style="padding:24px">Nothing to show yet.</td></tr>'
    return f'<div style="overflow-x:auto"><table class="sia-table"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def ticker() -> None:
    from .services import active_announcements

    a = active_announcements()
    if a:
        st.markdown(f'<div class="ticker">📣 {"  •  ".join(E(x["message"]) for x in a)}</div>', unsafe_allow_html=True)


def time_ago(dt: str | None) -> str:
    if not dt:
        return "never"
    try:
        d = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
        diff = (datetime.strptime(db.now(), "%Y-%m-%d %H:%M:%S") - d).total_seconds()
    except Exception:
        return dt
    if diff < 60:
        return "just now"
    if diff < 3600:
        return f"{int(diff // 60)} min ago"
    if diff < 86400:
        return f"{int(diff // 3600)} hr ago"
    return d.strftime("%d %b, %I:%M %p")


def flash(msg: str, kind: str = "success") -> None:
    st.session_state.setdefault("_flash", []).append((kind, msg))


def show_flash() -> None:
    icons = {"success": "✅", "error": "⛔", "warning": "⚠️", "info": "ℹ️"}
    for kind, msg in st.session_state.pop("_flash", []):
        st.toast(msg, icon=icons.get(kind, "ℹ️"))


def initials(name: str) -> str:
    import re

    parts = [p for p in re.sub(r"^(Dr|Prof|Mr|Mrs|Ms)\.?\s+", "", name or "", flags=re.I).split() if p]
    return "".join(p[0] for p in parts[:2]).upper() or "?"


def public_base_url() -> str:
    url = db.setting("public_url", "").strip().rstrip("/")
    if url:
        return url
    try:
        u = st.context.url  # Streamlit ≥ 1.45
        if u:
            from urllib.parse import urlsplit

            p = urlsplit(u)
            return f"{p.scheme}://{p.netloc}"
    except Exception:
        pass
    return "http://localhost:8501"


def color_palette() -> list[str]:
    return config.PALETTE


COOKIE = "sia_session"


def set_cookie(value: str, max_age: int) -> None:
    """Write the session cookie on the app's own origin (components iframe is same-origin)."""
    import json

    import streamlit.components.v1 as components

    js = (f"<script>const c={json.dumps(COOKIE)}+'='+{json.dumps(value)}+'; path=/; max-age={int(max_age)}; SameSite=Lax'"
          "+(location.protocol==='https:'?'; Secure':'');try{window.parent.document.cookie=c}catch(e){document.cookie=c}</script>")
    components.html(js, height=0)


def get_cookie() -> str:
    try:
        v = st.context.cookies.get(COOKIE, "")
        return v if isinstance(v, str) else ""
    except Exception:
        return ""
