"""Public pages: home, leaderboard, registration, status, big screen."""
from __future__ import annotations

import time
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from core import config, db, services, ui
from core.ui import E


# ----------------------------------------------------------------------
# Shared live data (respects public visibility settings)
# ----------------------------------------------------------------------
def public_data() -> dict:
    logged_in = st.session_state.get("user") is not None
    hidden = not logged_in and db.setting("leaderboard_public", "1") != "1"
    frozen = not logged_in and db.setting("show_scores_public", "1") != "1"
    teams = [] if hidden else services.team_leaderboard()
    schools = [] if hidden else services.school_leaderboard(teams)
    if frozen:
        for r in teams + schools:
            r.update(qr=0, jury=0, total=0, rank="–")
    return {"teams": teams, "schools": schools, "hidden": hidden, "frozen": frozen,
            "stats": services.event_stats(), "round": services.active_round()}


def hidden_box() -> None:
    st.markdown('<div class="sia-card" style="text-align:center;padding:40px"><div style="font-size:40px">🙈</div>'
                '<b>The leaderboard is temporarily hidden by the organiser.</b></div>', unsafe_allow_html=True)


# ----------------------------------------------------------------------
# Home
# ----------------------------------------------------------------------
def home() -> None:
    ev_date = db.setting("event_date", "")
    date_txt = ""
    days_left = ""
    if ev_date:
        try:
            d = datetime.strptime(ev_date, "%Y-%m-%d").replace(tzinfo=ZoneInfo(config.TIMEZONE))
            date_txt = d.strftime("%A, %d %B %Y")
            delta = (d - datetime.now(ZoneInfo(config.TIMEZONE))).days
            days_left = f"{max(0, delta + 1)} days to go" if delta >= -1 else "Event concluded"
        except ValueError:
            date_txt = ev_date
    st.markdown(f"""
    <div class="sia-hero">
      <div class="eb">{E(config.APP_ORG.upper())}</div>
      <h1>{E(db.setting('event_name'))}</h1>
      <p>{E(db.setting('event_tagline'))}: two competition zones, one combined ranking. Fun QR challenges meet real-world innovation, with live scores on screen.</p>
      <div style="margin-top:18px;display:flex;gap:18px;flex-wrap:wrap;color:#c9ccd6;font-size:14px">
        <span>📅 {E(date_txt or 'Date to be announced')}</span><span>📍 {E(db.setting('event_venue'))}</span>
        <span style="color:#d9cf7a;font-weight:700">⏳ {E(days_left)}</span>
      </div>
    </div>""", unsafe_allow_html=True)
    ui.ticker()

    c1, c2, _ = st.columns([1, 1, 3])
    if db.setting("registration_open", "1") == "1" and "register" in ui.PAGES:
        if c1.button("📝  Register your school", type="primary", width="stretch"):
            st.switch_page(ui.PAGES["register"])
    if "leaderboard" in ui.PAGES and c2.button("🏆  Live leaderboard", width="stretch"):
        st.switch_page(ui.PAGES["leaderboard"])

    s = services.event_stats()
    ui.kpi_row([("Schools", s["schools_approved"], "Confirmed participants", "🏫", "lav"),
                ("Teams", s["teams"], "2 per school", "👥", "olive"),
                ("QR Rounds", f"{s['rounds']:02d}", "10 points each", "📱", "sage"),
                ("Themes", f"{s['themes']:02d}", "Official hackathon themes", "💡", "teal")])

    st.markdown("### Two competition zones")
    z1, z2 = st.columns(2)
    z1.markdown('<div class="sia-card"><span class="badge" style="background:#9e9230;color:#fff">ZONE 01 · FUN & ENGAGEMENT</span>'
                '<h3 style="margin:8px 0 4px">QR Play Arena</h3><div class="muted" style="font-size:14px">Five quick activities. Scan the round QR for instructions; '
                'a volunteer verifies completion and records the score. Max <b>50 points</b> per team.</div></div>', unsafe_allow_html=True)
    z2.markdown('<div class="sia-card"><span class="badge" style="background:#2a9186;color:#fff">ZONE 02 · INNOVATION</span>'
                '<h3 style="margin:8px 0 4px">Innovation Hackathon</h3><div class="muted" style="font-size:14px">Four official themes, project display and jury evaluation '
                'using the <b>100-mark</b> rubric. Marks from several judges are averaged.</div></div>', unsafe_allow_html=True)

    st.markdown("### Official hackathon themes")
    cols = st.columns(2)
    for i, th in enumerate(services.themes_list()):
        ex = "".join(f'<span class="chip" style="margin:2px">{E(x.strip())}</span>' for x in (th["examples"] or "").split(",") if x.strip())
        cols[i % 2].markdown(f'<div class="theme-card t{th["num"]}"><div class="muted" style="font-weight:800;letter-spacing:1px">THEME {th["num"]:02d}</div>'
                             f'<h4 style="margin:4px 0 6px;font-size:17px">{E(th["title"])}</h4><div class="muted" style="font-size:14px;margin-bottom:8px">'
                             f'{E(th["description"])}</div>{ex}</div>', unsafe_allow_html=True)

    st.markdown("### QR Play Arena rounds")
    rounds = services.rounds_list()
    cols = st.columns(len(rounds) or 1)
    for col, r in zip(cols, rounds):
        live = ' <span class="badge b-active">● LIVE</span>' if r["status"] == "active" else ""
        border = "border:2px solid #3bb5a8;" if r["status"] == "active" else ""
        col.markdown(f'<div class="sia-card" style="{border}min-height:170px"><span class="round-no">{r["num"]:02d}</span>{live}'
                     f'<div style="font-weight:700;margin-top:8px">{E(r["title"])}</div><div class="muted">{E(r["description"])}</div></div>',
                     unsafe_allow_html=True)

    st.markdown("### Live standings — Top 5")
    _home_live()

    st.markdown("### How teams are scored")
    a, b = st.columns([2, 3])
    with a:
        ui.kpi_row([("QR Play Arena", 50, "max per team", "📱", "olive"), ("Jury", 100, "max per team", "📋", "teal")])
        ui.kpi_row([("Team total", 150, "QR + Jury", "👥", "lav"), ("School total", 300, "both teams", "🏫", "sage")])
    with b:
        rows = "".join(f'<div style="display:flex;justify-content:space-between;font-weight:600;font-size:14px"><span>{E(c["name"])}</span><span>{c["max_marks"]}</span></div>'
                       f'<div class="pbar" style="margin:4px 0 12px"><div style="width:{c["max_marks"] / 30 * 100:.0f}%"></div></div>' for c in services.criteria_list())
        st.markdown(f'<div class="sia-card"><h4>Jury rubric · 100 marks</h4>{rows}<div class="muted">With several judges, the final jury score is the <b>average</b> of their totals.</div></div>',
                    unsafe_allow_html=True)
    _footer()


@st.fragment(run_every=config.LIVE_REFRESH_SECONDS)
def _home_live() -> None:
    d = public_data()
    if d["hidden"]:
        hidden_box()
        return
    t1, t2 = st.tabs(["🏫 Schools", "👥 Teams"])
    t1.markdown(ui.school_table(d["schools"], limit=5), unsafe_allow_html=True)
    t2.markdown(ui.team_table(d["teams"], limit=5), unsafe_allow_html=True)
    st.caption(f"🟢 Live · updated {time.strftime('%H:%M:%S')}")


def _footer() -> None:
    st.markdown(f'<div style="margin-top:40px;padding:22px;border-radius:14px;background:#1e2230;color:#9ca1b2;font-size:13px;display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px">'
                f'<div><b style="color:#fff">{E(db.setting("event_name"))}</b><br>{E(db.setting("event_tagline"))} · {E(db.setting("event_venue"))}</div>'
                f'<div>✉️ {E(db.setting("contact_email"))} · 📞 {E(db.setting("contact_phone"))}<br>© {config.APP_ORG}</div></div>', unsafe_allow_html=True)


# ----------------------------------------------------------------------
# Leaderboard
# ----------------------------------------------------------------------
def leaderboard() -> None:
    ui.page_title("Live Leaderboard", "Scores update automatically as volunteers and judges submit them", live=True)
    c1, c2, c3 = st.columns([2, 2, 2])
    mode = c1.selectbox("Leaderboard view", ["Overall School Ranking", "Individual Team Ranking", "QR Play Arena Ranking", "Hackathon Jury Ranking"])
    themes = services.themes_list()
    theme = c2.selectbox("Theme", [None] + [t["id"] for t in themes],
                         format_func=lambda x: "All themes" if x is None else next(f"Theme {t['num']} · {t['title'].split('–')[0]}" for t in themes if t["id"] == x),
                         disabled=mode == "Overall School Ranking")
    q = c3.text_input("Search", placeholder="School or team…")
    _board_live(mode, theme, q)


@st.fragment(run_every=config.LIVE_REFRESH_SECONDS)
def _board_live(mode: str, theme, q: str) -> None:
    d = public_data()
    if d["round"]:
        st.success(f"📡 **Live now:** QR Round {d['round']['num']} · {d['round']['title']}")
    if d["hidden"]:
        hidden_box()
        return
    if d["frozen"]:
        st.warning("❄️ Scores are frozen until the results ceremony.")
    term = (q or "").lower().strip()
    if mode == "Overall School Ranking":
        rows = [s for s in d["schools"] if not term or term in (s["school"] + s["code"] + " ".join(s["teams"])).lower()]
        st.markdown(ui.school_table(rows), unsafe_allow_html=True)
    else:
        field = {"QR Play Arena Ranking": "qr", "Hackathon Jury Ranking": "jury"}.get(mode, "total")
        rows = [t for t in d["teams"] if (not theme or t["theme_id"] == theme) and (not term or term in (t["name"] + t["school"] + t["code"]).lower())]
        rows = services.sort_by(rows, field) if not d["frozen"] else rows
        st.markdown(ui.team_table(rows, field), unsafe_allow_html=True)
    st.caption(f"🟢 Updated {time.strftime('%H:%M:%S')}")


# ----------------------------------------------------------------------
# Registration
# ----------------------------------------------------------------------
def school_form(prefix: str, values: dict, submit_label: str):
    """Renders the shared school + 2 teams form. Returns dict or None."""
    themes = services.themes_list()
    theme_ids = [t["id"] for t in themes]
    tlabel = lambda i: next(f"Theme {t['num']} · {t['title']}" for t in themes if t["id"] == i)  # noqa: E731
    with st.form(f"{prefix}_form", clear_on_submit=False):
        st.markdown("#### 1 · School details")
        a, b = st.columns([2, 1])
        name = a.text_input("School name *", values.get("name", ""), max_chars=200)
        udise = b.text_input("UDISE code", values.get("udise", "") or "", max_chars=11, placeholder="11 digits")
        a, b, c = st.columns(3)
        atl = a.text_input("ATL school code", values.get("atl_code", "") or "")
        city = b.text_input("City *", values.get("city", "") or "")
        district = c.text_input("District", values.get("district", "") or "")
        address = st.text_area("Address", values.get("address", "") or "", height=70)
        a, b = st.columns(2)
        principal = a.text_input("Principal name", values.get("principal_name", "") or "")
        contact = b.text_input("ATL in-charge / contact person *", values.get("contact_name", "") or "")
        email = a.text_input("Contact email *", values.get("email", "") or "")
        phone = b.text_input("Contact phone *", values.get("phone", "") or "", placeholder="+91 98xxxxxxxx")
        data = {"name": name, "udise": udise, "atl_code": atl, "city": city, "district": district, "address": address,
                "principal_name": principal, "contact_name": contact, "email": email, "phone": phone}
        for i in (1, 2):
            st.markdown(f"#### {i + 1} · Team {i}")
            a, b = st.columns(2)
            data[f"team{i}_name"] = a.text_input(f"Team {i} name *", values.get(f"team{i}_name", "") or "", key=f"{prefix}t{i}n")
            cur = values.get(f"team{i}_theme")
            data[f"team{i}_theme"] = b.selectbox(f"Team {i} hackathon theme *", theme_ids, format_func=tlabel,
                                                 index=theme_ids.index(cur) if cur in theme_ids else None, placeholder="Select theme…", key=f"{prefix}t{i}t")
            data[f"team{i}_project"] = a.text_input("Project title", values.get(f"team{i}_project", "") or "", key=f"{prefix}t{i}p", placeholder="Can be updated later")
            data[f"team{i}_mentor"] = b.text_input("Mentor / guide teacher", values.get(f"team{i}_mentor", "") or "", key=f"{prefix}t{i}m")
            data[f"team{i}_members"] = a.text_area("Student members * (one per line, max 6)", values.get(f"team{i}_members", "") or "", key=f"{prefix}t{i}s", height=110)
            data[f"team{i}_desc"] = b.text_area("Project idea (short)", values.get(f"team{i}_desc", "") or "", key=f"{prefix}t{i}d", height=110)
        agree = True
        if prefix == "pub":
            agree = st.checkbox("I confirm the details are correct and the school agrees to the event rules and the photography consent for participants.")
        ok = st.form_submit_button(submit_label, type="primary", width="stretch")
    if ok:
        if not agree:
            st.error("Please tick the confirmation box.")
            return None
        return data
    return None


def register() -> None:
    st.markdown('<div class="sia-hero" style="padding:26px 28px"><div class="eb">PARTICIPATION</div><h1 style="font-size:32px">School & Team Registration</h1>'
                '<p>Each participating school registers <b>two teams</b>. Your School ID and Team IDs are created automatically. '
                'The organiser reviews and approves every registration.</p></div>', unsafe_allow_html=True)
    done = st.session_state.get("reg_done")
    if done:
        s = services.school_with_teams(done)
        if s:
            st.success(f"🎉 **Registration received!** Thank you, {s['contact_name']}. Your registration is **pending approval**. Save these IDs; you'll need them on event day.")
            rows = [["School", f'<span class="chip">{E(s["code"])}</span>', f'<b>{E(s["name"])}</b>']] + \
                   [[f"Team {t['slot']}", f'<span class="chip">{E(t["code"])}</span>', f'{E(t["name"])} <span class="muted">· Theme {t["theme_num"]}</span>'] for t in s["teams"]]
            st.markdown(ui.html_table(["Type", "ID", "Name"], rows), unsafe_allow_html=True)
            if st.button("Register another school"):
                st.session_state.pop("reg_done")
                st.rerun()
            return
    if db.setting("registration_open", "1") != "1":
        st.info("🔒 Registrations are closed. Please contact the organiser at " + db.setting("contact_email"))
        return
    mx = int(db.setting("max_schools", "0") or 0)
    used = int(db.q_val("SELECT COUNT(*) FROM schools WHERE status <> 'rejected'") or 0)
    if mx and used >= mx:
        st.warning(f"All {mx} slots are filled. Contact the organiser for the waiting list.")
        return
    if mx:
        st.caption(f"🎟️ {mx - used} of {mx} slots remaining")
    data = school_form("pub", st.session_state.get("reg_values", {}), "Submit registration")
    if data is not None:
        last = st.session_state.get("last_reg", 0)
        if time.time() - last < 15:
            st.error("Please wait a few seconds before submitting again.")
            return
        errors, sid = services.save_school(data, None, "pending")
        if errors:
            st.session_state["reg_values"] = data
            for msg in errors.values():
                st.error(msg)
        else:
            st.session_state["last_reg"] = time.time()
            st.session_state["reg_done"] = sid
            st.session_state.pop("reg_values", None)
            services.log(None, "school_registered", f"{db.q_val('SELECT code FROM schools WHERE id = :i', i=sid)} {data['name']}")
            st.rerun()


# ----------------------------------------------------------------------
# Status lookup
# ----------------------------------------------------------------------
def status() -> None:
    ui.page_title("Check registration status", "Enter your School ID (e.g. SCH001) and the contact email you registered with")
    with st.form("status"):
        a, b = st.columns(2)
        code = a.text_input("School ID").strip().upper()
        email = b.text_input("Contact email").strip().lower()
        go = st.form_submit_button("Check status", type="primary")
    if not go:
        return
    row = db.q_one("SELECT id FROM schools WHERE UPPER(code) = :c AND LOWER(email) = :e", c=code, e=email)
    if not row:
        st.error("No registration found for that School ID and email.")
        return
    s = services.school_with_teams(row["id"])
    st.markdown(f'<div class="sia-card"><div style="display:flex;justify-content:space-between;flex-wrap:wrap"><div><h3 style="margin:0">{E(s["name"])}</h3>'
                f'<div class="muted"><span class="chip">{E(s["code"])}</span> · {E(s["city"])}</div></div><div>{ui.badge(s["status"])}</div></div></div>', unsafe_allow_html=True)
    if s["status"] == "pending":
        st.warning(f"Your registration is being reviewed. You will be contacted at {s['email']}.")
    elif s["status"] == "rejected":
        st.error("This registration was not approved." + (f" Note: {s['admin_note']}" if s["admin_note"] else ""))
    scores = {}
    if s["status"] == "approved" and db.setting("show_scores_public", "1") == "1":
        scores = {t["id"]: t for t in services.team_leaderboard() if t["school_id"] == s["id"]}
    rows = []
    for t in s["teams"]:
        sc = scores.get(t["id"])
        rows.append([f'<span class="chip">{E(t["code"])}</span>', f'<b>{E(t["name"])}</b><div class="muted">{E(t["members"])}</div>',
                     f'T{t["theme_num"]} · {E(t["theme"])}', ui.fmt(sc["qr"]) if sc else "—", ui.fmt(sc["jury"]) if sc else "—",
                     f'<b>{ui.fmt(sc["total"])}</b>' if sc else "—"])
    st.markdown(ui.html_table(["Team ID", "Team", "Theme", "QR", "Jury", "Total"], rows, ["", "", "", "c", "c", "r"]), unsafe_allow_html=True)


# ----------------------------------------------------------------------
# Big screen (projector)
# ----------------------------------------------------------------------
def screen() -> None:
    st.markdown("""<style>
    [data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],[data-testid="stExpandSidebarButton"]{display:none}
    .stApp{background:#161a25}.block-container{max-width:100%;padding:1rem 2rem}
    .stApp .sia-card{background:#1e2230;border-color:#2c3243;color:#e8eaf0}
    .stApp .sia-table td{border-color:#2c3243;color:#e8eaf0}.stApp .sia-table tr:hover td{background:#232838}
    .stApp .sia-table th{background:#2c3243}.stApp .muted{color:#9ca1b2}.stApp .chip{background:#2c3243;color:#cfd3dd}
    .stApp .rank:not(.rank-1):not(.rank-2):not(.rank-3){background:#2c3243;color:#e8eaf0}
    .stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp p,.stApp span,.stApp div{color:inherit}
    .stApp{color:#e8eaf0}.stApp .sia-table{font-size:16px}
    </style>""", unsafe_allow_html=True)
    _screen_live()


@st.fragment(run_every=3)
def _screen_live() -> None:
    d = public_data()
    now = datetime.now(ZoneInfo(config.TIMEZONE)).strftime("%I:%M:%S %p")
    st.markdown(f'<div class="sia-bar"></div><div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap">'
                f'<div><div style="color:#3bb5a8;font-weight:700;letter-spacing:2px;font-size:13px">{E(config.APP_ORG.upper())}</div>'
                f'<div style="font-size:clamp(24px,3vw,40px);font-weight:800;color:#fff">{E(db.setting("event_name"))}</div></div>'
                f'<div style="text-align:right"><div style="font-size:32px;font-weight:800;color:#fff">{now}</div><div class="muted"><span class="live"></span>Live</div></div></div>',
                unsafe_allow_html=True)
    if d["round"]:
        st.markdown(f'<div class="ticker" style="font-size:20px;margin-top:10px">📡 LIVE NOW · QR Round {d["round"]["num"]} · {E(d["round"]["title"])}</div>', unsafe_allow_html=True)
    if d["hidden"]:
        hidden_box()
        return
    left, right = st.columns([5, 7])
    s = d["schools"]

    def pod(x, cls, label):
        if not x:
            return "<div></div>"
        return (f'<div class="pod {cls}"><div class="pr">{label}</div><div style="font-weight:700">{E(x["school"])}</div>'
                f'<div style="opacity:.75;font-size:13px">{E(x["city"] or "")}</div><div class="ps">{ui.fmt(x["total"])}</div></div>')

    with left:
        st.markdown('<div class="sia-card"><h4 style="color:#fff">🏆 Top Schools</h4>'
                    f'<div class="podium">{pod(s[1] if len(s) > 1 else None, "p2", "2nd")}{pod(s[0] if s else None, "p1", "1st")}{pod(s[2] if len(s) > 2 else None, "p3", "3rd")}</div>'
                    f'{ui.school_table(s[3:], limit=7, compact=True) if len(s) > 3 else ""}</div>', unsafe_allow_html=True)
    views = [("total", "Overall Team Ranking"), ("qr", "QR Play Arena Ranking"), ("jury", "Hackathon Jury Ranking")]
    field, label = views[int(time.time() // 12) % 3]
    rows = services.sort_by(d["teams"], field) if d["teams"] and not d["frozen"] else d["teams"]
    with right:
        st.markdown(f'<div class="sia-card"><h4 style="color:#fff">{label}</h4>{ui.team_table(rows, field, limit=10)}</div>', unsafe_allow_html=True)
    ann = services.active_announcements(1)
    if ann:
        st.markdown(f'<div class="sia-card" style="font-size:18px">📣 {E(ann[0]["message"])}</div>', unsafe_allow_html=True)
