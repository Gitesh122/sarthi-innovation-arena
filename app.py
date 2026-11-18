"""Sarthi Innovation Arena 2027 — Streamlit application entry point.

Run locally:   streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

from core import config, db, services, ui
from views import admin, jury, public, qr, staff

st.set_page_config(page_title="Sarthi Innovation Arena 2027", page_icon="🏆", layout="wide",
                   initial_sidebar_state="auto",
                   menu_items={"About": "Sarthi Innovation Arena 2027 · Sarthi Immortal AI"})
ui.inject_css()

# Ensure database exists (silent first-run provisioning)
try:
    db.engine()
except Exception as exc:  # pragma: no cover
    st.markdown('<div class="sia-error"><h3>We could not reach the database</h3>'
                '<div>The event server may be waking up. Please wait a few seconds and press <b>Try again</b>.</div></div>',
                unsafe_allow_html=True)
    if st.button("Try again", type="primary", icon="🔄"):
        db._engine = None
        st.rerun()
    with st.expander("Technical detail"):
        st.code(str(exc))
    st.stop()

# ---------- session / current user (survives page refresh via secure cookie) ----------
user = None
if not st.session_state.get("uid") and not st.session_state.get("logged_out"):
    _u = services.user_from_session(ui.get_cookie())
    if _u and _u["active"]:
        st.session_state["uid"] = _u["id"]
        st.session_state["session_token"] = ui.get_cookie()
if st.session_state.get("uid"):
    user = services.public_user(st.session_state["uid"])
    if not user or not user["active"]:
        st.session_state.pop("uid", None)
        user = None
st.session_state["user"] = user

# ---------- brand ----------
st.logo(str(config.BASE_DIR / "assets" / "logo.png"), size="large", icon_image=str(config.BASE_DIR / "assets" / "icon.png"))

# ---------- pages ----------
P = st.Page
home = P(public.home, title="Home", icon="🏠", url_path="home", default=user is None)
board = P(public.leaderboard, title="Live Leaderboard", icon="🏆", url_path="leaderboard")
register = P(public.register, title="School Registration", icon="📝", url_path="register")
status = P(public.status, title="Check Status", icon="🔎", url_path="status")
screen = P(public.screen, title="Big Screen", icon="🖥️", url_path="screen", visibility="hidden")
scan = P(qr.scan_page, title="QR Round", icon="📱", url_path="scan", visibility="hidden")
login = P(staff.login, title="Staff Login", icon="🔐", url_path="login")

pages: dict[str, list] = {}
if user is None:
    pages["Event"] = [home, board, register, status, login, screen, scan]
elif user["must_change_pw"]:
    pages["Account"] = [P(staff.profile, title="Secure Your Account", icon="🛡️", url_path="profile", default=True), scan, screen]
else:
    role = user["role"]
    main, comp, system = [], [], []
    if role == "admin":
        main = [P(admin.dashboard, title="Dashboard", icon="📊", url_path="dashboard", default=True),
                P(admin.schools, title="Schools", icon="🏫", url_path="schools"),
                P(admin.teams, title="Teams", icon="👥", url_path="teams")]
        comp = [P(qr.admin_qr, title="QR Play Arena", icon="📱", url_path="qr"),
                P(jury.panel, title="Jury Panel", icon="🧑‍⚖️", url_path="jury-panel"),
                P(jury.evaluation, title="Jury Evaluation", icon="📋", url_path="jury"),
                P(admin.live_board, title="Live Leaderboard", icon="🏆", url_path="live"),
                P(admin.announcements, title="Announcements", icon="📣", url_path="announcements")]
        system = [P(admin.users, title="Users & Roles", icon="🪪", url_path="users"),
                  P(admin.reports, title="Reports & Export", icon="📑", url_path="reports"),
                  P(admin.settings_page, title="Settings", icon="⚙️", url_path="settings"),
                  P(admin.logs, title="Activity Log", icon="🕘", url_path="logs")]
    elif role == "volunteer":
        comp = [P(qr.admin_qr, title="QR Play Arena", icon="📱", url_path="qr", default=True),
                P(admin.live_board, title="Live Leaderboard", icon="🏆", url_path="live")]
    else:  # jury
        comp = [P(jury.evaluation, title="Jury Evaluation", icon="📋", url_path="jury", default=True),
                P(admin.live_board, title="Live Leaderboard", icon="🏆", url_path="live")]
    if main:
        pages["Main"] = main
    pages["Competition"] = comp
    if system:
        pages["System"] = system
    pages["Account"] = [P(staff.profile, title="My Profile", icon="👤", url_path="profile"),
                        P(public.home, title="Event Website", icon="🌐", url_path="home"), board, screen, scan]
    if role in ("admin", "volunteer"):
        pages["Account"].append(P(qr.projector, title="QR Projector", icon="🖥️", url_path="projector", visibility="hidden"))

ui.PAGES.clear()
for _sec in pages.values():
    for _p in _sec:
        ui.PAGES[_p.url_path] = _p

def sign_out() -> None:
    u = st.session_state.get("user")
    if u:
        services.log(u, "logout")
    services.end_session(st.session_state.get("session_token", ""))
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.session_state["logged_out"] = True
    st.session_state["clear_cookie"] = True
    st.rerun()

nav = st.navigation(pages, expanded=True)
ui.quick_nav(nav, pages, user, sign_out)

with st.sidebar:
    if user:
        st.markdown(
            f'<div style="margin-top:14px;padding:12px;border-radius:12px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08)">'
            f'<div style="display:flex;gap:10px;align-items:center"><div style="width:36px;height:36px;border-radius:50%;'
            f'background:linear-gradient(90deg,#8a86a0,#3bb5a8);display:grid;place-items:center;color:#fff;font-weight:700">{ui.E(ui.initials(user["name"]))}</div>'
            f'<div><div style="color:#fff;font-weight:600;font-size:14px">{ui.E(user["name"])}</div>'
            f'<div style="font-size:11.5px;color:#9ca1b2">{ui.E(services.ROLES.get(user["role"], user["role"]))}</div></div></div></div>',
            unsafe_allow_html=True)
        if st.button("Sign out", icon="🚪", width="stretch"):
            sign_out()
    st.markdown(f'<div style="font-size:11px;color:#7d8296;margin-top:18px">© {ui.E(db.setting("event_name"))}<br>Sarthi Immortal AI</div>',
                unsafe_allow_html=True)

# cookie writes (hidden 0-px component)
if st.session_state.pop("write_cookie", False) and st.session_state.get("session_token"):
    with st.sidebar:
        ui.set_cookie(st.session_state["session_token"], services.SESSION_HOURS * 3600)
if st.session_state.pop("clear_cookie", False):
    with st.sidebar:
        ui.set_cookie("", 0)
if st.session_state.get("uid"):
    st.session_state.pop("logged_out", None)

# After the forced password change, land on the role's home page
if st.session_state.pop("go_home", False):
    _home = next((p for sec in pages.values() for p in sec if getattr(p, "_default", False)), None)
    if _home is not None:
        st.switch_page(_home)

ui.show_flash()
try:
    nav.run()
except Exception as exc:  # noqa: BLE001 - never show a raw traceback to event visitors
    import traceback

    st.markdown('<div class="sia-error"><h3>Something went wrong</h3>'
                '<div>Your data is safe. Please press <b>Reload page</b>. If it happens again, tell the organiser.</div></div>',
                unsafe_allow_html=True)
    if st.button("Reload page", type="primary", icon="🔄"):
        st.rerun()
    with st.expander("Technical detail"):
        st.code("".join(traceback.format_exception(exc))[-1800:])
