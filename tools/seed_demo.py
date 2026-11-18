"""Load rehearsal data (6 schools, 3 jury, 1 volunteer, sample scores).

    python tools/seed_demo.py

Never run this against the live competition database.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import db, services  # noqa: E402
from core.security import hash_password  # noqa: E402

if int(db.q_val("SELECT COUNT(*) FROM schools") or 0):
    sys.exit("Database already has schools; demo data not loaded.")

th = [t["id"] for t in services.themes_list()]
first = ["Aarav", "Diya", "Vihaan", "Ananya", "Ishaan", "Saanvi", "Kabir", "Myra", "Arjun", "Kiara"]
data = [("ABC Public School", "Nagpur", "Ritu Sharma", ["Tech Titans", "Innovators"], "approved"),
        ("XYZ Vidyalaya", "Nagpur", "Amit Deshmukh", ["Bot Squad", "Future Minds"], "approved"),
        ("Global School", "Wardha", "Sneha Patil", ["Code Crew", "NextGen"], "approved"),
        ("Sunrise Convent", "Kamptee", "Rahul Joshi", ["Robo Rangers", "Spark Labs"], "approved"),
        ("Vidya Niketan", "Bhandara", "Pooja Kulkarni", ["Circuit Breakers", "Idea Forge"], "pending"),
        ("Modern High School", "Nagpur", "Kiran Rao", ["Tinker Tribe", "Byte Busters"], "pending")]
for i, (name, city, contact, teams, status) in enumerate(data):
    d = {"name": name, "city": city, "district": city, "contact_name": contact, "principal_name": "Principal " + contact.split()[1],
         "email": name.lower().replace(" ", "") + "@school.example", "phone": f"+91 98{2210000 + i * 731:08d}", "address": f"{city}, Maharashtra"}
    for k, tn in enumerate(teams, 1):
        d.update({f"team{k}_name": tn, f"team{k}_theme": th[(i * 2 + k - 1) % 4],
                  f"team{k}_project": ["Smart Craft Catalogue", "AgriBot Lite", "Women SkillHub", "Waste Sorter AI", "Local Story AI", "Utility Rover"][(i + k) % 6],
                  f"team{k}_members": "\n".join(first[(i + k * 3) % 6:(i + k * 3) % 6 + 4]), f"team{k}_mentor": contact})
    err, _ = services.save_school(d, None, status)
    assert not err, err

db.insert("users", {"name": "Demo Volunteer", "email": "volunteer@arena.local", "password_hash": hash_password("Volunteer@123"),
                    "role": "volunteer", "active": 1, "must_change_pw": 0, "created_at": db.now()})
admin = db.q_one("SELECT * FROM users WHERE role = 'admin' ORDER BY id LIMIT 1")
created, _ = services.create_jury(admin, [
    {"name": "Dr. Meera Iyer", "designation": "Professor, VNIT Nagpur", "email": "jury1@arena.local"},
    {"name": "Prof. Sanjay Kale", "designation": "Robotics Mentor, AIM", "email": "jury2@arena.local"},
    {"name": "Ms. Ananya Rao", "designation": "Startup Founder", "email": "jury3@arena.local"}], assign_all=True)
for c in created:
    db.update("users", {"password_hash": hash_password("Jury@123")}, c["id"])

teams = db.q_all("SELECT t.id FROM teams t JOIN schools s ON s.id = t.school_id WHERE s.status = 'approved' ORDER BY t.id")
rounds = db.q_all("SELECT id FROM qr_rounds ORDER BY num LIMIT 3")
crit = services.criteria_list()
for ti, t in enumerate(teams):
    for ri, r in enumerate(rounds):
        db.insert("qr_scores", {"round_id": r["id"], "team_id": t["id"], "points": 6 + (ti * 3 + ri * 5) % 5, "created_at": db.now()})
    for ji, j in enumerate(created[:2]):
        if ji == 1 and ti % 3 == 2:
            continue
        services.save_evaluation(t["id"], j["id"], {c["id"]: max(0, c["max_marks"] - (ti * 2 + ci + ji * 3) % 6) for ci, c in enumerate(crit)}, "Demo evaluation")
db.insert("announcements", {"message": "Welcome to Sarthi Innovation Arena 2027! QR Play Arena rounds are running at Zone 01.",
                            "level": "info", "active": 1, "created_at": db.now()})
print("Demo data loaded: jury1..3@arena.local / Jury@123 · volunteer@arena.local / Volunteer@123")
