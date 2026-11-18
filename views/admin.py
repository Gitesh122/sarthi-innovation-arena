"""Admin modules: dashboard, schools, teams, leaderboard, announcements, users, reports, settings, logs."""
from __future__ import annotations

import io
import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import config, db, services, ui
from core.security import generate_password, hash_password, valid_email
from core.ui import E

PAL = config.PALETTE


def _chart_layout(fig, h=260):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Inter, sans-serif", color="#6b7183"), showlegend=False)
    return fig


# ======================================================================
# Dashboard
# ======================================================================
def dashboard() -> None:
    ui.page_title("Overview", "Event control · performance at a glance", live=True)
    _dash_live()


@st.fragment(run_every=config.LIVE_REFRESH_SECONDS + 1)
def _dash_live() -> None:
    s = services.event_stats()
    max_qr = s["teams"] * s["rounds"]
    ui.kpi_row([("Total schools", s["schools_total"], f"{s['schools_rejected']} rejected", "🏫", "lav"),
                ("Approved", s["schools_approved"], f"{s['teams']} active teams", "✅", "sage"),
                ("Pending approval", s["schools_pending"], "Review in Schools →", "⏳", "olive"),
                ("QR scores", s["qr_scores"], f"{round(s['qr_scores'] / max_qr * 100) if max_qr else 0}% of {max_qr} entries", "📱", "teal"),
                ("Jury evaluations", s["evaluations"], f"{s['jury_members']} jury members", "📋", "mix")])
    c1, c2, c3 = st.columns(3)
    with c1.container(border=True):
        st.markdown("<div class='sec-title'>REGISTRATION SUMMARY</div>", unsafe_allow_html=True)
        fig = go.Figure(go.Pie(labels=["Approved", "Pending", "Rejected"], values=[s["schools_approved"], s["schools_pending"], s["schools_rejected"]],
                               hole=.62, marker=dict(colors=[config.C_TEAL, config.C_OLIVE, config.C_LAV], line=dict(color="#fff", width=3)), sort=False, textinfo="none"))
        fig.add_annotation(text=f"<b>{s['schools_total']}</b><br>schools", showarrow=False, font=dict(size=18, color="#1f2433"))
        fig = _chart_layout(fig)
        fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.1))
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=f"p1{time.time()}")
    with c2.container(border=True):
        st.markdown("<div class='sec-title'>TEAMS BY THEME</div>", unsafe_allow_html=True)
        bt = db.q_all("""SELECT th.num, (SELECT COUNT(*) FROM teams t JOIN schools s ON s.id = t.school_id
                         WHERE t.theme_id = th.id AND s.status = 'approved') AS n FROM themes th ORDER BY th.num""")
        fig = go.Figure(go.Bar(x=[f"Theme {r['num']}" for r in bt], y=[r["n"] for r in bt], marker_color=PAL[:4], marker_cornerradius=8))
        st.plotly_chart(_chart_layout(fig), width="stretch", config={"displayModeBar": False}, key=f"p2{time.time()}")
    with c3.container(border=True):
        st.markdown("<div class='sec-title'>QR ROUND AVG. POINTS</div>", unsafe_allow_html=True)
        ra = db.q_all("SELECT r.num, COALESCE(AVG(q.points), 0) AS a FROM qr_rounds r LEFT JOIN qr_scores q ON q.round_id = r.id GROUP BY r.id, r.num ORDER BY r.num")
        fig = go.Figure(go.Bar(x=[f"R{r['num']}" for r in ra], y=[round(float(r["a"]), 1) for r in ra], marker_color=PAL, marker_cornerradius=8))
        fig = _chart_layout(fig)
        fig.update_yaxes(range=[0, 10])
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=f"p3{time.time()}")
    teams = services.team_leaderboard()
    a, b = st.columns([8, 4])
    with a.container(border=True):
        st.markdown("<div class='sec-title'>🏆 TOP PERFORMING TEAMS</div>", unsafe_allow_html=True)
        st.markdown(ui.team_table(teams, limit=6), unsafe_allow_html=True)
    with b.container(border=True):
        st.markdown("<div class='sec-title'>🏫 SCHOOL RANKING</div>", unsafe_allow_html=True)
        st.markdown(ui.school_table(services.school_leaderboard(teams), limit=6, compact=True), unsafe_allow_html=True)
    a, b = st.columns([7, 5])
    with a.container(border=True):
        st.markdown("<div class='sec-title'>LATEST REGISTRATIONS</div>", unsafe_allow_html=True)
        rs = db.q_all("SELECT code, name, city, status, created_at FROM schools ORDER BY id DESC LIMIT 6")
        st.markdown(ui.html_table(["ID", "School", "City", "Status", "Received"],
                                  [[f'<span class="chip">{E(r["code"])}</span>', f"<b>{E(r['name'])}</b>", E(r["city"] or ""), ui.badge(r["status"]),
                                    f'<span class="muted">{E(r["created_at"])}</span>'] for r in rs], ["", "", "", "", "r"]), unsafe_allow_html=True)
    with b.container(border=True):
        st.markdown("<div class='sec-title'>LIVE ACTIVITY</div>", unsafe_allow_html=True)
        for l in db.q_all("SELECT user_name, action, details, created_at FROM activity_log ORDER BY id DESC LIMIT 7"):
            st.markdown(f'<div style="padding:7px 0;border-bottom:1px solid #eee;font-size:13.5px"><b>{E(l["user_name"] or "System")}</b> · {E(l["action"].replace("_", " "))}'
                        f'<div class="muted">{E(l["details"] or "")} · {E(ui.time_ago(l["created_at"]))}</div></div>', unsafe_allow_html=True)
    st.caption(f"🟢 Live · updated {time.strftime('%H:%M:%S')}")


# ======================================================================
# Schools
# ======================================================================
def schools() -> None:
    user = st.session_state["user"]
    ui.page_title("Schools", "Registrations, approvals and school records")
    if st.session_state.get("edit_school") is not None:
        _school_editor(user, st.session_state["edit_school"])
        return
    counts = {k: int(db.q_val("SELECT COUNT(*) FROM schools" + (" WHERE status = :s" if k != "all" else ""), s=k) or 0)
              for k in ["all", "pending", "approved", "rejected"]}
    a, b, c = st.columns([5, 3, 2])
    status = a.segmented_control("Status", ["all", "pending", "approved", "rejected"], default="all",
                                 format_func=lambda k: f"{k.capitalize()} ({counts[k]})", key="sch_status") or "all"
    q = b.text_input("Search", placeholder="Name, ID, city, phone…", label_visibility="visible").strip().lower()
    c.write("")
    if c.button("➕ Add school", type="primary", width="stretch"):
        st.session_state["edit_school"] = 0
        st.rerun()
    sql = "SELECT s.*, (SELECT COUNT(*) FROM teams t WHERE t.school_id = s.id) AS team_count FROM schools s"
    rows = db.q_all(sql + (" WHERE s.status = :s" if status != "all" else "") + " ORDER BY s.id DESC", s=status)
    if q:
        rows = [r for r in rows if q in " ".join(str(r[k] or "") for k in ("name", "code", "city", "contact_name", "email", "phone")).lower()]
    st.markdown(ui.html_table(["ID", "School", "Contact", "Teams", "Status", "Registered"],
                              [[f'<span class="chip">{E(r["code"])}</span>', f'<b>{E(r["name"])}</b><div class="muted">{E(r["city"] or "")}'
                                f'{" · UDISE " + E(r["udise"]) if r["udise"] else ""}</div>', f'{E(r["contact_name"])}<div class="muted">{E(r["phone"])}</div>',
                                str(r["team_count"]), ui.badge(r["status"]), f'<span class="muted">{E(ui.time_ago(r["created_at"]))}</span>'] for r in rows],
                              ["", "", "", "c", "", ""]), unsafe_allow_html=True)
    if not rows:
        return
    st.markdown("#### Actions")
    ids = [r["id"] for r in rows]
    lbl = {r["id"]: f"{r['code']} · {r['name']} ({r['status']})" for r in rows}
    t1, t2 = st.tabs(["🔎 Open a school", "⚡ Bulk actions"])
    with t1:
        sid = st.selectbox("School", ids, format_func=lambda i: lbl[i], key="sch_pick")
        _school_detail(user, sid)
    with t2:
        sel = st.multiselect("Select schools", ids, format_func=lambda i: lbl[i])
        note = st.text_input("Reason (for rejections, shown to the school)")
        x, y, z = st.columns(3)
        if x.button("✅ Approve selected", disabled=not sel, width="stretch"):
            ui.flash(f"{services.set_school_status(user, sel, 'approved')} school(s) approved.")
            st.rerun()
        if y.button("✖ Reject selected", disabled=not sel, width="stretch"):
            ui.flash(f"{services.set_school_status(user, sel, 'rejected', note)} school(s) rejected.", "warning")
            st.rerun()
        confirm = z.checkbox("Confirm delete")
        if z.button("🗑 Delete selected", disabled=not (sel and confirm), width="stretch"):
            for i in sel:
                services.delete_school(user, i)
            ui.flash(f"{len(sel)} school(s) deleted with their teams and scores.")
            st.rerun()


def _school_detail(user: dict, sid: int) -> None:
    s = services.school_with_teams(sid)
    if not s:
        return
    scores = {t["id"]: t for t in services.team_leaderboard() if t["school_id"] == sid}
    a, b = st.columns([4, 8])
    with a.container(border=True):
        st.markdown(f"<div class='sec-title'>{E(s['name'])} {ui.badge(s['status'])}</div>", unsafe_allow_html=True)
        info = [("School ID", s["code"]), ("UDISE", s["udise"]), ("ATL code", s["atl_code"]), ("City / District", f"{s['city']} / {s['district'] or '—'}"),
                ("Address", s["address"]), ("Principal", s["principal_name"]), ("ATL in-charge", s["contact_name"]), ("Email", s["email"]),
                ("Phone", s["phone"]), ("Registered", s["created_at"]), ("Approved", s["approved_at"]), ("Admin note", s["admin_note"])]
        st.markdown("".join(f'<div style="display:flex;gap:8px;font-size:13.5px;padding:3px 0"><span class="muted" style="min-width:110px">{k}</span><span>{E(v or "—")}</span></div>'
                            for k, v in info), unsafe_allow_html=True)
        x, y = st.columns(2)
        if s["status"] != "approved" and x.button("✅ Approve", key=f"ap{sid}", type="primary", width="stretch"):
            services.set_school_status(user, [sid], "approved")
            ui.flash(f"{s['code']} approved.")
            st.rerun()
        if s["status"] != "rejected" and y.button("✖ Reject", key=f"rj{sid}", width="stretch"):
            services.set_school_status(user, [sid], "rejected", st.session_state.get(f"note{sid}", ""))
            ui.flash(f"{s['code']} rejected.", "warning")
            st.rerun()
        st.text_input("Rejection reason (optional)", key=f"note{sid}")
        x, y = st.columns(2)
        if x.button("✏️ Edit", key=f"ed{sid}", width="stretch"):
            st.session_state["edit_school"] = sid
            st.rerun()
        if s["status"] != "pending" and y.button("↺ Mark pending", key=f"pd{sid}", width="stretch"):
            services.set_school_status(user, [sid], "pending")
            st.rerun()
        with st.expander("🗑 Delete school"):
            if st.button("Permanently delete school, teams and scores", key=f"dl{sid}"):
                services.delete_school(user, sid)
                ui.flash("School deleted.")
                st.rerun()
    with b:
        rounds = services.rounds_list()
        for t in s["teams"]:
            sc = scores.get(t["id"])
            qr = {r["num"]: r["points"] for r in db.q_all("SELECT r.num, q.points FROM qr_scores q JOIN qr_rounds r ON r.id = q.round_id WHERE q.team_id = :t", t=t["id"])}
            evs = db.q_all("SELECT j.total, u.name FROM jury_evaluations j JOIN users u ON u.id = j.jury_id WHERE j.team_id = :t", t=t["id"])
            with st.container(border=True):
                st.markdown(f'<div style="display:flex;justify-content:space-between"><div class=\"sec-title\">Team {t["slot"]} · {E(t["name"])} <span class="chip">{E(t["code"])}</span></div>'
                            f'<span class="score" style="font-size:22px">{ui.fmt(sc["total"]) if sc else "—"}<span class="muted">/150</span></span></div>'
                            f'<div style="font-size:13.5px;margin:6px 0"><span class="muted">Theme:</span> T{t["theme_num"]} · {E(t["theme"] or "")} &nbsp; '
                            f'<span class="muted">Project:</span> {E(t["project_title"] or "—")}<br><span class="muted">Members:</span> {E(t["members"] or "")} &nbsp; '
                            f'<span class="muted">Mentor:</span> {E(t["mentor_name"] or "—")}</div>'
                            f'<div style="display:flex;gap:6px;margin:8px 0">' + "".join(
                                f'<div style="flex:1;text-align:center;border:1px solid #e7e8ee;border-radius:10px;padding:6px"><div class="muted">R{r["num"]}</div><b>{qr.get(r["num"], "—")}</b></div>' for r in rounds) +
                            '</div><div class="muted">Jury: ' + (", ".join(f"{E(e['name'])} <b>{ui.fmt(e['total'])}</b>" for e in evs) or "not evaluated yet") + '</div>',
                            unsafe_allow_html=True)


def _school_editor(user: dict, sid: int) -> None:
    from views.public import school_form

    s = services.school_with_teams(sid) if sid else None
    st.markdown(f"#### {'Edit ' + s['code'] + ' · ' + s['name'] if s else 'Add school (on-spot / offline entry)'}")
    if st.button("← Back to schools"):
        st.session_state.pop("edit_school")
        st.rerun()
    status = "approved"
    if not s:
        status = st.selectbox("Initial status", ["approved", "pending"], format_func=lambda x: "Approved (recommended for admin entry)" if x == "approved" else "Pending")
    data = school_form("adm", services.school_form_values(s) if s else st.session_state.get("adm_values", {}), "Save school")
    if data is not None:
        errors, new_id = services.save_school(data, sid or None, status)
        if errors:
            st.session_state["adm_values"] = data
            for m in errors.values():
                st.error(m)
        else:
            services.log(user, "school_updated" if sid else "school_added", f"{data['name']}")
            st.session_state.pop("edit_school")
            st.session_state.pop("adm_values", None)
            ui.flash("School saved.")
            st.rerun()


# ======================================================================
# Teams
# ======================================================================
def teams() -> None:
    ui.page_title("Teams", "Two teams per school")
    themes = services.themes_list()
    a, b, c = st.columns(3)
    status = a.selectbox("School status", ["approved", "pending", "rejected", "all"], format_func=str.capitalize)
    th = b.selectbox("Theme", [0] + [t["id"] for t in themes], format_func=lambda i: "All themes" if not i else next(f"Theme {t['num']}" for t in themes if t["id"] == i))
    q = c.text_input("Search", placeholder="Team, school, ID…").lower().strip()
    rows = db.q_all("""SELECT t.*, s.name AS school, s.status, s.city, th.num AS theme_num,
        COALESCE((SELECT SUM(points) FROM qr_scores q WHERE q.team_id = t.id), 0) AS qr,
        COALESCE((SELECT AVG(total) FROM jury_evaluations j WHERE j.team_id = t.id), 0) AS jury,
        (SELECT COUNT(*) FROM jury_evaluations j WHERE j.team_id = t.id) AS judges
        FROM teams t JOIN schools s ON s.id = t.school_id LEFT JOIN themes th ON th.id = t.theme_id ORDER BY t.code""")
    rows = [r for r in rows if (status == "all" or r["status"] == status) and (not th or r["theme_id"] == th)
            and (not q or q in f"{r['code']} {r['name']} {r['school']} {r['members']}".lower())]
    st.caption(f"{len(rows)} teams")
    st.markdown(ui.html_table(["Team ID", "Team", "School", "Theme", "Project", "QR", "Jury", "Total"],
                              [[f'<span class="chip">{E(r["code"])}</span>', f'<b>{E(r["name"])}</b><div class="muted">{E(r["members"] or "")}</div>',
                                f'{E(r["school"])} {ui.badge(r["status"]) if r["status"] != "approved" else ""}<div class="muted">{E(r["city"] or "")}</div>',
                                f'T{r["theme_num"]}', f'<span class="muted">{E(r["project_title"] or "—")}</span>', str(int(r["qr"])),
                                f'{ui.fmt(round(float(r["jury"]), 2))}<div class="muted">{r["judges"]} judge(s)</div>',
                                f'<span class="score">{ui.fmt(round(int(r["qr"]) + float(r["jury"]), 2))}</span>'] for r in rows],
                              ["", "", "", "c", "", "c", "c", "r"]), unsafe_allow_html=True)


# ======================================================================
# Live leaderboard (staff)
# ======================================================================
def live_board() -> None:
    from views.public import _board_live

    user = st.session_state["user"]
    ui.page_title("Live Leaderboard", "Auto-refreshes every few seconds", live=True)
    if user["role"] == "admin":
        pub = db.setting("leaderboard_public", "1") == "1"
        live = db.setting("show_scores_public", "1") == "1"
        a, b, c, _ = st.columns([2, 2, 2, 3])
        if a.button(("👁 Public: visible" if pub else "🙈 Public: hidden"), width="stretch"):
            db.set_setting("leaderboard_public", "0" if pub else "1")
            db.bump_version()
            services.log(user, "setting_changed", f"leaderboard_public = {0 if pub else 1}")
            st.rerun()
        if b.button(("🔓 Scores: live" if live else "❄️ Scores: frozen"), width="stretch"):
            db.set_setting("show_scores_public", "0" if live else "1")
            db.bump_version()
            services.log(user, "setting_changed", f"show_scores_public = {0 if live else 1}")
            st.rerun()
        if "screen" in ui.PAGES and c.button("🖥️ Big screen", width="stretch"):
            st.switch_page(ui.PAGES["screen"])
    a, b, c = st.columns(3)
    mode = a.selectbox("Leaderboard view", ["Overall School Ranking", "Individual Team Ranking", "QR Play Arena Ranking", "Hackathon Jury Ranking"])
    themes = services.themes_list()
    theme = b.selectbox("Theme", [None] + [t["id"] for t in themes], format_func=lambda x: "All themes" if x is None else next(f"Theme {t['num']}" for t in themes if t["id"] == x),
                        disabled=mode == "Overall School Ranking")
    q = c.text_input("Search", placeholder="School or team…")
    _board_live(mode, theme, q)


# ======================================================================
# Announcements
# ======================================================================
def announcements() -> None:
    user = st.session_state["user"]
    ui.page_title("Announcements", "Shown live on the website ticker and the big screen")
    a, b = st.columns([5, 7])
    with a, st.form("ann", clear_on_submit=True):
        msg = st.text_area("Message", max_chars=500, placeholder="e.g. Round 3 starts at 11:30 AM in Hall B")
        lvl = st.selectbox("Type", ["info", "success", "warning", "danger"], format_func=lambda x: {"info": "Info", "success": "Success", "warning": "Important", "danger": "Urgent"}[x])
        if st.form_submit_button("📣 Publish now", type="primary"):
            if len(msg.strip()) < 3:
                st.error("Message is too short.")
            else:
                db.insert("announcements", {"message": msg.strip(), "level": lvl, "active": 1, "created_by": user["id"], "created_at": db.now()})
                db.bump_version()
                services.log(user, "announcement", msg[:120])
                ui.flash("Announcement published live.")
                st.rerun()
    with b:
        rows = db.q_all("SELECT a.*, u.name AS author FROM announcements a LEFT JOIN users u ON u.id = a.created_by ORDER BY a.id DESC")
        if not rows:
            st.info("No announcements yet.")
        for r in rows:
            with st.container(border=True):
                x, y, z = st.columns([8, 1, 1])
                x.markdown(f'<div style="{"" if r["active"] else "text-decoration:line-through;color:#999"}">{E(r["message"])}</div>'
                           f'<div class="muted">{E(r["author"] or "System")} · {E(ui.time_ago(r["created_at"]))}</div>', unsafe_allow_html=True)
                if y.button("🙈" if r["active"] else "👁", key=f"at{r['id']}", help="Hide / show"):
                    db.update("announcements", {"active": 0 if r["active"] else 1}, r["id"])
                    db.bump_version()
                    st.rerun()
                if z.button("🗑", key=f"ad{r['id']}", help="Delete"):
                    db.execute("DELETE FROM announcements WHERE id = :i", i=r["id"])
                    db.bump_version()
                    st.rerun()


# ======================================================================
# Users
# ======================================================================
def users() -> None:
    me = st.session_state["user"]
    ui.page_title("Users & Roles", "Admins, QR volunteers and jury members")
    rows = db.q_all("""SELECT u.*, (SELECT COUNT(*) FROM jury_evaluations j WHERE j.jury_id = u.id) AS evals,
                       (SELECT COUNT(*) FROM qr_scores q WHERE q.volunteer_id = u.id) AS qr_entries FROM users u
                       ORDER BY CASE u.role WHEN 'admin' THEN 0 WHEN 'jury' THEN 1 ELSE 2 END, u.name""")
    ui.kpi_row([(f"{services.ROLES[r]}s", sum(1 for u in rows if u["role"] == r), "", ic, tone)
                for r, ic, tone in [("admin", "🛡️", "lav"), ("volunteer", "📱", "olive"), ("jury", "🧑‍⚖️", "teal")]])
    st.markdown(ui.html_table(["Name", "Email", "Role", "Activity", "Last login", "Status"],
                              [[f'<b>{E(u["name"])}</b>' + (' <span class="chip">You</span>' if u["id"] == me["id"] else "") + (f'<div class="muted">{E(u["designation"])}</div>' if u["designation"] else ""),
                                E(u["email"]), E(services.ROLES.get(u["role"], u["role"])),
                                f'<span class="muted">{u["evals"]} evaluations</span>' if u["role"] == "jury" else (f'<span class="muted">{u["qr_entries"]} QR entries</span>' if u["role"] == "volunteer" else "—"),
                                f'<span class="muted">{E(ui.time_ago(u["last_login"]))}</span>', ui.badge("active" if u["active"] else "inactive").replace("Inactive", "Disabled")] for u in rows]),
                unsafe_allow_html=True)
    st.info("💡 Create and manage jury members (with school assignments and login slips) in the **Jury Panel**.")
    a, b = st.columns(2)
    with a.expander("➕ Add user (admin / volunteer / jury)", expanded=False):
        with st.form("adduser", clear_on_submit=True):
            name = st.text_input("Full name")
            email = st.text_input("Login email")
            role = st.selectbox("Role", list(services.ROLES), format_func=lambda r: services.ROLES[r], index=1)
            desig = st.text_input("Designation / organisation (optional)")
            pw = st.text_input("Password (leave blank to auto-generate)")
            if st.form_submit_button("Create user", type="primary"):
                pw = pw or generate_password()
                if not name.strip() or not valid_email(email):
                    st.error("Name and a valid email are required.")
                elif len(pw) < 8:
                    st.error("Password must be at least 8 characters.")
                elif db.q_val("SELECT id FROM users WHERE LOWER(email) = :e", e=email.lower()):
                    st.error("Email already in use.")
                else:
                    db.insert("users", {"name": name.strip(), "email": email.strip().lower(), "role": role, "designation": desig or None,
                                        "password_hash": hash_password(pw), "active": 1, "must_change_pw": 0, "created_at": db.now()})
                    services.log(me, "user_created", f"{email} ({role})")
                    st.session_state["new_user_pw"] = (name, email, pw)
                    st.rerun()
        if st.session_state.get("new_user_pw"):
            n, e, p = st.session_state["new_user_pw"]
            st.success(f"User created. Share these details with **{n}**:")
            st.code(f"Email: {e}\nPassword: {p}", language=None)
            if st.button("Done"):
                st.session_state.pop("new_user_pw")
                st.rerun()
    with b.expander("✏️ Manage a user", expanded=False):
        uid = st.selectbox("User", [u["id"] for u in rows], format_func=lambda i: next(f"{u['name']} · {u['email']}" for u in rows if u["id"] == i))
        u = next(x for x in rows if x["id"] == uid)
        with st.form(f"mu{uid}"):
            name = st.text_input("Full name", u["name"])
            email = st.text_input("Login email", u["email"])
            role = st.selectbox("Role", list(services.ROLES), index=list(services.ROLES).index(u["role"]), format_func=lambda r: services.ROLES[r], disabled=uid == me["id"])
            desig = st.text_input("Designation", u["designation"] or "")
            newpw = st.text_input("New password (optional)")
            if st.form_submit_button("Save", type="primary"):
                if not name.strip() or not valid_email(email):
                    st.error("Name and a valid email are required.")
                elif db.q_val("SELECT id FROM users WHERE LOWER(email) = :e AND id <> :i", e=email.lower(), i=uid):
                    st.error("Email already in use.")
                elif newpw and len(newpw) < 8:
                    st.error("Password must be at least 8 characters.")
                else:
                    d = {"name": name.strip(), "email": email.strip().lower(), "designation": desig or None}
                    if uid != me["id"]:
                        d["role"] = role
                    if newpw:
                        d["password_hash"] = hash_password(newpw)
                    db.update("users", d, uid)
                    services.log(me, "user_updated", email)
                    ui.flash("User updated.")
                    st.rerun()
        if uid != me["id"]:
            x, y = st.columns(2)
            if x.button("⏸ Disable" if u["active"] else "▶ Enable", width="stretch"):
                db.update("users", {"active": 0 if u["active"] else 1}, uid)
                if u["active"]:
                    services.end_user_sessions(uid)
                services.log(me, "user_toggled", u["email"])
                st.rerun()
            if y.button("🗑 Delete user", width="stretch"):
                err = services.delete_user(me, uid)
                ui.flash(err or "User deleted.", "warning" if err else "success")
                st.rerun()


# ======================================================================
# Reports & export
# ======================================================================
def _df_export(kind: str) -> pd.DataFrame:
    crit = services.criteria_list()
    rounds = services.rounds_list()
    if kind == "schools":
        return pd.DataFrame(db.q_all("""SELECT code AS "School ID", name AS "School", udise AS "UDISE", atl_code AS "ATL code", city AS "City",
            district AS "District", address AS "Address", principal_name AS "Principal", contact_name AS "Contact", email AS "Email", phone AS "Phone",
            status AS "Status", admin_note AS "Admin note", created_at AS "Registered", approved_at AS "Approved" FROM schools ORDER BY id"""))
    if kind == "teams":
        return pd.DataFrame(db.q_all("""SELECT t.code AS "Team ID", t.name AS "Team", s.code AS "School ID", s.name AS "School", s.status AS "School status",
            th.num AS "Theme", t.project_title AS "Project", t.members AS "Members", t.mentor_name AS "Mentor", t.project_desc AS "Idea"
            FROM teams t JOIN schools s ON s.id = t.school_id LEFT JOIN themes th ON th.id = t.theme_id ORDER BY t.code"""))
    if kind == "qr":
        sc: dict = {}
        for q in db.q_all("SELECT team_id, round_id, points FROM qr_scores"):
            sc.setdefault(q["team_id"], {})[q["round_id"]] = q["points"]
        out = []
        for t in db.q_all("SELECT t.id, t.code, t.name, s.name AS school FROM teams t JOIN schools s ON s.id = t.school_id WHERE s.status = 'approved' ORDER BY t.code"):
            row = {"Team ID": t["code"], "Team": t["name"], "School": t["school"]}
            for r in rounds:
                row[f"R{r['num']} {r['title']}"] = sc.get(t["id"], {}).get(r["id"])
            row["QR total"] = sum(v or 0 for v in sc.get(t["id"], {}).values())
            out.append(row)
        return pd.DataFrame(out)
    if kind == "jury":
        out = []
        for ev in db.q_all("""SELECT j.*, t.code, t.name AS team, s.name AS school, u.name AS judge FROM jury_evaluations j JOIN teams t ON t.id = j.team_id
                              JOIN schools s ON s.id = t.school_id JOIN users u ON u.id = j.jury_id ORDER BY t.code, u.name"""):
            m = services.evaluation_marks(ev["id"])
            row = {"Team ID": ev["code"], "Team": ev["team"], "School": ev["school"], "Judge": ev["judge"]}
            row.update({f"{c['name']} ({c['max_marks']})": m.get(c["id"], 0) for c in crit})
            row.update({"Total": ev["total"], "Remarks": ev["remarks"], "Submitted": ev["updated_at"] or ev["created_at"]})
            out.append(row)
        return pd.DataFrame(out)
    if kind == "leaderboard":
        return pd.DataFrame([{"Rank": t["rank"], "Team ID": t["code"], "Team": t["name"], "School": t["school"], "Theme": f"T{t['theme_num']}",
                              "QR (50)": t["qr"], "Jury avg (100)": t["jury"], "Judges": t["judges"], "Total (150)": t["total"]} for t in services.team_leaderboard()])
    if kind == "school_ranking":
        return pd.DataFrame([{"Rank": s["rank"], "School ID": s["code"], "School": s["school"], "City": s["city"], "Teams": " & ".join(s["teams"]),
                              "QR": s["qr"], "Jury": s["jury"], "Combined (300)": s["total"]} for s in services.school_leaderboard()])
    return pd.DataFrame(db.q_all('SELECT created_at AS "Time", user_name AS "User", action AS "Action", details AS "Details" FROM activity_log ORDER BY id DESC'))


def _xlsx_all() -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for k, name in [("school_ranking", "School ranking"), ("leaderboard", "Team leaderboard"), ("schools", "Schools"), ("teams", "Teams"),
                        ("qr", "QR scores"), ("jury", "Jury mark sheets"), ("logs", "Activity log")]:
            _df_export(k).to_excel(xw, sheet_name=name, index=False)
    return buf.getvalue()


def _csv_safe(df: pd.DataFrame) -> bytes:
    df = df.copy()
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].map(lambda v: "'" + v if isinstance(v, str) and v[:1] in "=+-@" and not v.lstrip("+-").replace(".", "", 1).isdigit() else v)
    return ("﻿" + df.to_csv(index=False)).encode("utf-8")


def reports() -> None:
    user = st.session_state["user"]
    ui.page_title("Reports & Export", "Download Excel-ready data or the official results sheet")
    a, b = st.columns(2)
    with a.container(border=True):
        st.markdown("#### 📗 Complete workbook")
        st.caption("Every report in one Excel file, one sheet per report.")
        st.download_button("⬇️ Download Excel workbook (.xlsx)", _xlsx_all(), f"sarthi-arena-{time.strftime('%Y%m%d-%H%M')}.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary", width="stretch",
                           on_click=lambda: services.log(user, "export", "xlsx"))
    with b.container(border=True):
        st.markdown("#### 🏅 Official results sheet")
        st.caption("Printable HTML: school ranking, theme-wise top 3 and signature lines.")
        st.download_button("⬇️ Download results sheet", _results_html(), "official-results.html", "text/html", width="stretch")
    st.markdown("#### Individual CSV exports")
    cols = st.columns(4)
    for i, (k, title) in enumerate([("schools", "🏫 Schools register"), ("teams", "👥 Teams & members"), ("qr", "📱 QR scores"), ("jury", "📋 Jury mark sheets"),
                                    ("leaderboard", "🏆 Team leaderboard"), ("school_ranking", "🎖️ School ranking"), ("logs", "🕘 Activity log")]):
        cols[i % 4].download_button(title, _csv_safe(_df_export(k)), f"sarthi-arena-{k}.csv", "text/csv", width="stretch", key=f"dl{k}")
    st.markdown("#### Preview: school ranking")
    st.dataframe(_df_export("school_ranking"), hide_index=True, width="stretch")


def _results_html() -> str:
    teams = services.team_leaderboard()
    schools = services.school_leaderboard(teams)
    srows = "".join(f"<tr><td>{s['rank']}</td><td><b>{E(s['school'])}</b> ({E(s['code'])})</td><td>{E(' & '.join(s['teams']))}</td><td>{ui.fmt(s['qr'])}</td><td>{ui.fmt(s['jury'])}</td><td><b>{ui.fmt(s['total'])}</b></td></tr>" for s in schools)
    theme_html = ""
    for th in services.themes_list():
        tt = sorted([t for t in teams if t["theme_id"] == th["id"]], key=lambda t: -t["jury"])[:3]
        rows = "".join(f"<tr><td>{i + 1}</td><td><b>{E(t['name'])}</b> ({E(t['code'])})</td><td>{E(t['school'])}</td><td>{E(t['project_title'] or '')}</td><td><b>{ui.fmt(t['jury'])}</b></td></tr>" for i, t in enumerate(tt))
        theme_html += f"<h3>Theme {th['num']} · {E(th['title'])}: Top 3 by Jury</h3><table><tr><th>#</th><th>Team</th><th>School</th><th>Project</th><th>Jury /100</th></tr>{rows or '<tr><td colspan=5>No teams</td></tr>'}</table>"
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Official Results</title><style>
    body{{font-family:Inter,Arial,sans-serif;margin:30px;color:#1f2433}}.bar{{height:6px;background:linear-gradient(90deg,#8a86a0,#9e9230,#86a04e,#3bb5a8);border-radius:4px}}
    h1{{margin:14px 0 0;text-align:center}}.sub{{text-align:center;color:#6b7183;margin-bottom:20px}}table{{width:100%;border-collapse:collapse;margin-bottom:18px;font-size:14px}}
    th{{background:#2a3042;color:#fff;text-align:left;padding:8px}}td{{border-bottom:1px solid #e7e8ee;padding:8px}}.sig{{display:flex;justify-content:space-between;margin-top:70px}}
    .sig div{{border-top:1px solid #333;width:200px;padding-top:6px;font-size:13px}}</style></head><body onload="window.print()"><div class="bar"></div>
    <h1>{E(db.setting('event_name'))}</h1><div class="sub">{E(db.setting('event_tagline'))} · Official Results · Generated {db.now()}</div>
    <h2>Overall School Ranking</h2><table><tr><th>Rank</th><th>School</th><th>Teams</th><th>QR</th><th>Jury</th><th>Combined /300</th></tr>{srows}</table>
    {theme_html}<div class="sig"><div>Jury Chairperson</div><div>Event Coordinator</div><div>Organiser</div></div></body></html>"""


# ======================================================================
# Settings
# ======================================================================
def settings_page() -> None:
    user = st.session_state["user"]
    ui.page_title("Settings", "Event configuration, themes and rubric")
    a, b = st.columns(2)
    with a:
        with st.form("gen"):
            st.markdown("#### Event & controls")
            vals = {k: st.text_input(lbl, db.setting(k)) for k, lbl in [("event_name", "Event name"), ("event_tagline", "Tagline"), ("event_date", "Event date (YYYY-MM-DD)"),
                    ("event_venue", "Venue"), ("contact_email", "Contact email"), ("contact_phone", "Contact phone"),
                    ("public_url", "Public app URL (for QR codes, e.g. https://sarthi-arena.streamlit.app)")]}
            mx = st.number_input("Max schools (0 = unlimited)", 0, 10000, int(db.setting("max_schools", "0") or 0))
            toggles = {k: st.toggle(lbl, db.setting(k, "1" if k == "auto_assign_jury" else "0") == "1") for k, lbl in [
                ("registration_open", "Public school registration open"), ("leaderboard_public", "Public leaderboard visible"),
                ("show_scores_public", "Show live scores publicly (turn off to freeze before results)"), ("jury_locked", "Lock jury scoring"),
                ("auto_assign_jury", "Automatically assign newly approved schools to all active jury members")]}
            if st.form_submit_button("Save settings", type="primary"):
                for k, v in vals.items():
                    db.set_setting(k, v.strip())
                db.set_setting("max_schools", str(int(mx)))
                for k, v in toggles.items():
                    db.set_setting(k, "1" if v else "0")
                db.bump_version()
                services.log(user, "settings_saved", "general")
                ui.flash("Settings saved.")
                st.rerun()
        with st.form("crit"):
            st.markdown("#### Jury rubric (must total 100)")
            crit = services.criteria_list()
            newc = {}
            for c in crit:
                x, y = st.columns([4, 1])
                newc[c["id"]] = (x.text_input("Criterion", c["name"], key=f"cn{c['id']}", label_visibility="collapsed"),
                                 y.number_input("Max", 1, 100, int(c["max_marks"]), key=f"cm{c['id']}", label_visibility="collapsed"))
            if st.form_submit_button("Save rubric"):
                total = sum(v[1] for v in newc.values())
                if total != 100:
                    st.error(f"The rubric must total 100 marks (it is currently {total}).")
                else:
                    for cid, (n, m) in newc.items():
                        db.update("criteria", {"name": n.strip(), "max_marks": int(m)}, cid)
                    services.log(user, "settings_saved", "criteria")
                    ui.flash("Jury rubric updated.")
                    st.rerun()
    with b:
        with st.form("themes"):
            st.markdown("#### Hackathon themes")
            new = {}
            for t in services.themes_list():
                st.markdown(f"**Theme {t['num']}**")
                new[t["id"]] = (st.text_input("Title", t["title"], key=f"tt{t['id']}"), st.text_area("Description", t["description"] or "", key=f"td{t['id']}", height=70),
                                st.text_input("Examples (comma separated)", t["examples"] or "", key=f"tx{t['id']}"))
            if st.form_submit_button("Save themes"):
                for tid, (ti, de, ex) in new.items():
                    db.update("themes", {"title": ti.strip(), "description": de.strip(), "examples": ex.strip()}, tid)
                db.bump_version()
                services.log(user, "settings_saved", "themes")
                ui.flash("Themes updated.")
                st.rerun()
        with st.container(border=True):
            st.markdown("#### 🧰 Data & maintenance")
            st.caption(f"Database: **{db.engine().dialect.name}** · App v{config.APP_VERSION}")
            if db.is_sqlite():
                path = config.DATA_DIR / "arena.sqlite"
                if path.exists():
                    import sqlite3

                    src = sqlite3.connect(path)
                    tmp = config.DATA_DIR / "_backup.sqlite"
                    dst = sqlite3.connect(tmp)
                    src.backup(dst)
                    dst.close()
                    src.close()
                    st.download_button("💾 Download database backup", tmp.read_bytes(), f"sarthi-arena-backup-{time.strftime('%Y%m%d-%H%M')}.sqlite", width="stretch")
            else:
                st.caption("For PostgreSQL, use your provider's backup feature, or download the Excel workbook in Reports.")
            st.markdown("**Reset all scores** (after a rehearsal). Schools, teams and users are kept.")
            conf = st.text_input("Type RESET to confirm")
            if st.button("⚠️ Reset all scores", disabled=conf != "RESET"):
                services.reset_all_scores(user)
                ui.flash("All scores have been cleared.", "warning")
                st.rerun()


# ======================================================================
# Activity log
# ======================================================================
def logs() -> None:
    ui.page_title("Activity Log", "Full audit trail of logins, approvals and score changes")
    q = st.text_input("Search", placeholder="Action, user, details…").strip().lower()
    rows = db.q_all("SELECT created_at, user_name, action, details FROM activity_log ORDER BY id DESC LIMIT 2000")
    if q:
        rows = [r for r in rows if q in f"{r['user_name']} {r['action']} {r['details']}".lower()]
    st.caption(f"{len(rows)} entries")
    st.dataframe(pd.DataFrame(rows).rename(columns={"created_at": "Time", "user_name": "User", "action": "Action", "details": "Details"}) if rows else pd.DataFrame(),
                 hide_index=True, width="stretch", height=560)
