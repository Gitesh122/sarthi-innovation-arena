"""Business logic: auth, schools, scoring, jury, QR, logging."""
from __future__ import annotations

import re
import secrets
import threading
import time

from sqlalchemy import text

from . import db
from .db import execute, insert, now, q_all, q_one, q_val, update
from .security import hash_password, valid_email, valid_phone, verify_password

ROLES = {"admin": "Administrator", "volunteer": "QR Volunteer", "jury": "Jury Member"}


# ======================================================================
# Activity log
# ======================================================================
def log(user: dict | None, action: str, details: str = "") -> None:
    insert("activity_log", {"user_id": (user or {}).get("id"), "user_name": (user or {}).get("name", "Public"),
                            "action": action, "details": (details or "")[:500], "created_at": now()})


# ======================================================================
# Authentication
# ======================================================================
_fail_lock = threading.Lock()
_failures: dict[str, list[float]] = {}


def authenticate(email: str, password: str) -> tuple[dict | None, str | None]:
    key = (email or "").strip().lower()
    with _fail_lock:
        recent = [t for t in _failures.get(key, []) if time.time() - t < 300]
        _failures[key] = recent
    if len(recent) >= 5:
        return None, "Too many failed attempts. Please wait 5 minutes and try again."
    u = q_one("SELECT * FROM users WHERE LOWER(email) = :e", e=key)
    if not u or not verify_password(password or "", u["password_hash"]):
        with _fail_lock:
            _failures.setdefault(key, []).append(time.time())
        return None, "Invalid email or password."
    if not u["active"]:
        return None, "Your account is disabled. Please contact the event administrator."
    with _fail_lock:
        _failures.pop(key, None)
    update("users", {"last_login": now()}, u["id"])
    log(u, "login", u["email"])
    return public_user(u["id"]), None


SESSION_HOURS = 14


def create_session(uid: int) -> str:
    import hashlib
    from datetime import datetime, timedelta

    token = secrets.token_urlsafe(32)
    exp = (datetime.strptime(now(), "%Y-%m-%d %H:%M:%S") + timedelta(hours=SESSION_HOURS)).strftime("%Y-%m-%d %H:%M:%S")
    execute("DELETE FROM sessions WHERE expires_at < :n", n=now())
    insert("sessions", {"token_hash": hashlib.sha256(token.encode()).hexdigest(), "user_id": uid, "expires_at": exp, "created_at": now()})
    return token


def user_from_session(token: str) -> dict | None:
    import hashlib

    if not token or len(token) > 100:
        return None
    row = q_one("SELECT user_id FROM sessions WHERE token_hash = :h AND expires_at > :n",
                h=hashlib.sha256(token.encode()).hexdigest(), n=now())
    return public_user(row["user_id"]) if row else None


def end_session(token: str) -> None:
    import hashlib

    if token:
        execute("DELETE FROM sessions WHERE token_hash = :h", h=hashlib.sha256(token.encode()).hexdigest())


def end_user_sessions(uid: int) -> None:
    execute("DELETE FROM sessions WHERE user_id = :u", u=uid)


def public_user(uid: int) -> dict | None:
    return q_one("SELECT id, name, email, role, designation, must_change_pw, active FROM users WHERE id = :i", i=uid)


# ======================================================================
# Themes / criteria / rounds
# ======================================================================
def themes_list() -> list[dict]:
    return q_all("SELECT * FROM themes ORDER BY num")


def criteria_list() -> list[dict]:
    return q_all("SELECT * FROM criteria ORDER BY sort")


def rounds_list() -> list[dict]:
    return q_all("""SELECT r.*, (SELECT COUNT(*) FROM qr_scores q WHERE q.round_id = r.id) AS scored
                    FROM qr_rounds r ORDER BY r.num""")


def active_round() -> dict | None:
    return q_one("SELECT * FROM qr_rounds WHERE status = 'active' ORDER BY activated_at DESC LIMIT 1")


# ======================================================================
# Schools
# ======================================================================
def save_school(data: dict, school_id: int | None = None, status: str = "pending") -> tuple[dict, int | None]:
    """Validate + save school and its two teams. Returns (errors, school_id)."""
    e: dict[str, str] = {}
    s = {k: (data.get(k) or "").strip() for k in
         ["name", "udise", "atl_code", "city", "district", "address", "principal_name", "contact_name", "email", "phone"]}
    s["email"] = s["email"].lower()
    if len(s["name"]) < 3:
        e["name"] = "School name is required."
    if not s["city"]:
        e["city"] = "City is required."
    if not s["contact_name"]:
        e["contact_name"] = "ATL in-charge / contact person is required."
    if not valid_email(s["email"]):
        e["email"] = "A valid email is required."
    if not valid_phone(s["phone"]):
        e["phone"] = "A valid phone number is required."
    if s["udise"] and not re.fullmatch(r"\d{11}", s["udise"]):
        e["udise"] = "UDISE code must be 11 digits."
    if not e:
        dup = q_val("""SELECT id FROM schools WHERE ((LOWER(name) = LOWER(:n) AND LOWER(city) = LOWER(:c))
                       OR (:u <> '' AND udise = :u)) AND id <> :sid""",
                    n=s["name"], c=s["city"], u=s["udise"], sid=school_id or 0)
        if dup:
            e["name"] = "This school is already registered. Contact the organiser for changes."

    theme_ids = {t["id"] for t in themes_list()}
    team_rows = {}
    for i in (1, 2):
        t = {
            "name": (data.get(f"team{i}_name") or "").strip(),
            "theme_id": int(data.get(f"team{i}_theme") or 0),
            "project_title": (data.get(f"team{i}_project") or "").strip(),
            "project_desc": (data.get(f"team{i}_desc") or "").strip(),
            "mentor_name": (data.get(f"team{i}_mentor") or "").strip(),
        }
        members = [m.strip() for m in re.split(r"[\n,]+", data.get(f"team{i}_members") or "") if m.strip()]
        if len(t["name"]) < 2:
            e[f"team{i}_name"] = f"Team {i} name is required."
        if t["theme_id"] not in theme_ids:
            e[f"team{i}_theme"] = f"Select a hackathon theme for Team {i}."
        if not members:
            e[f"team{i}_members"] = f"Add at least one student for Team {i}."
        elif len(members) > 6:
            e[f"team{i}_members"] = f"Maximum 6 students in Team {i}."
        t["members"] = ", ".join(members)
        team_rows[i] = t
    if "team1_name" not in e and "team2_name" not in e and team_rows[1]["name"].lower() == team_rows[2]["name"].lower():
        e["team2_name"] = "The two teams must have different names."
    if e:
        return e, None

    with db.engine().begin() as c:
        if school_id:
            db.update("schools", {**s, "updated_at": now()}, school_id, c)
        else:
            school_id = db.insert("schools", {**s, "status": status, "created_at": now(),
                                              "approved_at": now() if status == "approved" else None}, c)
            c.execute(text("UPDATE schools SET code = :code WHERE id = :i"), {"code": f"SCH{school_id:03d}", "i": school_id})
        code = c.execute(text("SELECT code FROM schools WHERE id = :i"), {"i": school_id}).scalar()
        for slot, t in team_rows.items():
            existing = c.execute(text("SELECT id FROM teams WHERE school_id = :s AND slot = :sl"), {"s": school_id, "sl": slot}).scalar()
            if existing:
                db.update("teams", t, existing, c)
            else:
                db.insert("teams", {**t, "school_id": school_id, "slot": slot, "code": f"{code}-T{slot}", "created_at": now()}, c)
    if status == "approved" and db.setting("auto_assign_jury", "1") == "1":
        assign_school_to_all_juries(school_id)
    db.bump_version()
    return {}, school_id


def school_with_teams(sid: int) -> dict | None:
    s = q_one("SELECT * FROM schools WHERE id = :i", i=sid)
    if not s:
        return None
    s["teams"] = q_all("""SELECT t.*, th.title AS theme, th.num AS theme_num FROM teams t
                          LEFT JOIN themes th ON th.id = t.theme_id WHERE t.school_id = :i ORDER BY t.slot""", i=sid)
    return s


def school_form_values(s: dict | None) -> dict:
    if not s:
        return {}
    v = dict(s)
    for t in s.get("teams", []):
        i = t["slot"]
        v.update({f"team{i}_name": t["name"], f"team{i}_theme": t["theme_id"], f"team{i}_project": t["project_title"],
                  f"team{i}_desc": t["project_desc"], f"team{i}_members": (t["members"] or "").replace(", ", "\n"),
                  f"team{i}_mentor": t["mentor_name"]})
    return v


def set_school_status(user: dict, ids: list[int], status: str, note: str = "") -> int:
    n = 0
    for sid in ids:
        s = q_one("SELECT id, code, name, status FROM schools WHERE id = :i", i=sid)
        if not s or s["status"] == status:
            continue
        update("schools", {"status": status, "admin_note": note or None, "updated_at": now(),
                           "approved_at": now() if status == "approved" else None}, sid)
        log(user, f"school_{status}", f"{s['code']} {s['name']}")
        if status == "approved" and db.setting("auto_assign_jury", "1") == "1":
            assign_school_to_all_juries(sid)
        n += 1
    if n:
        db.bump_version()
    return n


def delete_school(user: dict, sid: int) -> None:
    s = q_one("SELECT code, name FROM schools WHERE id = :i", i=sid)
    if not s:
        return
    with db.engine().begin() as c:  # explicit cascade (works even if FK pragmas are off)
        team_ids = [r[0] for r in c.execute(text("SELECT id FROM teams WHERE school_id = :i"), {"i": sid})]
        for tid in team_ids:
            c.execute(text("DELETE FROM jury_marks WHERE evaluation_id IN (SELECT id FROM jury_evaluations WHERE team_id = :t)"), {"t": tid})
            c.execute(text("DELETE FROM jury_evaluations WHERE team_id = :t"), {"t": tid})
            c.execute(text("DELETE FROM qr_scores WHERE team_id = :t"), {"t": tid})
        c.execute(text("DELETE FROM teams WHERE school_id = :i"), {"i": sid})
        c.execute(text("DELETE FROM jury_assignments WHERE school_id = :i"), {"i": sid})
        c.execute(text("DELETE FROM schools WHERE id = :i"), {"i": sid})
    log(user, "school_deleted", f"{s['code']} {s['name']}")
    db.bump_version()


# ======================================================================
# Leaderboards
# ======================================================================
def _rank(rows: list[dict], field: str) -> list[dict]:
    rank, prev = 0, None
    for i, r in enumerate(rows, 1):
        if prev is None or r[field] != prev:
            rank, prev = i, r[field]
        r["rank"] = rank
    return rows


def team_leaderboard(theme_id: int | None = None) -> list[dict]:
    sql = """SELECT t.id, t.code, t.name, t.slot, t.project_title, t.theme_id, t.members,
                    s.id AS school_id, s.code AS school_code, s.name AS school, s.city,
                    th.num AS theme_num, th.title AS theme,
                    COALESCE((SELECT SUM(q.points) FROM qr_scores q WHERE q.team_id = t.id), 0) AS qr,
                    COALESCE((SELECT AVG(j.total) FROM jury_evaluations j WHERE j.team_id = t.id), 0) AS jury,
                    (SELECT COUNT(*) FROM jury_evaluations j WHERE j.team_id = t.id) AS judges,
                    (SELECT COUNT(*) FROM jury_assignments ja JOIN users u ON u.id = ja.jury_id
                      WHERE ja.school_id = s.id AND u.active = 1 AND u.role = 'jury') AS assigned_judges
             FROM teams t JOIN schools s ON s.id = t.school_id
             LEFT JOIN themes th ON th.id = t.theme_id
             WHERE s.status = 'approved'"""
    params = {}
    if theme_id:
        sql += " AND t.theme_id = :th"
        params["th"] = theme_id
    rows = q_all(sql, **params)
    for r in rows:
        r["qr"] = int(r["qr"] or 0)
        r["jury"] = round(float(r["jury"] or 0), 2)
        r["total"] = round(r["qr"] + r["jury"], 2)
    rows.sort(key=lambda r: (-r["total"], -r["jury"], -r["qr"], r["code"]))
    return _rank(rows, "total")


def sort_by(rows: list[dict], field: str) -> list[dict]:
    rows = sorted((dict(r) for r in rows), key=lambda r: (-r[field], -r["total"], r["code"]))
    return _rank(rows, field)


def school_leaderboard(team_rows: list[dict] | None = None) -> list[dict]:
    team_rows = team_rows if team_rows is not None else team_leaderboard()
    agg: dict[int, dict] = {}
    for t in team_rows:
        s = agg.setdefault(t["school_id"], {"school_id": t["school_id"], "code": t["school_code"], "school": t["school"],
                                            "city": t["city"], "qr": 0, "jury": 0.0, "total": 0.0, "teams": []})
        s["qr"] += t["qr"]
        s["jury"] += t["jury"]
        s["total"] += t["total"]
        s["teams"].append(t["name"])
    rows = list(agg.values())
    for r in rows:
        r["jury"], r["total"] = round(r["jury"], 2), round(r["total"], 2)
    rows.sort(key=lambda r: (-r["total"], -r["jury"], r["code"]))
    return _rank(rows, "total")


def event_stats() -> dict:
    v = lambda sql: int(q_val(sql) or 0)  # noqa: E731
    return {
        "schools_total": v("SELECT COUNT(*) FROM schools"),
        "schools_approved": v("SELECT COUNT(*) FROM schools WHERE status = 'approved'"),
        "schools_pending": v("SELECT COUNT(*) FROM schools WHERE status = 'pending'"),
        "schools_rejected": v("SELECT COUNT(*) FROM schools WHERE status = 'rejected'"),
        "teams": v("SELECT COUNT(*) FROM teams t JOIN schools s ON s.id = t.school_id WHERE s.status = 'approved'"),
        "qr_scores": v("SELECT COUNT(*) FROM qr_scores"),
        "evaluations": v("SELECT COUNT(*) FROM jury_evaluations"),
        "jury_members": v("SELECT COUNT(*) FROM users WHERE role = 'jury' AND active = 1"),
        "rounds": v("SELECT COUNT(*) FROM qr_rounds"),
        "themes": v("SELECT COUNT(*) FROM themes"),
    }


def active_announcements(limit: int = 5) -> list[dict]:
    return q_all(f"SELECT * FROM announcements WHERE active = 1 ORDER BY id DESC LIMIT {int(limit)}")


# ======================================================================
# QR Play Arena
# ======================================================================
def record_qr_score(user: dict, round_id: int, team_code: str, points: int, remarks: str, overwrite: bool,
                    allow_inactive: bool) -> tuple[bool, str, bool]:
    """Returns (ok, message, exists_needs_confirm)."""
    rnd = q_one("SELECT * FROM qr_rounds WHERE id = :i", i=round_id)
    if not rnd:
        return False, "Round not found.", False
    if not allow_inactive and rnd["status"] != "active":
        return False, "This round is not active. Ask the admin to activate it.", False
    team = q_one("""SELECT t.id, t.code, t.name FROM teams t JOIN schools s ON s.id = t.school_id
                    WHERE UPPER(t.code) = :c AND s.status = 'approved'""", c=team_code.strip().upper())
    if not team:
        return False, f"Team ID \"{team_code}\" not found or school not approved.", False
    if not (0 <= points <= rnd["max_points"]):
        return False, f"Points must be between 0 and {rnd['max_points']}.", False
    ex = q_one("SELECT id, points FROM qr_scores WHERE round_id = :r AND team_id = :t", r=round_id, t=team["id"])
    if ex and not overwrite:
        return False, f"{team['code']} already has {ex['points']} points in this round.", True
    if ex:
        update("qr_scores", {"points": points, "remarks": remarks, "volunteer_id": user["id"], "updated_at": now()}, ex["id"])
    else:
        insert("qr_scores", {"round_id": round_id, "team_id": team["id"], "points": points, "remarks": remarks,
                             "volunteer_id": user["id"], "created_at": now()})
    db.bump_version()
    log(user, "qr_score", f"R{rnd['num']} {team['code']} = {points}" + (f" (was {ex['points']})" if ex else ""))
    return True, f"Saved {points} pts for {team['code']} · {team['name']}", False


def round_scores(round_id: int) -> list[dict]:
    return q_all("""SELECT q.id, t.code, t.name AS team, s.name AS school, q.points, q.remarks,
                           u.name AS volunteer, COALESCE(q.updated_at, q.created_at) AS time
                    FROM qr_scores q JOIN teams t ON t.id = q.team_id JOIN schools s ON s.id = t.school_id
                    LEFT JOIN users u ON u.id = q.volunteer_id WHERE q.round_id = :r
                    ORDER BY COALESCE(q.updated_at, q.created_at) DESC""", r=round_id)


def set_round_status(user: dict, round_id: int, status: str) -> None:
    if status == "active":
        execute("UPDATE qr_rounds SET status = 'closed' WHERE status = 'active' AND id <> :i", i=round_id)
        update("qr_rounds", {"status": "active", "activated_at": now()}, round_id)
    else:
        update("qr_rounds", {"status": status}, round_id)
    db.bump_version()
    log(user, "round_status", f"Round {q_val('SELECT num FROM qr_rounds WHERE id = :i', i=round_id)} → {status}")


def regenerate_round_token(user: dict, round_id: int) -> None:
    update("qr_rounds", {"token": secrets.token_hex(8)}, round_id)
    log(user, "round_qr_regenerated", f"round id {round_id}")


# ======================================================================
# Jury
# ======================================================================
def jury_members(active_only: bool = False) -> list[dict]:
    sql = """SELECT u.*,
        (SELECT COUNT(*) FROM jury_assignments ja JOIN schools s ON s.id = ja.school_id AND s.status = 'approved' WHERE ja.jury_id = u.id) AS schools,
        (SELECT COUNT(*) FROM jury_assignments ja JOIN schools s ON s.id = ja.school_id AND s.status = 'approved'
            JOIN teams t ON t.school_id = s.id WHERE ja.jury_id = u.id) AS teams_assigned,
        (SELECT COUNT(*) FROM jury_evaluations je WHERE je.jury_id = u.id) AS evaluated
        FROM users u WHERE u.role = 'jury'"""
    if active_only:
        sql += " AND u.active = 1"
    return q_all(sql + " ORDER BY u.id")


def create_jury(user: dict, rows: list[dict], assign_all: bool) -> tuple[list[dict], list[str]]:
    from .security import generate_password

    created, errors = [], []
    for i, r in enumerate(rows, 1):
        name, email, desig = (r.get("name") or "").strip(), (r.get("email") or "").strip().lower(), (r.get("designation") or "").strip()
        if not name and not email:
            continue
        if not name or not valid_email(email):
            errors.append(f"Row {i}: name and a valid email are required.")
            continue
        if q_val("SELECT id FROM users WHERE LOWER(email) = :e", e=email):
            errors.append(f"{email} is already registered.")
            continue
        pw = generate_password()
        jid = insert("users", {"name": name, "designation": desig or None, "email": email, "password_hash": hash_password(pw),
                               "role": "jury", "active": 1, "must_change_pw": 0, "created_at": now()})
        created.append({"id": jid, "name": name, "designation": desig, "email": email, "password": pw})
        log(user, "jury_created", f"{name} <{email}>")
    if created and assign_all:
        for s in q_all("SELECT id FROM schools WHERE status = 'approved'"):
            for c in created:
                _assign(c["id"], s["id"])
        db.bump_version()
    return created, errors


def _assign(jury_id: int, school_id: int) -> None:
    if not q_val("SELECT id FROM jury_assignments WHERE jury_id = :j AND school_id = :s", j=jury_id, s=school_id):
        insert("jury_assignments", {"jury_id": jury_id, "school_id": school_id, "created_at": now()})


def assign_school_to_all_juries(school_id: int) -> None:
    for j in q_all("SELECT id FROM users WHERE role = 'jury' AND active = 1"):
        _assign(j["id"], school_id)


def assignment_map() -> dict[int, set[int]]:
    m: dict[int, set[int]] = {}
    for r in q_all("SELECT jury_id, school_id FROM jury_assignments"):
        m.setdefault(r["school_id"], set()).add(r["jury_id"])
    return m


def save_assignments(user: dict, desired: dict[tuple[int, int], bool]) -> tuple[int, int]:
    """desired: {(school_id, jury_id): bool}. Returns (added, removed)."""
    current = assignment_map()
    added = removed = 0
    for (sid, jid), on in desired.items():
        has = jid in current.get(sid, set())
        if on and not has:
            _assign(jid, sid)
            added += 1
        elif not on and has:
            execute("DELETE FROM jury_assignments WHERE jury_id = :j AND school_id = :s", j=jid, s=sid)
            removed += 1
    if added or removed:
        db.bump_version()
        log(user, "jury_assignments", f"+{added} / -{removed}")
    return added, removed


def auto_assign(user: dict, per_school: int, replace: bool) -> str:
    juries = [r["id"] for r in q_all("SELECT id FROM users WHERE role = 'jury' AND active = 1 ORDER BY id")]
    schools_ = [r["id"] for r in q_all("SELECT id FROM schools WHERE status = 'approved' ORDER BY id")]
    if not juries or not schools_:
        return "You need at least one active jury member and one approved school."
    k = max(1, min(len(juries), per_school))
    if replace:
        execute("DELETE FROM jury_assignments")
    for i, sid in enumerate(schools_):
        for m in range(k):
            _assign(juries[(i + m) % len(juries)], sid)
    db.bump_version()
    log(user, "jury_auto_assign", f"{len(schools_)} schools × {k} judges")
    return f"Assigned {k} jury member(s) to each of {len(schools_)} schools."


def jury_can_evaluate(jury_id: int, team_id: int) -> bool:
    return bool(q_val("""SELECT 1 FROM teams t JOIN schools s ON s.id = t.school_id
                         JOIN jury_assignments ja ON ja.school_id = s.id AND ja.jury_id = :j
                         WHERE t.id = :t AND s.status = 'approved'""", j=jury_id, t=team_id))


def jury_teams(jury_id: int) -> list[dict]:
    return q_all("""SELECT t.id, t.code, t.name, t.project_title, t.project_desc, t.members, s.name AS school,
                           th.num AS theme_num, th.title AS theme, j.id AS eval_id, j.total, j.remarks
                    FROM teams t JOIN schools s ON s.id = t.school_id LEFT JOIN themes th ON th.id = t.theme_id
                    JOIN jury_assignments ja ON ja.school_id = s.id AND ja.jury_id = :j
                    LEFT JOIN jury_evaluations j ON j.team_id = t.id AND j.jury_id = :j
                    WHERE s.status = 'approved' ORDER BY t.code""", j=jury_id)


def evaluation_marks(eval_id: int) -> dict[int, float]:
    return {r["criterion_id"]: float(r["marks"]) for r in q_all("SELECT criterion_id, marks FROM jury_marks WHERE evaluation_id = :e", e=eval_id)}


def save_evaluation(team_id: int, jury_id: int, marks: dict[int, float], remarks: str = "") -> float:
    crit = criteria_list()
    clean = {}
    for c in crit:
        m = float(marks.get(c["id"], 0) or 0)
        clean[c["id"]] = max(0.0, min(float(c["max_marks"]), round(m * 2) / 2))
    total = round(sum(clean.values()), 2)
    with db.engine().begin() as conn:
        eid = conn.execute(text("SELECT id FROM jury_evaluations WHERE team_id = :t AND jury_id = :j"), {"t": team_id, "j": jury_id}).scalar()
        if eid:
            db.update("jury_evaluations", {"total": total, "remarks": remarks, "updated_at": now()}, eid, conn)
            conn.execute(text("DELETE FROM jury_marks WHERE evaluation_id = :e"), {"e": eid})
        else:
            eid = db.insert("jury_evaluations", {"team_id": team_id, "jury_id": jury_id, "total": total,
                                                 "remarks": remarks, "created_at": now()}, conn)
        for cid, m in clean.items():
            db.insert("jury_marks", {"evaluation_id": eid, "criterion_id": cid, "marks": m}, conn)
    db.bump_version()
    return total


def delete_evaluation(user: dict, eval_id: int) -> None:
    ev = q_one("""SELECT j.id, t.code, u.name FROM jury_evaluations j JOIN teams t ON t.id = j.team_id
                  JOIN users u ON u.id = j.jury_id WHERE j.id = :i""", i=eval_id)
    if ev:
        execute("DELETE FROM jury_marks WHERE evaluation_id = :i", i=eval_id)
        execute("DELETE FROM jury_evaluations WHERE id = :i", i=eval_id)
        db.bump_version()
        log(user, "jury_score_deleted", f"{ev['code']} by {ev['name']}")


def delete_user(user: dict, uid: int) -> str | None:
    n = int(q_val("SELECT COUNT(*) FROM jury_evaluations WHERE jury_id = :i", i=uid) or 0)
    if n:
        return f"This person has submitted {n} evaluation(s). Disable the account instead so the marks stay in the results."
    execute("UPDATE qr_scores SET volunteer_id = NULL WHERE volunteer_id = :i", i=uid)
    execute("DELETE FROM jury_assignments WHERE jury_id = :i", i=uid)
    execute("UPDATE announcements SET created_by = NULL WHERE created_by = :i", i=uid)
    execute("DELETE FROM users WHERE id = :i", i=uid)
    db.bump_version()
    log(user, "user_deleted", f"id {uid}")
    return None


def reset_all_scores(user: dict) -> None:
    execute("DELETE FROM jury_marks")
    execute("DELETE FROM jury_evaluations")
    execute("DELETE FROM qr_scores")
    execute("UPDATE qr_rounds SET status = 'inactive', activated_at = NULL")
    db.bump_version()
    log(user, "scores_reset", "All QR + jury scores cleared")
