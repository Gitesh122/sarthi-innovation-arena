"""Jury Panel (admin) and Jury Evaluation (admin matrix / judge workspace)."""
from __future__ import annotations

import csv
import io

import pandas as pd
import streamlit as st

from core import config, db, services, ui
from core.security import generate_password, hash_password, valid_email
from core.ui import E


# ======================================================================
# Jury Panel — admin
# ======================================================================
def panel() -> None:
    user = st.session_state["user"]
    ui.page_title("Jury Panel", "Create jury members, share secure access and assign schools for evaluation")
    juries = services.jury_members()
    schools = db.q_all("""SELECT s.id, s.code, s.name, s.city, (SELECT COUNT(*) FROM teams t WHERE t.school_id = s.id) AS teams
                          FROM schools s WHERE s.status = 'approved' ORDER BY s.code""")
    amap = services.assignment_map()
    active = [j for j in juries if j["active"]]
    covered = sum(1 for s in schools if amap.get(s["id"]))
    expected = sum(j["teams_assigned"] for j in active)
    done = sum(j["evaluated"] for j in juries)
    locked = db.setting("jury_locked") == "1"
    ui.kpi_row([("Jury members", len(active), f"{len(juries) - len(active)} disabled", "🧑‍⚖️", "lav"),
                ("Schools covered", f"{covered}/{len(schools)}", f"{len(schools) - covered} without jury", "🏫", "olive"),
                ("Evaluations", f"{done}/{expected}", f"{round(done / expected * 100) if expected else 0}% complete", "📋", "sage"),
                ("Scoring", "LOCKED" if locked else "OPEN", "Change in Settings", "🔒" if locked else "🔓", "teal")])

    _show_credentials()

    st.markdown('<div class="sia-card"><b>Jury workflow</b><div class="muted">1. Create jury members → 2. Share the login slips → '
                '3. Assign schools → 4. Judges evaluate on their phone or tablet</div></div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1.expander("➕ Add jury members", expanded=not juries):
        n = st.number_input("How many jury members?", 1, 15, 3, key="jn")
        with st.form("addjury", clear_on_submit=True):
            rows = []
            for i in range(int(n)):
                a, b, c = st.columns([4, 3, 4])
                rows.append({"name": a.text_input(f"Jury {i + 1} · Full name", key=f"jn{i}", placeholder="Dr. Meera Iyer"),
                             "designation": b.text_input("Designation", key=f"jd{i}", placeholder="Professor, VNIT"),
                             "email": c.text_input("Login email", key=f"je{i}", placeholder="name@example.com")})
            assign_all = st.checkbox(f"Assign all {len(schools)} approved schools to these jury members (every project gets marks from every judge, then averaged)",
                                     value=bool(schools), disabled=not schools)
            if st.form_submit_button("Create & generate logins", type="primary", width="stretch"):
                created, errors = services.create_jury(user, rows, assign_all)
                for e in errors:
                    st.error(e)
                if created:
                    st.session_state["new_creds"] = st.session_state.get("new_creds", []) + created
                    ui.flash(f"{len(created)} jury member(s) created. Share the login details.")
                    st.rerun()
                elif not errors:
                    st.warning("Fill in at least one jury member.")
    with c2.expander("🪄 Auto-assign schools", expanded=False):
        if not active or not schools:
            st.info("You need at least one active jury member and one approved school.")
        else:
            with st.form("auto"):
                opts = list(range(len(active), 0, -1))
                k = st.selectbox("Judges per school", opts, format_func=lambda k: f"{k} judge{'s' if k > 1 else ''} per school" +
                                 (" · every jury evaluates every school (recommended)" if k == len(active) else " · split evenly" if k == 1 else " · rotating panels"))
                rep = st.checkbox("Replace existing assignments", value=True)
                if st.form_submit_button("Assign now", type="primary"):
                    ui.flash(services.auto_assign(user, int(k), rep))
                    st.rerun()

    if not juries:
        st.markdown('<div class="sia-card" style="text-align:center;padding:36px"><div style="font-size:46px">🧑‍⚖️</div><h3>Set up your jury panel</h3>'
                    '<div class="muted">Create three (or more) jury members in one step. Each one gets a personal login and sees only the schools you assign to them.</div></div>',
                    unsafe_allow_html=True)
        return

    # ---------- jury cards ----------
    cols = st.columns(3)
    chip_map: dict[int, list[str]] = {}
    for r in db.q_all("SELECT ja.jury_id, s.code FROM jury_assignments ja JOIN schools s ON s.id = ja.school_id AND s.status = 'approved' ORDER BY s.code"):
        chip_map.setdefault(r["jury_id"], []).append(r["code"])
    for i, j in enumerate(juries):
        pct = min(100, round(j["evaluated"] / j["teams_assigned"] * 100)) if j["teams_assigned"] else 0
        chips = chip_map.get(j["id"], [])
        chip_html = "".join(f'<span class="chip" style="margin:2px">{E(c)}</span>' for c in chips[:8]) + (f'<span class="chip">+{len(chips) - 8}</span>' if len(chips) > 8 else "")
        if not chips:
            chip_html = '<span style="color:#b7791f;font-size:13px">⚠️ No schools assigned yet</span>'
        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"""<div class="jury-top jc{i % 4}" style="margin:-1rem -1rem 10px;{'' if j['active'] else 'filter:grayscale(.7);opacity:.7'}">
                  <div style="display:flex;gap:12px;align-items:center"><div class="jury-av">{E(ui.initials(j['name']))}</div>
                  <div style="flex:1;min-width:0"><div style="font-size:11px;font-weight:700;opacity:.8">JURY {i + 1:02d}</div>
                  <div style="font-size:18px;font-weight:800;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{E(j['name'])}</div>
                  <div style="font-size:12.5px;opacity:.8">{E(j['designation'] or 'Jury member')}</div></div>
                  <span class="badge" style="background:#fff;color:{'#11704a' if j['active'] else '#555'}">{'Active' if j['active'] else 'Disabled'}</span></div></div>
                  <div class="muted">✉️ {E(j['email'])} · 🕘 {E('last seen ' + ui.time_ago(j['last_login']) if j['last_login'] else 'never signed in')}</div>
                  <div style="display:flex;justify-content:space-between;font-weight:600;font-size:13.5px;margin-top:8px"><span>{j['schools']} schools · {j['teams_assigned']} teams</span><span>{j['evaluated']} evaluated</span></div>
                  <div class="pbar" style="margin:6px 0 8px"><div style="width:{pct}%"></div></div><div style="min-height:26px">{chip_html}</div>""",
                            unsafe_allow_html=True)
                if st.button("🔑 Generate new password", key=f"pw{j['id']}", width="stretch"):
                    pw = generate_password()
                    db.update("users", {"password_hash": hash_password(pw)}, j["id"])
                    services.log(user, "jury_password_reset", j["email"])
                    st.session_state["new_creds"] = st.session_state.get("new_creds", []) + [{**j, "password": pw}]
                    st.rerun()
                b2, b3 = st.columns(2)
                if b2.button("⏸ Disable" if j["active"] else "▶ Enable", key=f"tg{j['id']}", width="stretch"):
                    db.update("users", {"active": 0 if j["active"] else 1}, j["id"])
                    if j["active"]:
                        services.end_user_sessions(j["id"])
                    db.bump_version()
                    services.log(user, "jury_toggled", j["email"])
                    st.rerun()
                if b3.button("🗑 Remove", key=f"rm{j['id']}", width="stretch"):
                    err = services.delete_user(user, j["id"])
                    ui.flash(err or "Jury member removed.", "warning" if err else "success")
                    st.rerun()
                with st.expander("✏️ Edit details"):
                    with st.form(f"ej{j['id']}"):
                        nm = st.text_input("Full name", j["name"])
                        dg = st.text_input("Designation", j["designation"] or "")
                        em = st.text_input("Login email", j["email"])
                        if st.form_submit_button("Save"):
                            if not nm.strip() or not valid_email(em):
                                st.error("Name and a valid email are required.")
                            elif db.q_val("SELECT id FROM users WHERE LOWER(email) = :e AND id <> :i", e=em.lower(), i=j["id"]):
                                st.error("That email is already used by another account.")
                            else:
                                db.update("users", {"name": nm.strip(), "designation": dg.strip() or None, "email": em.strip().lower()}, j["id"])
                                services.log(user, "jury_updated", em)
                                ui.flash("Jury member updated.")
                                st.rerun()

    # ---------- assignment matrix ----------
    st.markdown("### 🗂️ School ↔ Jury assignment")
    if not schools:
        st.info("No approved schools yet. Approve registrations in **Schools** first.")
        return
    st.caption("Tick the boxes, then press **Save assignments**. Each judge sees both teams of every school assigned to them.")
    jcols = {f"{j['name']}" + ("" if j["active"] else " (off)"): j["id"] for j in juries}
    df = pd.DataFrame([{"School": f"{s['code']} · {s['name']}", "City": s["city"] or "", **{lbl: jid in amap.get(s["id"], set()) for lbl, jid in jcols.items()}}
                       for s in schools])
    edited = st.data_editor(df, hide_index=True, width="stretch", disabled=["School", "City"], key="assign_editor",
                            column_config={lbl: st.column_config.CheckboxColumn(lbl, width="small") for lbl in jcols})
    counts = edited[list(jcols)].sum(axis=1)
    no_jury = [edited.iloc[i]["School"] for i in range(len(edited)) if counts.iloc[i] == 0]
    a, b = st.columns([1, 3])
    if a.button("💾 Save assignments", type="primary", width="stretch"):
        desired = {(s["id"], jid): bool(edited.iloc[i][lbl]) for i, s in enumerate(schools) for lbl, jid in jcols.items()}
        added, removed = services.save_assignments(user, desired)
        ui.flash(f"Assignments saved: {added} added, {removed} removed.")
        st.rerun()
    if no_jury:
        b.warning(f"{len(no_jury)} school(s) have no jury: " + ", ".join(x.split(' · ')[0] for x in no_jury))
    else:
        b.success("✅ Every approved school has at least one judge.")


def _show_credentials() -> None:
    creds = st.session_state.get("new_creds")
    if not creds:
        return
    login_url = f"{ui.public_base_url()}/login"
    with st.container(border=True):
        st.markdown('<div class="ticker">🔑 <b>Jury login details</b>. Passwords are shown <b>only now</b>. Download the slips or copy them before closing.</div>',
                    unsafe_allow_html=True)
        st.markdown(f"Login page: **{login_url}**")
        st.markdown(ui.html_table(["Jury member", "Login email", "Password"],
                                  [[f'<b>{E(c["name"])}</b><div class="muted">{E(c.get("designation") or "")}</div>', E(c["email"]),
                                    f'<span class="chip" style="font-size:15px">{E(c["password"])}</span>'] for c in creds]), unsafe_allow_html=True)
        st.code("\n".join([f"Login: {login_url}"] + [f"{c['name']} | {c['email']} | {c['password']}" for c in creds]), language=None)
        a, b, c = st.columns(3)
        a.download_button("🖨️ Download printable login slips", _slips_html(creds, login_url), "jury-login-slips.html", "text/html", width="stretch")
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Name", "Designation", "Email", "Password", "Login URL"])
        for x in creds:
            w.writerow([x["name"], x.get("designation") or "", x["email"], x["password"], login_url])
        b.download_button("⬇️ Download as CSV", buf.getvalue(), "jury-logins.csv", "text/csv", width="stretch")
        if c.button("✅ Done, I've saved them", type="primary", width="stretch"):
            st.session_state.pop("new_creds")
            st.rerun()


def _slips_html(creds: list[dict], login_url: str) -> str:
    slips = "".join(f"""<div class="slip"><div class="bar"></div><div class="org">{E(config.APP_ORG.upper())}</div>
      <h2>{E(db.setting('event_name'))}</h2><div class="m">Jury access · Confidential</div>
      <div class="n">{E(c['name'])}</div><div class="m">{E(c.get('designation') or '')}</div>
      <table><tr><th>Login page</th><td>{E(login_url)}</td></tr><tr><th>Email</th><td>{E(c['email'])}</td></tr>
      <tr><th>Password</th><td class="pw">{E(c['password'])}</td></tr></table>
      <div class="m">Sign in → Jury Evaluation → select a team → mark each criterion → Submit. Please keep this slip confidential.</div></div>""" for c in creds)
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Jury login slips</title><style>
    body{{font-family:Inter,Arial,sans-serif;color:#1f2433;margin:30px}}.slip{{border:2px dashed #c9ccd6;border-radius:14px;padding:24px;margin-bottom:20px;page-break-inside:avoid}}
    .bar{{height:6px;border-radius:4px;background:linear-gradient(90deg,#8a86a0,#9e9230,#86a04e,#3bb5a8);margin-bottom:14px}}
    .org{{font-weight:700;letter-spacing:2px;color:#2a9186;font-size:12px}}h2{{margin:4px 0}}.m{{color:#6b7183;margin-bottom:10px}}.n{{font-size:20px;font-weight:800}}
    table{{border-collapse:collapse;margin:10px 0}}th{{text-align:left;padding:6px 16px 6px 0;color:#6b7183}}td{{padding:6px 0}}.pw{{font-family:monospace;font-size:20px;font-weight:700}}
    </style></head><body onload="window.print()">{slips}</body></html>"""


# ======================================================================
# Jury Evaluation — admin matrix OR judge workspace
# ======================================================================
def evaluation() -> None:
    user = st.session_state["user"]
    if user["role"] == "admin":
        _admin_matrix(user)
    else:
        _judge_workspace(user)


def _admin_matrix(user: dict) -> None:
    teams = sorted(services.team_leaderboard(), key=lambda t: t["code"])
    judges = db.q_all("SELECT id, name, active FROM users WHERE role = 'jury' ORDER BY id")
    evals: dict[tuple, dict] = {(e["team_id"], e["jury_id"]): e for e in db.q_all("SELECT id, team_id, jury_id, total FROM jury_evaluations")}
    amap = services.assignment_map()
    done = sum(1 for t in teams if t["judges"])
    locked = db.setting("jury_locked") == "1"
    ui.page_title("Jury Evaluation", f"{done} of {len(teams)} teams evaluated · final score = average of judges", live=True)
    a, b, c = st.columns(3)
    a.markdown(ui.kpi("Teams evaluated", f"{done}/{len(teams)}", "", "📋", "teal"), unsafe_allow_html=True)
    b.markdown(ui.kpi("Jury members", len([j for j in judges if j["active"]]), "Manage in Jury Panel", "🧑‍⚖️", "lav"), unsafe_allow_html=True)
    with c:
        st.markdown(ui.kpi("Scoring", "LOCKED" if locked else "OPEN", "", "🔒" if locked else "🔓", "olive" if locked else "sage"), unsafe_allow_html=True)
        if st.button("🔓 Unlock scoring" if locked else "🔒 Lock final scores", width="stretch"):
            db.set_setting("jury_locked", "0" if locked else "1")
            services.log(user, "jury_lock", "unlocked" if locked else "locked")
            st.rerun()
    rows = []
    for t in teams:
        cells = []
        for j in judges:
            ev = evals.get((t["id"], j["id"]))
            if ev:
                cells.append(f'<b>{ui.fmt(ev["total"])}</b>')
            elif j["id"] in amap.get(t["school_id"], set()):
                cells.append('<span title="Assigned, awaiting marks" style="color:#b7791f">⏳</span>')
            else:
                cells.append('<span class="muted" title="Not assigned">—</span>')
        rows.append([f'<span class="chip">{E(t["code"])}</span> <b>{E(t["name"])}</b><div class="muted">{E(t["school"])}</div>', f'T{t["theme_num"]}', *cells,
                     f'<span class="score">{ui.fmt(t["jury"]) if t["judges"] else "—"}</span><div class="muted">{t["judges"]}/{t["assigned_judges"]} judges</div>'])
    st.markdown(ui.html_table(["Team", "Theme", *[E(j["name"]) for j in judges], "Average"], rows, ["", "c", *["c"] * len(judges), "c"]), unsafe_allow_html=True)

    st.markdown("#### 🔍 Mark-sheet detail")
    if teams:
        tid = st.selectbox("Team", [t["id"] for t in teams], format_func=lambda i: next(f"{t['code']} · {t['name']} ({t['school']})" for t in teams if t["id"] == i))
        crit = services.criteria_list()
        evs = db.q_all("SELECT j.*, u.name FROM jury_evaluations j JOIN users u ON u.id = j.jury_id WHERE j.team_id = :t", t=tid)
        rws = []
        for ev in evs:
            m = services.evaluation_marks(ev["id"])
            rws.append([f"<b>{E(ev['name'])}</b>", *[ui.fmt(m.get(c['id'], 0)) for c in crit], f'<span class="score">{ui.fmt(ev["total"])}</span>', E(ev["remarks"] or "")])
        st.markdown(ui.html_table(["Judge", *[f"{E(c['name'])} ({c['max_marks']})" for c in crit], "Total", "Remarks"], rws, ["", *["c"] * len(crit), "c", ""]),
                    unsafe_allow_html=True)
        if evs:
            with st.expander("🗑️ Delete an evaluation"):
                eid = st.selectbox("Evaluation", [e["id"] for e in evs], format_func=lambda i: next(f"{e['name']} · {ui.fmt(e['total'])}" for e in evs if e["id"] == i))
                if st.button("Delete evaluation"):
                    services.delete_evaluation(user, eid)
                    ui.flash("Evaluation removed.")
                    st.rerun()


def _judge_workspace(user: dict) -> None:
    teams = services.jury_teams(user["id"])
    done = sum(1 for t in teams if t["eval_id"])
    locked = db.setting("jury_locked") == "1"
    ui.page_title("Jury Evaluation", f"Welcome, {user['name']} · {done} of {len(teams)} projects evaluated")
    pend = len(teams) - done
    ui.kpi_row([("Assigned schools", len({t["school"] for t in teams}), "", "🏫", "lav"), ("Projects", len(teams), "", "👥", "olive"),
                ("Evaluated", done, "", "✅", "sage"), ("Pending", pend, "Keep going!" if pend else ("All done. Thank you!" if teams else "—"), "⏳", "teal")])
    if locked:
        st.warning("🔒 Scoring is locked by the administrator. You can view but not change marks.")
    if not teams:
        st.markdown('<div class="sia-card" style="text-align:center;padding:40px"><div style="font-size:44px">📭</div><h3>No schools assigned yet</h3>'
                    '<div class="muted">The event administrator will assign schools to you shortly. This page updates when you reload.</div></div>',
                    unsafe_allow_html=True)
        return
    left, right = st.columns([5, 7], gap="large")
    with left:
        st.markdown(f"#### Assigned projects <span class='chip'>{done}/{len(teams)}</span>", unsafe_allow_html=True)
        st.markdown(f'<div class="pbar" style="margin-bottom:10px"><div style="width:{done / len(teams) * 100:.0f}%"></div></div>', unsafe_allow_html=True)
        st.markdown(ui.html_table(["Team", "Theme", "Your score"],
                                  [[f'<span class="chip">{E(t["code"])}</span> <b>{E(t["name"])}</b><div class="muted">{E(t["school"])}</div>', f'T{t["theme_num"]}',
                                    f'<span class="score">{ui.fmt(t["total"])}</span>' if t["eval_id"] else '<span class="badge b-pending">Pending</span>'] for t in teams],
                                  ["", "c", "r"]), unsafe_allow_html=True)
    with right:
        ids = [t["id"] for t in teams]
        first_pending = next((t["id"] for t in teams if not t["eval_id"]), ids[0])
        cur_id = st.session_state.get("jury_team", first_pending)
        if cur_id not in ids:
            cur_id = first_pending
        cur_id = st.selectbox("Select project to evaluate", ids, index=ids.index(cur_id),
                              format_func=lambda i: next(f"{'✅' if t['eval_id'] else '⏳'} {t['code']} · {t['name']} ({t['school']})" for t in teams if t["id"] == i))
        st.session_state["jury_team"] = cur_id
        t = next(x for x in teams if x["id"] == cur_id)
        st.markdown(f'<div class="sia-card" style="background:#f6f7fa"><div class="muted">T{t["theme_num"]} · {E(t["theme"] or "")}</div>'
                    f'<div style="font-size:20px;font-weight:800">{E(t["project_title"] or "Untitled project")}</div><div style="font-size:14px">{E(t["project_desc"] or "")}</div>'
                    f'<div class="muted" style="margin-top:4px">👥 {E(t["members"] or "")} · {E(t["school"])}</div>'
                    f'<div style="margin-top:6px">{ui.badge("approved").replace("Approved", "Submitted") if t["eval_id"] else ui.badge("pending").replace("Pending", "Not submitted")}</div></div>',
                    unsafe_allow_html=True)
        crit = services.criteria_list()
        marks0 = services.evaluation_marks(t["eval_id"]) if t["eval_id"] else {}
        marks = {}
        for c in crit:
            marks[c["id"]] = st.slider(f"{c['name']} (max {c['max_marks']})", 0.0, float(c["max_marks"]), float(marks0.get(c["id"], 0.0)), 0.5,
                                       key=f"m{t['id']}_{c['id']}", disabled=locked)
        total = sum(marks.values())
        a, b = st.columns([3, 2])
        remarks = a.text_area("Remarks / feedback", t["remarks"] or "", key=f"rm{t['id']}", height=110, disabled=locked)
        b.markdown(f'<div class="total-box" style="margin-top:28px"><div style="font-size:12px;font-weight:700">TOTAL</div><div class="tv">{ui.fmt(total)}</div><div style="font-size:12px">out of 100</div></div>',
                   unsafe_allow_html=True)
        if not locked:
            confirm = st.checkbox(f"I confirm these marks for {t['code']}", key=f"cf{t['id']}")
            if st.button(("Update" if t["eval_id"] else "Submit") + " evaluation", type="primary", width="stretch", disabled=not confirm):
                if total == 0:
                    st.error("All marks are zero. Please mark each criterion before submitting.")
                elif not services.jury_can_evaluate(user["id"], t["id"]) or db.setting("jury_locked") == "1":
                    st.error("This team is not assigned to you, or scoring is locked.")
                else:
                    tot = services.save_evaluation(t["id"], user["id"], marks, remarks)
                    services.log(user, "jury_score", f"{t['code']} = {ui.fmt(tot)}")
                    nxt = next((x["id"] for x in teams if not x["eval_id"] and x["id"] != t["id"]), None)
                    if nxt:
                        st.session_state["jury_team"] = nxt
                    ui.flash(f"Evaluation saved for {t['code']}: {ui.fmt(tot)} / 100." + (" Moving to the next project." if nxt else ""))
                    st.rerun()
