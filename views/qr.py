"""QR Play Arena: public scan page, round control, volunteer score entry, projector."""
from __future__ import annotations

import io

import qrcode
import streamlit as st

from core import config, db, services, ui
from core.ui import E


def qr_png(data: str, box: int = 10) -> bytes:
    img = qrcode.make(data, box_size=box, border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def scan_url(token: str) -> str:
    return f"{ui.public_base_url()}/scan?t={token}"


# ----------------------------------------------------------------------
# Public scan landing page
# ----------------------------------------------------------------------
def scan_page() -> None:
    token = st.query_params.get("t", "")
    rnd = db.q_one("SELECT * FROM qr_rounds WHERE token = :t", t=token) if token else None
    _, mid, _ = st.columns([1, 3, 1])
    with mid:
        if not rnd:
            st.markdown('<div class="sia-card" style="text-align:center;padding:40px"><div style="font-size:46px">📱</div>'
                        '<h3>Invalid or expired QR code</h3><div class="muted">Please scan the QR code displayed at the active QR Play Arena station.</div></div>',
                        unsafe_allow_html=True)
            return
        _scan_live(rnd["id"])


@st.fragment(run_every=8)
def _scan_live(rid: int) -> None:
    r = db.q_one("SELECT * FROM qr_rounds WHERE id = :i", i=rid)
    status = {"active": '<span class="badge b-active">● Round is LIVE</span>',
              "closed": '<span class="badge b-closed">Round closed</span>'}.get(r["status"], '<span class="badge b-inactive">Not started yet. Wait for the volunteer.</span>')
    steps = ""
    if r["status"] == "active":
        steps = "<h4 style='margin-top:16px'>How to play</h4><ol>" + "".join(f"<li>{E(x)}</li>" for x in (r["instructions"] or "").split("\n") if x.strip()) + "</ol>"
    st.markdown(f"""<div class="sia-card" style="padding:0;overflow:hidden"><div class="sia-bar" style="border-radius:0"></div><div style="padding:22px">
      <div style="display:flex;gap:14px;align-items:center"><span class="round-no" style="width:56px;height:56px;font-size:22px">{r['num']:02d}</span>
      <div><div class="muted" style="font-weight:700;letter-spacing:1px">QR PLAY ARENA · ROUND {r['num']}</div><h2 style="margin:0">{E(r['title'])}</h2></div></div>
      <div style="margin:14px 0">{status}</div><div class="muted" style="font-size:15px">{E(r['description'])}</div>{steps}
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:14px">{ui.kpi('Max points', r['max_points'], '', '🎯', 'olive')}{ui.kpi('Your Team ID', 'SCHxxx-T1/T2', '', '🪪', 'teal')}</div>
      <div style="background:#eef6ff;border-radius:10px;padding:12px;margin-top:10px;font-size:14px">ℹ️ Scanning alone does not award points. Complete the challenge and tell the volunteer your <b>Team ID</b>; they will verify it and record your score.</div>
    </div></div>""", unsafe_allow_html=True)


# ----------------------------------------------------------------------
# Admin / volunteer QR control
# ----------------------------------------------------------------------
def admin_qr() -> None:
    user = st.session_state["user"]
    is_admin = user["role"] == "admin"
    ui.page_title("QR Play Arena", "Control rounds, display QR codes and record verified scores" if is_admin else "Record verified scores against Team ID")
    rounds = services.rounds_list()
    teams = db.q_all("SELECT t.code, t.name, s.name AS school FROM teams t JOIN schools s ON s.id = t.school_id WHERE s.status = 'approved' ORDER BY t.code")
    n_teams = len(teams)

    # Round cards
    cols = st.columns(len(rounds))
    act = services.active_round()
    default_id = st.session_state.get("qr_round") or (act["id"] if act else rounds[0]["id"])
    for col, r in zip(cols, rounds):
        pct = (r["scored"] / n_teams * 100) if n_teams else 0
        border = "border:2px solid #3bb5a8;background:#f2fbfa;" if r["id"] == default_id else ""
        col.markdown(f'<div class="sia-card" style="{border}padding:14px"><div style="display:flex;justify-content:space-between;align-items:flex-start"><span class="round-no">{r["num"]:02d}</span>{ui.badge(r["status"])}</div>'
                     f'<div style="font-weight:700;margin-top:8px;font-size:14px">{E(r["title"])}</div><div class="muted">{r["scored"]} / {n_teams} scored</div>'
                     f'<div class="pbar" style="margin-top:6px"><div style="width:{pct:.0f}%"></div></div></div>', unsafe_allow_html=True)
        if col.button("Open" if r["id"] != default_id else "Selected", key=f"sel{r['id']}", width="stretch", disabled=r["id"] == default_id):
            st.session_state["qr_round"] = r["id"]
            st.rerun()
    rnd = next(r for r in rounds if r["id"] == default_id)

    left, right = st.columns([4, 8], gap="large")
    with left, st.container(border=True):
        st.markdown(f'<div class=\"sec-title\">Round {rnd["num"]} QR &nbsp;{ui.badge(rnd["status"])}</div>', unsafe_allow_html=True)
        url = scan_url(rnd["token"])
        png = qr_png(url)
        st.image(png, width=240)
        st.caption(url)
        st.download_button("⬇️ Download QR (PNG)", png, file_name=f"qr-round-{rnd['num']}.png", mime="image/png", width="stretch")
        if "projector" in ui.PAGES and st.button("🖥️ Projector view (auto-follows active round)", width="stretch"):
            st.switch_page(ui.PAGES["projector"])
        if is_admin:
            st.divider()
            if rnd["status"] != "active" and st.button("▶️ Activate round", type="primary", width="stretch"):
                services.set_round_status(user, rnd["id"], "active")
                ui.flash(f"Round {rnd['num']} is now LIVE. Any other active round was closed.")
                st.rerun()
            if rnd["status"] == "active" and st.button("⏹️ Close round", width="stretch"):
                services.set_round_status(user, rnd["id"], "closed")
                ui.flash("Round closed.")
                st.rerun()
            if rnd["status"] != "inactive" and st.button("↺ Reset to inactive", width="stretch"):
                services.set_round_status(user, rnd["id"], "inactive")
                st.rerun()
            with st.expander("⚙️ Round settings"):
                with st.form(f"rs{rnd['id']}"):
                    title = st.text_input("Title", rnd["title"])
                    desc = st.text_input("Short description", rnd["description"] or "")
                    ins = st.text_area("Instructions (one step per line)", rnd["instructions"] or "", height=140)
                    mx = st.number_input("Max points", 1, 100, int(rnd["max_points"]))
                    if st.form_submit_button("Save", type="primary"):
                        db.update("qr_rounds", {"title": title, "description": desc, "instructions": ins, "max_points": int(mx)}, rnd["id"])
                        services.log(user, "round_updated", f"Round {rnd['num']}")
                        ui.flash("Round details saved.")
                        st.rerun()
                if st.button("🔁 Regenerate QR (old prints stop working)"):
                    services.regenerate_round_token(user, rnd["id"])
                    ui.flash("New QR code generated.", "warning")
                    st.rerun()

    with right:
        st.markdown(f"#### ✍️ Record score · Round {rnd['num']}  \n<span class='muted'>Max {rnd['max_points']} points</span>", unsafe_allow_html=True)
        if not is_admin and rnd["status"] != "active":
            st.warning(f"🔒 This round is **{rnd['status']}**. Scores can only be recorded while the round is active.")
        elif not teams:
            st.info("No approved teams yet.")
        else:
            codes = [t["code"] for t in teams]
            label = {t["code"]: f"{t['code']} · {t['name']} — {t['school']}" for t in teams}
            with st.form("score", clear_on_submit=True):
                code = st.selectbox("Team ID (type to search)", codes, index=None, format_func=lambda c: label[c], placeholder="e.g. SCH001-T1")
                pts = st.segmented_control("Points", list(range(0, int(rnd["max_points"]) + 1)) if rnd["max_points"] <= 20 else list(range(0, int(rnd["max_points"]) + 1, 5)))
                remarks = st.text_input("Remarks (optional)", placeholder="e.g. completed in 45s")
                overwrite = st.checkbox("Overwrite if this team already has a score in this round")
                go = st.form_submit_button("✅ Save score", type="primary", width="stretch")
            if go:
                if not code:
                    st.error("Select a Team ID.")
                elif pts is None:
                    st.error("Select the points.")
                else:
                    ok, msg, exists = services.record_qr_score(user, rnd["id"], code, int(pts), remarks, overwrite, is_admin)
                    if ok:
                        st.toast(msg, icon="✅")
                    elif exists:
                        st.warning(f"⚠️ {msg} Tick **Overwrite** and save again to replace it.")
                    else:
                        st.error(msg)
        _scores_live(rnd["id"], n_teams, is_admin)


@st.fragment(run_every=config.LIVE_REFRESH_SECONDS)
def _scores_live(rid: int, n_teams: int, is_admin: bool) -> None:
    rows = services.round_scores(rid)
    st.markdown(f"#### Recorded scores <span class='chip'>{len(rows)} / {n_teams}</span>", unsafe_allow_html=True)
    st.markdown(ui.html_table(["Team", "School", "Points", "Remarks", "By", "Time"],
                              [[f'<span class="chip">{E(r["code"])}</span> <b>{E(r["team"])}</b>', E(r["school"]), f'<span class="score">{r["points"]}</span>',
                                f'<span class="muted">{E(r["remarks"] or "")}</span>', E(r["volunteer"] or "—"), f'<span class="muted">{E((r["time"] or "")[11:16])}</span>']
                               for r in rows], ["", "", "c", "", "", ""]), unsafe_allow_html=True)
    if is_admin and rows:
        with st.expander("🗑️ Remove a score"):
            pick = st.selectbox("Score entry", [r["id"] for r in rows], format_func=lambda i: next(f"{r['code']} · {r['points']} pts" for r in rows if r["id"] == i), key=f"del{rid}")
            if st.button("Remove selected score", key=f"delb{rid}"):
                r = next(x for x in rows if x["id"] == pick)
                db.execute("DELETE FROM qr_scores WHERE id = :i", i=pick)
                db.bump_version()
                services.log(st.session_state["user"], "qr_score_deleted", f"{r['code']} ({r['points']})")
                st.toast("Score removed", icon="🗑️")
                st.rerun()


# ----------------------------------------------------------------------
# Projector view — follows whichever round is active
# ----------------------------------------------------------------------
def projector() -> None:
    st.markdown("""<style>[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],[data-testid="stExpandSidebarButton"]{display:none}
    .stApp{background:#161a25;color:#e8eaf0}.block-container{max-width:100%}</style>""", unsafe_allow_html=True)
    _projector_live()


@st.fragment(run_every=config.LIVE_REFRESH_SECONDS)
def _projector_live() -> None:
    r = services.active_round()
    st.markdown('<div class="sia-bar"></div>', unsafe_allow_html=True)
    if not r:
        st.markdown('<div style="text-align:center;padding:120px 0;color:#e8eaf0"><div style="font-size:70px">⏳</div>'
                    '<h1 style="color:#fff">Next round starting soon</h1><p style="color:#9ca1b2;font-size:18px">This screen switches automatically when a round is activated.</p></div>',
                    unsafe_allow_html=True)
        return
    a, b = st.columns([5, 6], gap="large")
    with a:
        st.image(qr_png(scan_url(r["token"]), 14), width=440)
        st.markdown('<div style="color:#9ca1b2;margin-top:8px">Scan with your phone camera</div>', unsafe_allow_html=True)
    with b:
        st.markdown(f'<div style="color:#3bb5a8;font-weight:700;letter-spacing:2px">QR PLAY ARENA · ROUND {r["num"]:02d}</div>'
                    f'<div style="font-size:54px;font-weight:800;color:#fff;line-height:1.05;margin:8px 0 14px">{E(r["title"])}</div>'
                    f'<div style="font-size:22px;color:#c9ccd6">{E(r["description"])}</div>'
                    f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:24px">{ui.kpi("Max points", r["max_points"], "", "🎯", "olive")}{ui.kpi("Status", "LIVE", "", "📡", "teal")}</div>'
                    f'<p style="font-size:19px;color:#e8eaf0;margin-top:18px">ℹ️ Complete the challenge, then give your <b>Team ID</b> to the volunteer.</p>',
                    unsafe_allow_html=True)
