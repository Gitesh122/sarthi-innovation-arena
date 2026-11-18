"""Database layer — SQLAlchemy Core, portable between SQLite and PostgreSQL."""
from __future__ import annotations

import secrets
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import (Column, Float, ForeignKey, Integer, MetaData, String, Table, Text,
                        UniqueConstraint, create_engine, event, text)
from sqlalchemy.engine import Engine

from . import config

metadata = MetaData()

users = Table("users", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(120), nullable=False),
    Column("email", String(160), nullable=False, unique=True),
    Column("password_hash", String(255), nullable=False),
    Column("role", String(20), nullable=False, default="volunteer"),
    Column("designation", String(150)),
    Column("must_change_pw", Integer, nullable=False, default=0),
    Column("active", Integer, nullable=False, default=1),
    Column("last_login", String(19)),
    Column("created_at", String(19), nullable=False),
)
themes = Table("themes", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("num", Integer, nullable=False),
    Column("title", String(200), nullable=False),
    Column("description", Text),
    Column("examples", Text),
)
schools = Table("schools", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("code", String(20), unique=True),
    Column("name", String(200), nullable=False),
    Column("udise", String(30)),
    Column("atl_code", String(40)),
    Column("city", String(100)),
    Column("district", String(100)),
    Column("address", Text),
    Column("principal_name", String(120)),
    Column("contact_name", String(120), nullable=False),
    Column("email", String(160), nullable=False),
    Column("phone", String(20), nullable=False),
    Column("status", String(20), nullable=False, default="pending"),
    Column("admin_note", Text),
    Column("created_at", String(19), nullable=False),
    Column("updated_at", String(19)),
    Column("approved_at", String(19)),
)
teams = Table("teams", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("school_id", Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
    Column("slot", Integer, nullable=False),
    Column("code", String(30), unique=True),
    Column("name", String(120), nullable=False),
    Column("theme_id", Integer, ForeignKey("themes.id", ondelete="SET NULL")),
    Column("project_title", String(200)),
    Column("project_desc", Text),
    Column("members", Text),
    Column("mentor_name", String(120)),
    Column("created_at", String(19), nullable=False),
)
qr_rounds = Table("qr_rounds", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("num", Integer, nullable=False),
    Column("title", String(150), nullable=False),
    Column("description", Text),
    Column("instructions", Text),
    Column("max_points", Integer, nullable=False, default=10),
    Column("token", String(40), nullable=False, unique=True),
    Column("status", String(20), nullable=False, default="inactive"),
    Column("activated_at", String(19)),
)
qr_scores = Table("qr_scores", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("round_id", Integer, ForeignKey("qr_rounds.id", ondelete="CASCADE"), nullable=False),
    Column("team_id", Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
    Column("points", Integer, nullable=False),
    Column("remarks", String(255)),
    Column("volunteer_id", Integer, ForeignKey("users.id", ondelete="SET NULL")),
    Column("created_at", String(19), nullable=False),
    Column("updated_at", String(19)),
    UniqueConstraint("round_id", "team_id"),
)
criteria = Table("criteria", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(120), nullable=False),
    Column("max_marks", Integer, nullable=False),
    Column("sort", Integer, nullable=False, default=0),
)
jury_evaluations = Table("jury_evaluations", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("team_id", Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
    Column("jury_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("total", Float, nullable=False, default=0),
    Column("remarks", Text),
    Column("created_at", String(19), nullable=False),
    Column("updated_at", String(19)),
    UniqueConstraint("team_id", "jury_id"),
)
jury_marks = Table("jury_marks", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("evaluation_id", Integer, ForeignKey("jury_evaluations.id", ondelete="CASCADE"), nullable=False),
    Column("criterion_id", Integer, ForeignKey("criteria.id", ondelete="CASCADE"), nullable=False),
    Column("marks", Float, nullable=False, default=0),
    UniqueConstraint("evaluation_id", "criterion_id"),
)
jury_assignments = Table("jury_assignments", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("jury_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("school_id", Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", String(19), nullable=False),
    UniqueConstraint("jury_id", "school_id"),
)
settings = Table("settings", metadata,
    Column("skey", String(60), primary_key=True),
    Column("svalue", Text),
)
announcements = Table("announcements", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("message", String(500), nullable=False),
    Column("level", String(20), nullable=False, default="info"),
    Column("active", Integer, nullable=False, default=1),
    Column("created_by", Integer, ForeignKey("users.id", ondelete="SET NULL")),
    Column("created_at", String(19), nullable=False),
)
activity_log = Table("activity_log", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer),
    Column("user_name", String(120)),
    Column("action", String(60), nullable=False),
    Column("details", String(500)),
    Column("created_at", String(19), nullable=False),
)

sessions = Table("sessions", metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("expires_at", String(19), nullable=False),
    Column("created_at", String(19), nullable=False),
)

TABLES = {t.name: t for t in metadata.sorted_tables}

_engine: Engine | None = None
_lock = threading.Lock()


def now() -> str:
    return datetime.now(ZoneInfo(config.TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S")


def _pg_creator(url: str):
    """psycopg2 connector that retries: serverless Postgres (Neon) needs a few seconds to wake after idling."""
    import time

    import psycopg2

    dsn = url.replace("postgresql+psycopg2://", "postgresql://", 1)

    def _connect():
        last = None
        for wait in (0, 1.5, 3, 5):
            if wait:
                time.sleep(wait)
            try:
                return psycopg2.connect(dsn, connect_timeout=20, keepalives=1, keepalives_idle=30,
                                        keepalives_interval=10, keepalives_count=5)
            except psycopg2.OperationalError as exc:  # database still waking up / transient network error
                last = exc
        raise last  # type: ignore[misc]

    return _connect



def engine() -> Engine:
    global _engine
    if _engine is None:
        with _lock:
            if _engine is None:
                url = config.database_url()
                if url.startswith("sqlite"):
                    eng = create_engine(url, connect_args={"check_same_thread": False, "timeout": 15}, future=True)

                    @event.listens_for(eng, "connect")
                    def _sqlite_pragmas(dbapi_conn, _):  # noqa: ANN001
                        cur = dbapi_conn.cursor()
                        cur.execute("PRAGMA foreign_keys=ON")
                        cur.execute("PRAGMA journal_mode=WAL")
                        cur.execute("PRAGMA busy_timeout=8000")
                        cur.close()
                else:
                    eng = create_engine(url, pool_pre_ping=True, pool_recycle=240, pool_size=4, max_overflow=6,
                                        pool_timeout=30, future=True, creator=_pg_creator(url))
                _engine = eng
                _provision(eng)
    return _engine


def is_sqlite() -> bool:
    return engine().dialect.name == "sqlite"


# ---------- query helpers ----------
def _retry(fn):
    """Retry once on a dropped connection (serverless DB restarts, idle timeouts)."""
    import functools

    from sqlalchemy.exc import DBAPIError, OperationalError

    @functools.wraps(fn)
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except (OperationalError, DBAPIError) as exc:
            if not (isinstance(exc, OperationalError) or getattr(exc, "connection_invalidated", False)):
                raise
            engine().dispose()
            return fn(*a, **kw)

    return wrapper


@_retry
def q_all(sql: str, **params) -> list[dict]:
    with engine().connect() as c:
        return [dict(r._mapping) for r in c.execute(text(sql), params)]


@_retry
def q_one(sql: str, **params) -> dict | None:
    with engine().connect() as c:
        r = c.execute(text(sql), params).first()
        return dict(r._mapping) if r else None


@_retry
def q_val(sql: str, **params):
    with engine().connect() as c:
        r = c.execute(text(sql), params).first()
        return r[0] if r else None


@_retry
def execute(sql: str, **params) -> int:
    with engine().begin() as c:
        return c.execute(text(sql), params).rowcount


def insert(table: str, data: dict, conn=None) -> int:
    t = TABLES[table]
    if conn is not None:
        return conn.execute(t.insert().values(**data)).inserted_primary_key[0]
    with engine().begin() as c:
        return c.execute(t.insert().values(**data)).inserted_primary_key[0]


def update(table: str, data: dict, row_id: int, conn=None) -> None:
    t = TABLES[table]
    stmt = t.update().where(t.c.id == row_id).values(**data)
    if conn is not None:
        conn.execute(stmt)
        return
    with engine().begin() as c:
        c.execute(stmt)


# ---------- settings ----------
def setting(key: str, default: str = "") -> str:
    v = q_val("SELECT svalue FROM settings WHERE skey = :k", k=key)
    return default if v is None else str(v)


def set_setting(key: str, value: str) -> None:
    with engine().begin() as c:
        exists = c.execute(text("SELECT 1 FROM settings WHERE skey = :k"), {"k": key}).first()
        if exists:
            c.execute(text("UPDATE settings SET svalue = :v WHERE skey = :k"), {"k": key, "v": value})
        else:
            c.execute(text("INSERT INTO settings (skey, svalue) VALUES (:k, :v)"), {"k": key, "v": value})


def bump_version() -> None:
    set_setting("data_version", secrets.token_hex(6))


# ---------- first-run provisioning ----------
def _provision(eng: Engine) -> None:
    metadata.create_all(eng)
    with eng.begin() as c:
        if c.execute(text("SELECT COUNT(*) FROM themes")).scalar():
            return
        _seed_core(c)


def _seed_core(c) -> None:
    from .security import hash_password

    for n, t, d, x in [
        (1, "Women Empowerment – Smart Tech Leader", "Technology for women-led skills, micro-enterprises and opportunities.", "AI Business Assistant, Digital Product Catalogue, Skill-to-Business Platform"),
        (2, "Vocal for Local – Local Innovation Revival", "Technology for local products, crafts, traditional skills and regional knowledge.", "Local Product Finder, Craft Digitisation, AI Product Storytelling"),
        (3, "Social & Productive Work – Smart Everyday Solutions", "Use AI, IoT or automation to make everyday work simpler, smarter and more productive.", "Smart Workspace, Resource Monitor, Intelligent Sorting"),
        (4, "Swadeshi Multipurpose Robot – Build for India", "Low-cost robotic solutions for local and everyday requirements.", "Utility Robot, Collection Robot, Agriculture Assistant"),
    ]:
        insert("themes", {"num": n, "title": t, "description": d, "examples": x}, c)

    for n, t, d, ins in [
        (1, "Tech Dumb Charades", "Act out a technology word without speaking. Team guesses within the time limit.",
         "One member picks a technology word card from the volunteer.\nAct it out — no speaking, no lip-syncing, no pointing at objects.\nTeammates have 60 seconds to guess.\nUp to 10 points: 2 points per correct word (max 5 words)."),
        (2, "Emoji Decode Challenge", "Decode technology concepts from emoji clues.",
         "The volunteer shows a sheet of 5 emoji puzzles.\nEach puzzle hides a technology concept (e.g. ☁️💻 = Cloud Computing).\nYou have 2 minutes for all 5.\n2 points per correct answer."),
        (3, "Human Robot Challenge", "Guide a participant through a simple route using movement commands.",
         "One member is blindfolded and becomes the \"robot\".\nTeammates may only use commands: FORWARD n, LEFT, RIGHT, STOP.\nGuide the robot through the taped route to the goal.\nPoints for accuracy, time and boundaries touched (max 10)."),
        (4, "Tech Pictionary", "Draw a mystery technology word without letters or numbers.",
         "One member draws the mystery word on the board.\nNo letters, numbers or symbols allowed.\nTeam has 90 seconds to guess as many words as possible.\n2 points per correct word (max 10)."),
        (5, "Sell the Impossible", "Create a short advertisement for a funny imaginary invention.",
         "Pick a random \"impossible invention\" card.\nPrepare for 2 minutes, then pitch a 60-second advertisement.\nJudged on creativity, humour and teamwork.\nMaximum 10 points."),
    ]:
        insert("qr_rounds", {"num": n, "title": t, "description": d, "instructions": ins, "max_points": 10,
                             "token": secrets.token_hex(8), "status": "inactive"}, c)

    for i, (n, m) in enumerate([("Problem Understanding", 15), ("Novelty & Uniqueness", 20),
                                ("Working Prototype / Display Model", 30), ("Practicality & Impact", 20),
                                ("Presentation & Teamwork", 15)]):
        insert("criteria", {"name": n, "max_marks": m, "sort": i + 1}, c)

    for k, v in {
        "event_name": config.APP_NAME, "event_tagline": "ATL Mega Event · Nagpur Region",
        "event_date": "2027-01-23", "event_venue": "Nagpur, Maharashtra",
        "registration_open": "1", "leaderboard_public": "1", "show_scores_public": "1",
        "jury_locked": "0", "auto_assign_jury": "1", "max_schools": "60",
        "contact_email": "events@sarthi.example", "contact_phone": "+91 90000 00000",
        "public_url": "", "data_version": secrets.token_hex(6),
    }.items():
        c.execute(text("INSERT INTO settings (skey, svalue) VALUES (:k, :v)"), {"k": k, "v": v})

    insert("users", {"name": config.DEFAULT_ADMIN_NAME, "email": config.DEFAULT_ADMIN_EMAIL,
                     "password_hash": hash_password(config.DEFAULT_ADMIN_PASSWORD), "role": "admin",
                     "must_change_pw": 1, "active": 1, "created_at": now()}, c)
