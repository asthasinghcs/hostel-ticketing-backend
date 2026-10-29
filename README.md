# HostelCare API

**The Flask backend for the [live HostelCare grievance portal](https://hostelgrievance.onrender.com/).** It stores tickets, comments, votes, sessions, and dated history, and enforces student hostel boundaries on the server.

### [Open the live application →](https://hostelgrievance.onrender.com/)

[API health](https://hostel-ticketing-backend.onrender.com/api/health) · [Frontend repository](https://github.com/asthasinghcs/hostel-ticketing-frontend) · [SRS](docs/HostelCare_SRS.pdf) · [Professor demo guide](docs/PROFESSOR_DEMO.md)

## What it provides

| Area | Behaviour |
| --- | --- |
| Accounts | Student signup accepts a 6–12 digit roll number at `@kiit.ac.in`. Staff accounts are created through a trusted command-line tool. |
| Access | Students see and act within their stored hostel; wardens and admins manage all 36 configured KP/QC hostels. |
| Tickets | Create, list, search by date and hostel, change status as staff, and read dated event history. |
| Participation | One vote per student per unresolved ticket; authorized comments and discussion. |
| Reporting | A consistent overview returns tickets and status totals together, including daily activity and overdue indicators. |
| Storage | Neon PostgreSQL in the hosted deployment; SQLite when no database URL is configured locally. |

The [deployed frontend](https://hostelgrievance.onrender.com/) presents these workflows. For a quick demonstration, sign in as `24054001@kiit.ac.in` / `Demo!KP1.01a` with **Student → KP → KP-1**, or as `hostelcare.demo.kp@gmail.com` / `Demo!Staff.KP.42` under **Warden & admin**. These are fictional public test accounts. The [demo guide](docs/PROFESSOR_DEMO.md) includes the QC-1 account and a five-minute walkthrough.

## System design

```text
Browser (React + Vite)
        │ HTTPS / JSON
        ▼
Render (Flask API) ──► Neon PostgreSQL
        │
        └─► temporary SQLite databases for local tests
```

Protected endpoints derive identity from an opaque bearer session, never a submitted user ID. Passwords and session tokens are stored as hashes. Database credentials stay on the server. The live app uses the `DATABASE_URL` connection and a direct connection for initialization; existing records survive restarts and redeployments.

## Run locally

Requires Python 3.10+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

The API runs at `http://localhost:5000`. Without `DATABASE_URL`, it creates or opens `hostel_ticketing.db` locally. Set `FRONTEND_ORIGINS` to the comma-separated browser origins allowed to call the API. The deployed Neon connection string belongs in a private backend environment variable; never commit it.

To create a staff account locally:

```powershell
python manage.py create-staff --name "KP Warden" --email warden@example.edu --role warden --block KP-1
```

The command prompts privately for a password. Public signup creates student accounts only. For demo fixtures and append-safe import instructions, see [demo accounts](docs/DEMO_ACCOUNTS.md).

## API at a glance

| Resource | Purpose |
| --- | --- |
| `GET /api/health`, `GET /api/hostels` | Storage health and configured hostel catalogue. |
| `POST /api/signup`, `POST /api/login`, `GET /api/me`, `POST /api/logout` | Account and session flows. |
| `GET /api/overview`, `GET /api/tickets`, `POST /api/tickets` | Consistent reporting and ticket submission. |
| `PATCH /api/tickets/{id}/status` | Staff status transitions. |
| `POST /api/tickets/{id}/vote`, `GET/POST /api/tickets/{id}/comments` | Participation and discussion. |
| `GET /api/tickets/{id}/history`, `GET /api/stats` | Dated event history and counts. |

See the [project guide](docs/PROJECT.md) and [SRS](docs/SRS.md) for complete contracts and authorization rules.

## Checks and evidence

```powershell
python -m unittest -v
python docs/validation/check_srs_validation.py
```

The recorded baseline passed **38 backend regression tests**, **14 frontend tests**, and **40 API boundary checks**. Tests use disposable SQLite databases, while separate hosted checks verified Neon persistence, student isolation, staff scope, date counts, and CORS. [Review the validation report and raw results](docs/validation/README.md). The SRS states the limits of performance, accessibility, and security validation.

## Project documents

| Document | Contents |
| --- | --- |
| [SRS (PDF)](docs/HostelCare_SRS.pdf) · [Word](docs/HostelCare_SRS.docx) · [source](docs/SRS.md) | Requirements, UI, database model, interfaces, testing, and traceability. |
| [Professor demo](docs/PROFESSOR_DEMO.md) | Working demo logins and presentation sequence. |
| [Neon deployment](docs/NEON_SETUP.md) | Hosted storage configuration and migration evidence. |
| [Project guide](docs/PROJECT.md) | Detailed architecture, setup, API, deployment, and operations. |
