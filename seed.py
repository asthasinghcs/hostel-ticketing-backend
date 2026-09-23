"""
Seeds the hostel_ticketing.db with sample students, wardens/admins,
and a realistic spread of tickets (some old/overdue, some recent,
some resolved) so the app looks populated for a demo.

Run: python3 seed.py
"""
import sqlite3
import hashlib
from datetime import datetime, timedelta

DB_PATH = "hostel_ticketing.db"


def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def run():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(open("schema.sql").read())
    cur = conn.cursor()

    # ---- Users ----
    students = [
        ("Astha Sharma", "astha@kiit.ac.in", "KP-2"),
        ("Rohit Verma", "rohit@kiit.ac.in", "KP-2"),
        ("Priya Nair", "priya@kiit.ac.in", "KP-1"),
        ("Aman Gupta", "aman@kiit.ac.in", "KP-3"),
        ("Sneha Das", "sneha@kiit.ac.in", "KP-1"),
        ("Kabir Singh", "kabir@kiit.ac.in", "KP-2"),
        ("Ritika Roy", "ritika@kiit.ac.in", "KP-3"),
        ("Yash Patel", "yash@kiit.ac.in", "KP-1"),
        ("Meera Iyer", "meera@kiit.ac.in", "KP-2"),
        ("Dev Malhotra", "dev@kiit.ac.in", "KP-3"),
    ]
    for name, email, block in students:
        cur.execute(
            "INSERT INTO users (name, email, password, role, hostel_block) VALUES (?,?,?,?,?)",
            (name, email, hash_pw("password123"), "student", block),
        )

    wardens = [
        ("Warden KP-1", "warden.kp1@kiit.ac.in", "KP-1"),
        ("Warden KP-2", "warden.kp2@kiit.ac.in", "KP-2"),
        ("Admin Office", "admin@kiit.ac.in", None),
    ]
    roles = ["warden", "warden", "admin"]
    for (name, email, block), role in zip(wardens, roles):
        cur.execute(
            "INSERT INTO users (name, email, password, role, hostel_block) VALUES (?,?,?,?,?)",
            (name, email, hash_pw("adminpass"), role, block),
        )

    conn.commit()

    # ---- Tickets ----
    now = datetime.now()

    def ts(hours_ago):
        return (now - timedelta(hours=hours_ago)).strftime("%Y-%m-%d %H:%M:%S")

    tickets = [
        # (user_id, category, description, block, floor, room, status, created_hours_ago, resolved_hours_ago)
        (1, "Wi-Fi", "No Wi-Fi signal on 2nd floor since morning.", "KP-2", "2", "214", "Open", 60, None),
        (2, "Wi-Fi", "Wi-Fi extremely slow, can't attend online classes.", "KP-2", "2", "220", "Open", 55, None),
        (3, "AC", "AC not cooling, room feels humid.", "KP-1", "3", "310", "In Progress", 30, None),
        (4, "Water Purifier", "Water purifier on 1st floor not dispensing water.", "KP-3", "1", "N/A", "Open", 70, None),
        (5, "Sanitation", "Washroom on 1st floor needs urgent cleaning.", "KP-1", "1", "N/A", "Open", 10, None),
        (6, "Mess Food", "Food quality has dropped significantly this week.", "KP-2", None, None, "Open", 5, None),
        (7, "AC", "AC making loud noise at night.", "KP-3", "2", "205", "Resolved", 96, 4),
        (8, "Wi-Fi", "Router in common room not working.", "KP-1", "Ground", "N/A", "Resolved", 120, 12),
        (9, "Water Purifier", "Purifier filter needs replacement, water tastes odd.", "KP-2", "3", "N/A", "In Progress", 20, None),
        (10, "Sanitation", "Garbage not collected for 2 days.", "KP-3", "Ground", "N/A", "Open", 50, None),
        (1, "Mess Food", "Same menu repeated 3 days in a row.", "KP-2", None, None, "Open", 8, None),
        (3, "AC", "AC remote missing from common room.", "KP-1", "3", "N/A", "Open", 3, None),
        (5, "Wi-Fi", "Wi-Fi down in entire KP-1 block.", "KP-1", None, None, "Resolved", 150, 100),
        (2, "Sanitation", "Water leakage near washroom entrance.", "KP-2", "2", "N/A", "Open", 49, None),
        (9, "Water Purifier", "No cold water option working.", "KP-2", "3", "N/A", "Open", 15, None),
        (4, "AC", "AC filter dirty, causing bad smell.", "KP-3", "1", "108", "Open", 2, None),
        (7, "Mess Food", "Insects found in food yesterday.", "KP-3", None, None, "In Progress", 25, None),
        (10, "Wi-Fi", "Wi-Fi password not working after reset.", "KP-3", "Ground", "N/A", "Open", 1, None),
    ]

    ticket_ids = []
    for (uid, cat, desc, block, floor, room, status, hrs_ago, resolved_hrs_ago) in tickets:
        resolved_at = ts(resolved_hrs_ago) if resolved_hrs_ago is not None else None
        cur.execute(
            """INSERT INTO tickets
               (user_id, category, description, hostel_block, floor, room_no, status, created_at, resolved_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (uid, cat, desc, block, floor, room, status, ts(hrs_ago), resolved_at),
        )
        ticket_ids.append(cur.lastrowid)

    conn.commit()

    # ---- Votes (simulate shared-problem upvoting) ----
    import random
    random.seed(42)
    for tid in ticket_ids:
        voters = random.sample(range(1, 11), k=random.randint(0, 5))
        for uid in voters:
            try:
                cur.execute(
                    "INSERT INTO votes (ticket_id, user_id) VALUES (?,?)", (tid, uid)
                )
            except sqlite3.IntegrityError:
                pass

    conn.commit()
    conn.close()
    print(f"Seeded {len(students)} students, {len(wardens)} staff, {len(tickets)} tickets.")


if __name__ == "__main__":
    run()
