# Hostel Grievance & Maintenance Ticketing — Backend

## Setup
```
pip install flask flask-cors
python seed.py      # creates + populates hostel_ticketing.db (run once)
python app.py        # starts server on http://localhost:5000
```

## Sample logins (all seeded with password "password123" for students, "adminpass" for staff)
- Student: astha@kiit.ac.in / password123
- Admin:   admin@kiit.ac.in / adminpass

## API Endpoints
- POST   /api/signup                     — create account
- POST   /api/login                      — returns user info
- GET    /api/tickets?hostel_block=&status=&sort=votes|newest
- POST   /api/tickets                    — create ticket {user_id, category, description, hostel_block, floor, room_no}
- PATCH  /api/tickets/<id>/status        — update status {status: "Open"|"In Progress"|"Resolved"}
- POST   /api/tickets/<id>/vote          — upvote {user_id}
- GET    /api/stats                      — dashboard counts (total/open/in_progress/resolved/overdue)

Tickets open past 48 hours (and not Resolved) are automatically flagged `"overdue": true` in every response.
