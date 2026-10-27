# HostelCare — Backend

Flask + PostgreSQL/SQLite API for hostel grievances, voting, discussions, sessions, and staff management.

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

Thirty-seven tests run against temporary databases. They cover session handling, role boundaries, identity spoofing, ticket/vote/comment behavior, validation, overdue rules, migration safety, and CORS.

## Deployment

Use gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 on Linux, persistent storage for DATABASE_PATH, and the deployed frontend origin in FRONTEND_ORIGINS. Deploy the matching frontend because authentication response contracts changed.

See [the complete project guide](docs/PROJECT.md) for API payloads, migration details, role permissions, storage, deployment steps, and validation results. The previously committed database is excluded from source tracking; the local database file is retained.

## Hostels, recent demo data, and dates

The app supports 36 configured hostels: KP-1–KP-25 and QC-1–QC-11. New student accounts use rollnumber@kiit.ac.in. Today, Last 7 days, From/To filters, daily totals, and ticket history use India time.

[Demo accounts and import instructions](docs/DEMO_ACCOUNTS.md) lists all 40 synthetic student logins and three staff logins. The backend fixture is appended once with `python seed.py --append-demo` after setting DATABASE_PATH; it preserves existing records and detects repeats. The concrete local sample increased the ticket total from 20 to 60.

## Render storage

Set DATABASE_URL to the internal managed PostgreSQL URL in the backend environment. SQLite remains the local default. See [deployment and private migration instructions](docs/PROJECT.md#render-deployment). The selected free database expires on 26 November 2026; export or move it before then.
