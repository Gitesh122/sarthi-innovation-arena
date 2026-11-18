# Sarthi Innovation Arena 2027 — Python / Streamlit Edition

The event management system rewritten in **Python + Streamlit**. It keeps every feature of the PHP version: public website, school registration, role-based admin panel, QR Play Arena, the Jury Panel with school assignments, live leaderboards, reports and the brand gradient theme.

**Stack:** Python 3.10+ · Streamlit · SQLAlchemy (SQLite locally, PostgreSQL in the cloud) · Pandas · Plotly · qrcode

---

## What's new in 4.1
- **Navigation that never disappears on phones:** a swipeable menu strip (with *Sign out*) sits at the top of every page on mobile/tablet, and whenever the sidebar is collapsed on a laptop. The sidebar toggle button is now always visible.
- **Mobile-first layout:** larger touch targets, 2-column KPI cards, compact tables/podium, no iOS zoom on inputs, compact login screen.
- **Hosting resilience:** database connections auto-retry (serverless Postgres waking up), stale connections are recycled, and any unexpected error shows a friendly *Reload* card instead of a raw traceback.

## 1. Run on your computer (2 minutes)

```bash
cd sarthi_streamlit
pip install -r requirements.txt
streamlit run app.py
```
Open **http://localhost:8501**. There is no install screen: the database (`data/arena.sqlite`) is created automatically on the first run.

**First-run administrator** (you must change the password at first sign-in):

| Email | Temporary password |
|---|---|
| `admin@sarthiarena.in` | `Sarthi@2027` |

Change these defaults in `core/config.py` before you deploy.

**Rehearsal data (optional):** `python tools/seed_demo.py` loads 6 schools, 3 jury members (`jury1..3@arena.local` / `Jury@123`), a volunteer (`volunteer@arena.local` / `Volunteer@123`) and sample scores. Never run it on the live database.

### Event day on a laptop (most reliable, no internet needed)
```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```
Connect judges and volunteers to the same Wi-Fi or hotspot. They open `http://<laptop-IP>:8501`.
In **Settings**, set *Public app URL* to `http://<laptop-IP>:8501` so the QR codes point to the laptop.

---

## 2. Deploy free on Streamlit Community Cloud

> ⚠️ **Important:** Streamlit Cloud's disk is temporary. It is wiped whenever the app restarts or sleeps.
> For a hosted app you **must** use a free cloud PostgreSQL database (step B), or registrations and scores will be lost.

**A. Put the code on GitHub**
1. Create a free GitHub account and a new repository (for example `sarthi-arena`).
2. Upload all files from this folder. `data/*.sqlite` and `secrets.toml` are ignored automatically.

**B. Create a free PostgreSQL database (Neon)**
1. Sign up at **neon.com** (free, no credit card) → create a project.
2. Copy the **connection string**. It looks like
   `postgresql://user:password@ep-xxxx.aws.neon.tech/neondb?sslmode=require`

**C. Deploy**
1. Go to **share.streamlit.io** and sign in with GitHub.
2. Click **Create app** → choose your repository, branch `main`, main file `app.py`.
3. Open **Advanced settings → Secrets** and paste:
   ```toml
   DATABASE_URL = "postgresql://user:password@ep-xxxx.aws.neon.tech/neondb?sslmode=require"
   ```
4. Click **Deploy**. Your app goes live at `https://<your-name>.streamlit.app`. The tables are created automatically.
5. Sign in as admin → **Settings** → set *Public app URL* to your `.streamlit.app` address, so the QR codes are correct.

**Free-tier notes**
- Apps sleep after a period with no visitors. The first visit wakes the app in under a minute. Open the app yourself before the event starts.
- The free container has limited memory (about 1 GB). That is fine for registrations and the public leaderboard. For the live competition day, with many judges, volunteers and screens refreshing every few seconds, the **laptop setup above is the safest option**. You can point the laptop at the same Neon database by setting `DATABASE_URL`, so no data needs copying.

---

## 3. Features

### Public
- **Home:** event hero with countdown, announcements ticker, live stats, two zones, four themes, five QR rounds, live Top 5, scoring model
- **School Registration:** school + 2 teams, validation, duplicate detection, automatic School and Team IDs (SCH001, SCH001-T1/T2)
- **Check Status:** School ID + email → approval status and scores
- **Live Leaderboard:** School / Team / QR / Jury views, theme filter, search. Updates automatically every 4 seconds
- **Big screen** (`/screen`): dark projector view with podium; the team ranking rotates between views every 12 seconds
- **QR scan page** (`/scan?t=…`): round instructions, shown only while the round is active

### Staff (role-based)
| Module | Admin | Volunteer | Jury |
|---|:-:|:-:|:-:|
| Dashboard: KPIs, Plotly charts, top teams, school ranking, live activity | ✅ | | |
| Schools: approve / reject with a reason / bulk actions / add / edit / delete | ✅ | | |
| Teams list with filters | ✅ | | |
| QR Play Arena: activate/close rounds, QR codes (PNG), projector view that follows the active round, score entry | ✅ | ✅ (active round only) | |
| **Jury Panel:** create 3+ judges at once, auto-generated passwords, printable login slips and CSV, assignment grid, auto-assign | ✅ | | |
| Jury Evaluation: assigned schools only, sliders with half marks, live total, moves to the next project automatically | matrix + mark sheets | | ✅ |
| Live Leaderboard + public visible/hidden and live/frozen switches | ✅ | 👁 | 👁 |
| Announcements, Users & Roles, Settings, Activity log | ✅ | | |
| Reports: complete **Excel workbook**, CSV exports, printable official results sheet | ✅ | | |

### Scoring
- QR: 5 rounds × 10 = **50** · Jury rubric 15/20/30/20/15 = **100** (several judges → **average**)
- Team total **150** · School total (both teams) **300** · ties broken by Jury score, then QR score

### Security
- Passwords: PBKDF2-SHA256 with 240,000 iterations.
- First admin login forces a password change.
- Five failed logins lock that email for 5 minutes.
- **Secure session cookie:** the token is stored only as a hash, the session lasts 14 hours, staff stay signed in when they refresh, and access ends at sign-out or when an account is disabled.
- Role checks on every page and every action.
- Judges can only score assigned schools, and all-zero mark sheets are blocked.
- Full audit log.
- CSV formula-injection guard.

---

## 4. Event-day workflow
1. **Before:** schools register → admin approves → **Jury Panel → Add jury members** (tick "assign all approved schools") → download the login slips → add volunteers in **Users & Roles**.
2. **QR Arena:** QR Play Arena → open a round → **Activate**. Open the **Projector view** at the station. Volunteers record scores on their phones.
3. **Hackathon:** judges sign in → pick a project → move the sliders → confirm → Submit.
4. **Display:** open `/screen` on the hall projector.
5. **Results:** Live Leaderboard → **Scores: frozen** → Jury Evaluation → **Lock final scores** → Reports → **Official results sheet**.

## 5. Project structure
```
sarthi_streamlit/
├── app.py                   ← entry point, navigation, sessions
├── core/
│   ├── config.py            ← settings, defaults, DB URL
│   ├── db.py                ← tables, provisioning, query helpers
│   ├── security.py          ← password hashing & validation
│   ├── services.py          ← business logic (schools, scoring, jury, QR, sessions)
│   └── ui.py                ← theme CSS, KPI cards, tables, cookies
├── views/
│   ├── public.py            ← home, register, status, leaderboard, big screen
│   ├── staff.py             ← login, profile / forced password change
│   ├── admin.py             ← dashboard, schools, teams, announcements, users, reports, settings, logs
│   ├── jury.py              ← Jury Panel + evaluation
│   └── qr.py                ← QR scan page, round control, projector
├── assets/                  ← logo & icon
├── tools/seed_demo.py       ← rehearsal data
├── .streamlit/config.toml   ← brand theme
└── requirements.txt
```

## 6. Reset
- **SQLite:** delete `data/arena.sqlite`.
- **Neon:** drop the tables, or create a new database.

The app sets itself up again on the next visit.
