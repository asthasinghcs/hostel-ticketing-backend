"""
Transparent Hostel Grievance & Maintenance Ticketing System
Backend API (Flask + SQLite)

Run:
    pip install flask flask-cors
    python3 seed.py        # first time only, creates + populates DB
    python3 app.py         # starts server on http://localhost:5000
"""
import sqlite3
import hashlib
from datetime import datetime
from flask import Flask, request, jsonify, g
from flask_cors import CORS
import os

DB_PATH = "hostel_ticketing.db"
OVERDUE_HOURS = 48

app = Flask(__name__)
CORS(app)  # allow the frontend (different origin/port) to call this API


# ---------- DB helpers ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def is_overdue(ticket_row):
    if ticket_row["status"] == "Resolved":
        return False
    created = datetime.strptime(ticket_row["created_at"], "%Y-%m-%d %H:%M:%S")
    age_hours = (datetime.now() - created).total_seconds() / 3600
    return age_hours > OVERDUE_HOURS


def ticket_to_dict(row, vote_count=0):
    d = dict(row)
    d["vote_count"] = vote_count
    d["overdue"] = is_overdue(row)
    return d


# ---------- Auth (simple, no JWT — fine for a course project) ----------
@app.route("/api/signup", methods=["POST"])
def signup():
    data = request.get_json()
    required = ["name", "email", "password", "role"]
    if not all(k in data and data[k] for k in required):
        return jsonify({"error": "Missing required fields"}), 400

    db = get_db()
    try:
        db.execute(
            "INSERT INTO users (name, email, password, role, hostel_block) VALUES (?,?,?,?,?)",
            (data["name"], data["email"], hash_pw(data["password"]),
             data["role"], data.get("hostel_block")),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Email already registered"}), 409

    return jsonify({"message": "Signup successful"}), 201


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE email = ? AND password = ?",
        (data.get("email"), hash_pw(data.get("password", ""))),
    ).fetchone()

    if not user:
        return jsonify({"error": "Invalid email or password"}), 401

    return jsonify({
        "id": user["id"], "name": user["name"], "email": user["email"],
        "role": user["role"], "hostel_block": user["hostel_block"],
    })


# ---------- Tickets ----------
@app.route("/api/tickets", methods=["GET"])
def list_tickets():
    """
    Query params (all optional):
      hostel_block=KP-2   -> filter by block
      status=Open         -> filter by status
      sort=votes|newest   -> sort order (default newest)
    """
    db = get_db()
    query = "SELECT * FROM tickets WHERE 1=1"
    params = []

    block = request.args.get("hostel_block")
    if block:
        query += " AND hostel_block = ?"
        params.append(block)

    status = request.args.get("status")
    if status:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY created_at DESC"
    rows = db.execute(query, params).fetchall()

    result = []
    for row in rows:
        vote_count = db.execute(
            "SELECT COUNT(*) as c FROM votes WHERE ticket_id = ?", (row["id"],)
        ).fetchone()["c"]
        result.append(ticket_to_dict(row, vote_count))

    sort = request.args.get("sort", "newest")
    if sort == "votes":
        result.sort(key=lambda t: t["vote_count"], reverse=True)

    return jsonify(result)


@app.route("/api/tickets", methods=["POST"])
def create_ticket():
    data = request.get_json()
    required = ["user_id", "category", "description", "hostel_block"]
    if not all(k in data and data[k] for k in required):
        return jsonify({"error": "Missing required fields"}), 400

    db = get_db()
    cur = db.execute(
        """INSERT INTO tickets (user_id, category, description, hostel_block, floor, room_no)
           VALUES (?,?,?,?,?,?)""",
        (data["user_id"], data["category"], data["description"], data["hostel_block"],
         data.get("floor"), data.get("room_no")),
    )
    db.commit()
    new_row = db.execute("SELECT * FROM tickets WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(ticket_to_dict(new_row, 0)), 201


@app.route("/api/tickets/<int:ticket_id>/status", methods=["PATCH"])
def update_status(ticket_id):
    data = request.get_json()
    new_status = data.get("status")
    if new_status not in ("Open", "In Progress", "Resolved"):
        return jsonify({"error": "Invalid status"}), 400

    db = get_db()
    resolved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if new_status == "Resolved" else None
    db.execute(
        "UPDATE tickets SET status = ?, resolved_at = ? WHERE id = ?",
        (new_status, resolved_at, ticket_id),
    )
    db.commit()
    row = db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not row:
        return jsonify({"error": "Ticket not found"}), 404
    vote_count = db.execute(
        "SELECT COUNT(*) as c FROM votes WHERE ticket_id = ?", (ticket_id,)
    ).fetchone()["c"]
    return jsonify(ticket_to_dict(row, vote_count))


# ---------- Votes ----------
@app.route("/api/tickets/<int:ticket_id>/vote", methods=["POST"])
def vote_ticket(ticket_id):
    data = request.get_json()
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    db = get_db()
    try:
        db.execute(
            "INSERT INTO votes (ticket_id, user_id) VALUES (?,?)", (ticket_id, user_id)
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "You already voted on this ticket"}), 409

    vote_count = db.execute(
        "SELECT COUNT(*) as c FROM votes WHERE ticket_id = ?", (ticket_id,)
    ).fetchone()["c"]
    return jsonify({"ticket_id": ticket_id, "vote_count": vote_count}), 201


# ---------- Stats (handy for admin dashboard header) ----------
@app.route("/api/stats", methods=["GET"])
def stats():
    db = get_db()
    total = db.execute("SELECT COUNT(*) c FROM tickets").fetchone()["c"]
    open_count = db.execute("SELECT COUNT(*) c FROM tickets WHERE status='Open'").fetchone()["c"]
    in_progress = db.execute("SELECT COUNT(*) c FROM tickets WHERE status='In Progress'").fetchone()["c"]
    resolved = db.execute("SELECT COUNT(*) c FROM tickets WHERE status='Resolved'").fetchone()["c"]

    all_open = db.execute("SELECT * FROM tickets WHERE status != 'Resolved'").fetchall()
    overdue = sum(1 for t in all_open if is_overdue(t))

    return jsonify({
        "total": total, "open": open_count, "in_progress": in_progress,
        "resolved": resolved, "overdue": overdue,
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True
    )
