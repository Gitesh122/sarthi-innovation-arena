"""Staff login and profile / forced password change."""
from __future__ import annotations

import streamlit as st

from core import config, db, services, ui
from core.security import hash_password, strong_enough, valid_email, verify_password
from core.ui import E


def login() -> None:
    left, right = st.columns([11, 9], gap="large")
    with left:
        st.markdown(f"""
        <div class="sia-hero sia-login-hero">
          <div class="eb">{E(config.APP_ORG.upper())} · CONTROL CENTRE</div>
          <h1>{E(db.setting('event_name'))}</h1>
          <p>{E(db.setting('event_tagline'))}. The secure workspace for organisers, QR volunteers and the jury panel.</p>
          <div style="margin-top:26px;display:grid;gap:14px;color:#dfe2ea">
            <div>📡 <b>Live scoring</b><br><span style="color:#aeb3c2;font-size:13px">Every mark shows on the leaderboard within seconds.</span></div>
            <div>📋 <b>Jury evaluation</b><br><span style="color:#aeb3c2;font-size:13px">Official 100-mark rubric, scores averaged across judges.</span></div>
            <div>🛡️ <b>Secure &amp; audited</b><br><span style="color:#aeb3c2;font-size:13px">Role-based access, and a full activity log of every change.</span></div>
          </div>
        </div>""", unsafe_allow_html=True)
    with right:
        st.markdown("<div class='sia-login-gap'></div>", unsafe_allow_html=True)
        st.markdown("## Welcome back")
        st.caption("Sign in with the credentials issued by the event office.")
        st.markdown('<span class="chip">🛡️ Admin</span> <span class="chip">📱 Volunteer</span> <span class="chip">🏅 Jury</span>', unsafe_allow_html=True)
        st.write("")
        with st.form("login"):
            email = st.text_input("Email address", placeholder="name@example.com")
            pw = st.text_input("Password", type="password", placeholder="••••••••")
            go = st.form_submit_button("Sign in securely →", type="primary", width="stretch")
        if go:
            user, err = services.authenticate(email, pw)
            if err:
                st.error(err)
            else:
                st.session_state["uid"] = user["id"]
                st.session_state["session_token"] = services.create_session(user["id"])
                st.session_state["write_cookie"] = True
                ui.flash(f"Welcome, {user['name']}!")
                st.rerun()


def profile() -> None:
    user = st.session_state["user"]
    force = bool(user["must_change_pw"])
    ui.page_title("Secure Your Account" if force else "My Profile", "One-time step before you continue" if force else "Account and password")
    if force:
        st.markdown('<div class="ticker" style="padding:14px 18px">🛡️ <b>You signed in with a temporary password.</b> Set your own secure password'
                    + (" (and, if you like, your own login email)" if user["role"] == "admin" else "") + " to unlock the dashboard.</div>",
                    unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 3, 1])
    with mid, st.form("profile"):
        name = st.text_input("Full name", user["name"])
        email = st.text_input("Login email", user["email"], disabled=not (force and user["role"] == "admin"))
        a, b = st.columns(2)
        new = a.text_input("New password" + (" *" if force else " (optional)"), type="password", help="At least 8 characters, letters and numbers")
        conf = b.text_input("Confirm new password", type="password")
        cur = st.text_input("Current password *", type="password")
        ok = st.form_submit_button("Secure account & continue" if force else "Save changes", type="primary", width="stretch")
    if not ok:
        return
    row = db.q_one("SELECT password_hash FROM users WHERE id = :i", i=user["id"])
    if not verify_password(cur, row["password_hash"]):
        st.error("Current password is incorrect.")
    elif not name.strip():
        st.error("Name is required.")
    elif force and not new:
        st.error("Please set a new password to continue.")
    elif new and not strong_enough(new):
        st.error("New password must be at least 8 characters and contain letters and numbers.")
    elif new and verify_password(new, row["password_hash"]):
        st.error("New password must be different from the current one.")
    elif new != conf:
        st.error("New passwords do not match.")
    else:
        data = {"name": name.strip()}
        if new:
            data.update(password_hash=hash_password(new), must_change_pw=0)
        if force and user["role"] == "admin" and valid_email(email) and email.lower() != user["email"]:
            if db.q_val("SELECT id FROM users WHERE LOWER(email) = :e AND id <> :i", e=email.lower(), i=user["id"]):
                st.error("That email is already in use.")
                return
            data["email"] = email.lower()
        db.update("users", data, user["id"])
        services.log(user, "profile_updated", "password changed" if new else "name changed")
        if force:
            st.session_state["go_home"] = True
        ui.flash("Your account is secured. Welcome to the control room!" if force else "Profile updated.")
        st.rerun()
