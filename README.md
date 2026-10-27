# HostelCare — Backend

Flask + SQLite API for hostel grievances, voting, discussions, sessions, and staff management.

## Run locally

Use Python 3.10+ (verified with Python 3.12.10).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

The API listens on http://localhost:5000. Missing tables/indexes initialize automatically; existing data is retained. DATABASE_PATH defaults to hostel_ticketing.db beside app.py. Set FRONTEND_ORIGINS to comma-separated exact allowed frontend origins.

Do not run seed.py against production data. To try sample accounts, point DATABASE_PATH at a separate empty demo database, then run python seed.py.

## Staff accounts

```powershell
python manage.py create-staff --name "Hostel Administrator" --email admin@example.edu --role admin
python manage.py create-staff --name "KP-1 Warden" --email warden@example.edu --role warden --block KP-1
```

Passwords are entered privately through prompts. Public signup can create students only.

## Tests

```powershell
python -m unittest -v
```

Twenty-four tests run against temporary databases. They cover session handling, role boundaries, identity spoofing, ticket/vote/comment behavior, validation, overdue rules, migration safety, and CORS.

## Deployment

Use gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 on Linux, persistent storage for DATABASE_PATH, and the deployed frontend origin in FRONTEND_ORIGINS. Deploy the matching frontend because authentication response contracts changed.

See [the complete project guide](docs/PROJECT.md) for API payloads, migration details, role permissions, storage, deployment steps, and validation results. The previously committed database is excluded from source tracking; the local database file is retained.
