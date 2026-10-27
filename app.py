"""HostelCare API. Run with gunicorn app:app or python app.py."""
import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

from flask import Flask, g, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import Forbidden, HTTPException, NotFound
from werkzeug.security import check_password_hash, generate_password_hash

ROOT = Path(__file__).resolve().parent
BLOCKS = ("KP-1", "KP-2", "KP-3")
CATEGORIES = ("Wi-Fi", "AC", "Water Purifier", "Sanitation", "Mess Food", "Other")
STATUSES = ("Open", "In Progress", "Resolved")
OVERDUE_HOURS = 48
SESSION_HOURS = 12


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def timestamp(value):
    return value.strftime("%Y-%m-%d %H:%M:%S")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"], timeout=15)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def init_db():
    """Add missing tables/indexes; never drop or reseed existing data."""
    db = get_db()
    db.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
    db.commit()


def public_user(row):
    return {key: row[key] for key in ("id", "name", "email", "role", "hostel_block")}


def new_session(user):
    token = secrets.token_urlsafe(32)
    expires = timestamp(utcnow() + timedelta(hours=SESSION_HOURS))
    db = get_db()
    db.execute("DELETE FROM sessions WHERE expires_at <= ?", (timestamp(utcnow()),))
    db.execute("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
               (hashlib.sha256(token.encode()).hexdigest(), user["id"], expires))
    db.commit()
    return {"user": public_user(user), "token": token, "expires_at": expires + "Z"}


def authenticated(*roles):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            token = header[7:] if header.startswith("Bearer ") else ""
            if not token or len(token) > 256:
                return jsonify(error="Please sign in."), 401
            g.token_hash = hashlib.sha256(token.encode()).hexdigest()
            g.user = get_db().execute(
                "SELECT u.* FROM users u JOIN sessions s ON u.id=s.user_id "
                "WHERE s.token_hash=? AND s.expires_at>?",
                (g.token_hash, timestamp(utcnow())),
            ).fetchone()
            if g.user is None:
                return jsonify(error="Your session has expired. Please sign in again."), 401
            if roles and g.user["role"] not in roles:
                return jsonify(error="You do not have permission for this action."), 403
            return fn(*args, **kwargs)
        return wrapped
    return decorate


def body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("A JSON object is required.")
    return data


def field(data, name, maximum, required=True):
    value = data.get(name, "")
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text.")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{name} is required.")
    if len(value) > maximum:
        raise ValueError(f"{name} must be at most {maximum} characters.")
    return value


def block_scope():
    block = request.args.get("hostel_block", "")
    if block and block not in BLOCKS:
        raise ValueError("Invalid hostel block.")
    if g.user["role"] == "student":
        if block and block != g.user["hostel_block"]:
            raise Forbidden("Students can only access their own hostel.")
        if g.user["hostel_block"] not in BLOCKS:
            raise Forbidden("A valid hostel must be assigned to this student.")
        return g.user["hostel_block"]
    return block


def accessible_ticket(ticket_id):
    row = get_db().execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if row is None:
        raise NotFound("Ticket not found.")
    if g.user["role"] == "student" and row["hostel_block"] != g.user["hostel_block"]:
        raise Forbidden("Students can only access their own hostel.")
    return row


def is_overdue(row):
    return row["status"] != "Resolved" and utcnow() - datetime.fromisoformat(row["created_at"]) > timedelta(hours=OVERDUE_HOURS)


def ticket_dict(row):
    result = dict(row)
    result["overdue"] = is_overdue(row)
    db = get_db()
    if "vote_count" not in row.keys():
        result["vote_count"] = db.execute("SELECT COUNT(*) FROM votes WHERE ticket_id=?", (row["id"],)).fetchone()[0]
        result["has_voted"] = db.execute("SELECT 1 FROM votes WHERE ticket_id=? AND user_id=?", (row["id"], g.user["id"])).fetchone() is not None
    else:
        result["has_voted"] = bool(row["has_voted"])
    return result


app = Flask(__name__)
app.config.update(DATABASE=os.environ.get("DATABASE_PATH", str(ROOT / "hostel_ticketing.db")), MAX_CONTENT_LENGTH=32 * 1024)
CORS(app, resources={r"/api/*": {"origins": [origin.strip() for origin in os.environ.get(
    "FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,https://hostel-ticketing-frontend-17du.onrender.com"
).split(",") if origin.strip()]}}, allow_headers=["Content-Type", "Authorization"])


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.errorhandler(ValueError)
def invalid_value(error):
    return jsonify(error=str(error)), 400


@app.errorhandler(HTTPException)
def http_error(error):
    return jsonify(error=error.description), error.code


@app.errorhandler(sqlite3.IntegrityError)
def integrity_error(_error):
    return jsonify(error="This change conflicts with existing data or contains invalid values."), 409


@app.errorhandler(Exception)
def unexpected_error(error):
    app.logger.exception("Unhandled API error", exc_info=error)
    return jsonify(error="The server could not complete the request. Please try again."), 500


@app.get("/api/health")
def health():
    get_db().execute("SELECT 1 FROM users LIMIT 1")
    return jsonify(status="ok")


@app.post("/api/signup")
def signup():
    data = body()
    if data.get("role", "student") != "student":
        return jsonify(error="Staff accounts must be created by an administrator using the server CLI."), 403
    name = field(data, "name", 100)
    email = field(data, "email", 254).lower()
    password = data.get("password")
    block = field(data, "hostel_block", 10)
    if email.count("@") != 1 or not all(email.split("@")) or any(c.isspace() for c in email):
        raise ValueError("Enter a valid email address.")
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        raise ValueError("Password must contain 8 to 128 characters.")
    if block not in BLOCKS:
        raise ValueError("Invalid hostel block.")
    db = get_db()
    if db.execute("SELECT 1 FROM users WHERE lower(email)=?", (email,)).fetchone():
        return jsonify(error="Email already registered."), 409
    cur = db.execute("INSERT INTO users (name,email,password,role,hostel_block) VALUES (?,?,?,'student',?)",
                     (name, email, generate_password_hash(password), block))
    db.commit()
    user = db.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
    return jsonify(new_session(user)), 201


@app.post("/api/login")
def login():
    data = body()
    email = field(data, "email", 254).lower()
    password = data.get("password")
    if not isinstance(password, str) or not 1 <= len(password) <= 128:
        raise ValueError("Enter your password (at most 128 characters).")
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE lower(email)=?", (email,)).fetchone()
    stored = user["password"] if user else ""
    legacy = len(stored) == 64 and all(char in "0123456789abcdef" for char in stored)
    valid = (hmac.compare_digest(stored, hashlib.sha256(password.encode()).hexdigest()) if legacy
             else check_password_hash(stored, password) if stored else False)
    if not valid:
        return jsonify(error="Invalid email or password."), 401
    portal = data.get("portal")
    if portal not in (None, "student", "staff"):
        raise ValueError("Invalid portal.")
    if portal == "student":
        if user["role"] != "student":
            return jsonify(error="Please use the staff portal for this account."), 403
        if data.get("hostel_block") != user["hostel_block"]:
            return jsonify(error="This account belongs to another hostel. Select your registered hostel."), 403
    if portal == "staff" and user["role"] not in ("warden", "admin"):
        return jsonify(error="This portal is for wardens and administrators."), 403
    if legacy:
        db.execute("UPDATE users SET password=? WHERE id=?", (generate_password_hash(password), user["id"]))
        db.commit()
    return jsonify(new_session(user))


@app.get("/api/me")
@authenticated()
def me():
    return jsonify(user=public_user(g.user))


@app.post("/api/logout")
@authenticated()
def logout():
    get_db().execute("DELETE FROM sessions WHERE token_hash=?", (g.token_hash,))
    get_db().commit()
    return jsonify(message="Signed out.")


def get_tickets():
    block = block_scope()
    status = request.args.get("status", "")
    sort = request.args.get("sort", "newest")
    if status and status not in STATUSES:
        raise ValueError("Invalid status.")
    if sort not in ("newest", "votes"):
        raise ValueError("Invalid sort order.")
    query = ("SELECT t.*, COUNT(v.id) AS vote_count, "
             "MAX(CASE WHEN v.user_id=? THEN 1 ELSE 0 END) AS has_voted "
             "FROM tickets t LEFT JOIN votes v ON v.ticket_id=t.id WHERE 1=1")
    params = [g.user["id"]]
    for key, value in (("hostel_block", block), ("status", status)):
        if value:
            query += f" AND t.{key}=?"
            params.append(value)
    rows = get_db().execute(query + " GROUP BY t.id ORDER BY t.created_at DESC, t.id DESC", params).fetchall()
    tickets = [ticket_dict(row) for row in rows]
    if sort == "votes":
        tickets.sort(key=lambda ticket: ticket["vote_count"], reverse=True)
    return tickets


@app.get("/api/tickets")
@authenticated()
def list_tickets():
    return jsonify(get_tickets())


@app.post("/api/tickets")
@authenticated("student")
def create_ticket():
    data = body()
    category = field(data, "category", 30)
    description = field(data, "description", 4000)
    block = field(data, "hostel_block", 10)
    floor = field(data, "floor", 30, required=False)
    room = field(data, "room_no", 30, required=False)
    if category not in CATEGORIES or block not in BLOCKS:
        raise ValueError("Invalid category or hostel block.")
    if block != g.user["hostel_block"]:
        return jsonify(error="Submit tickets for your assigned hostel block."), 403
    db = get_db()
    cur = db.execute("INSERT INTO tickets (user_id,category,description,hostel_block,floor,room_no) VALUES (?,?,?,?,?,?)",
                     (g.user["id"], category, description, block, floor or None, room or None))
    db.commit()
    return jsonify(ticket_dict(accessible_ticket(cur.lastrowid))), 201


@app.patch("/api/tickets/<int:ticket_id>/status")
@authenticated("admin", "warden")
def update_status(ticket_id):
    row = accessible_ticket(ticket_id)
    status = body().get("status")
    if status not in STATUSES:
        raise ValueError("Invalid status.")
    resolved_at = (row["resolved_at"] or timestamp(utcnow())) if status == "Resolved" else None
    db = get_db()
    db.execute("UPDATE tickets SET status=?, resolved_at=? WHERE id=?", (status, resolved_at, ticket_id))
    db.commit()
    return jsonify(ticket_dict(accessible_ticket(ticket_id)))


@app.post("/api/tickets/<int:ticket_id>/vote")
@authenticated("student")
def vote_ticket(ticket_id):
    row = accessible_ticket(ticket_id)
    body()  # Identity always comes from the session, never a submitted user_id.
    if row["hostel_block"] != g.user["hostel_block"]:
        return jsonify(error="You can upvote tickets in your assigned block."), 403
    if row["status"] == "Resolved":
        return jsonify(error="This ticket is already resolved."), 409
    db = get_db()
    try:
        db.execute("INSERT INTO votes (ticket_id,user_id) VALUES (?,?)", (ticket_id, g.user["id"]))
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return jsonify(error="You already voted on this ticket."), 409
    return jsonify(ticket_dict(accessible_ticket(ticket_id))), 201


@app.get("/api/tickets/<int:ticket_id>/comments")
@authenticated()
def list_comments(ticket_id):
    accessible_ticket(ticket_id)
    rows = get_db().execute(
        "SELECT c.id,c.ticket_id,c.text,c.created_at,u.name AS author_name,u.role AS author_role "
        "FROM comments c JOIN users u ON c.user_id=u.id WHERE c.ticket_id=? ORDER BY c.created_at,c.id",
        (ticket_id,),
    ).fetchall()
    return jsonify([dict(row) for row in rows])


@app.post("/api/tickets/<int:ticket_id>/comments")
@authenticated()
def add_comment(ticket_id):
    row = accessible_ticket(ticket_id)
    if g.user["role"] == "student" and row["hostel_block"] != g.user["hostel_block"]:
        return jsonify(error="You can comment on tickets in your assigned block."), 403
    text = field(body(), "text", 2000)
    db = get_db()
    cur = db.execute("INSERT INTO comments (ticket_id,user_id,text) VALUES (?,?,?)", (ticket_id, g.user["id"], text))
    db.commit()
    return jsonify(id=cur.lastrowid, ticket_id=ticket_id, text=text,
                   author_name=g.user["name"], author_role=g.user["role"],
                   created_at=db.execute("SELECT created_at FROM comments WHERE id=?", (cur.lastrowid,)).fetchone()[0]), 201


def get_stats():
    block = block_scope()
    rows = get_db().execute("SELECT * FROM tickets" + (" WHERE hostel_block=?" if block else ""),
                            (block,) if block else ()).fetchall()
    counts = {"total": len(rows), "open": 0, "in_progress": 0, "resolved": 0, "overdue": 0}
    for row in rows:
        counts[row["status"].lower().replace(" ", "_")] += 1
        counts["overdue"] += int(is_overdue(row))
    counts["my_total"] = sum(1 for row in rows if row["user_id"] == g.user["id"])
    return counts


@app.get("/api/stats")
@authenticated()
def stats():
    return jsonify(get_stats())


@app.get("/api/overview")
@authenticated()
def overview():
    # One SQLite read snapshot keeps the list and its counters consistent.
    db = get_db()
    db.execute("BEGIN")
    return jsonify(tickets=get_tickets(), stats=get_stats(), updated_at=timestamp(utcnow()) + "Z")


@app.after_request
def prevent_api_caching(response):
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
