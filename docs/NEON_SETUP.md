# Neon setup and verification — 27 October 2026

## Active hosting

- Website: https://hostel-ticketing-frontend-17du.onrender.com/
- API: https://hostel-ticketing-backend.onrender.com/
- Database: Neon project `polished-union-24877324` (SE project), organization `org-rough-paper-30136928`, branch `production` (`br-solitary-recipe-b5azjxug`), AWS Ohio, PostgreSQL 18.
- The project was verified as `free_v3`. Only PostgreSQL is used. The existing Flask authentication stays in place.
- Backend cutover deployment: `dep-dbgbhdm7bikc73fkebe0`, live at 2026-10-27 14:44:45 UTC (20:14:45 IST).
- The application no longer depends on the Render database that expires on 26 November. That original database is retained as the previous copy; it was not deleted.

## CLI setup

Commands ran in `C:/hostel-ticketing-backend`, which owns database access. The React frontend remains in its separate repository.

The requested `npm i -g neon@latest` failed with Windows EPERM. The first npx attempt also hit a cache permission error. A writable cache resolved the fallback:

```powershell
$env:npm_config_cache='C:/Users/KIIT/Documents/Codex/neon-cli-cache'
npx --yes neon@latest --version
# 8.13.0
```

The exact requested init attempted to reinstall coding-agent plugins and failed at that step. The already-installed skills were used; agent setup was skipped on retry:

```powershell
npx --yes neon@latest init -y --no-agent-setup --org-id org-rough-paper-30136928 --project-id polished-union-24877324 --branch production --services postgres
```

The first link was explicitly reported as offline/unverified. Browser authentication then timed out after 60 seconds. The project owner completed `npx --yes neon@latest login` in PowerShell. Retrying init verified the selected project, preserved neon.ts and pulled the environment. `neon config plan` reported no infrastructure changes.

```text
Linked .neon
  Project         SE project (polished-union-24877324)
  Branch          production
  Org             org-rough-paper-30136928
Pulled 3 Neon variables into .env.local
  Postgres        DATABASE_URL, DATABASE_URL_UNPOOLED
  Branch          NEON_BRANCH
```

Then the requested deploy completed:

```powershell
npx --yes neon@latest deploy
```

```text
Applying to branch production (br-solitary-recipe-b5azjxug)
No changes — branch production already matches the policy.
Utilized services: Postgres
Pulled 3 Neon variables into .env.local
```

## Code and private configuration

- `neon.ts` declares the PostgreSQL-only policy without overriding the selected production branch's existing compute settings.
- `package.json` and its lockfile contain Neon setup dependencies and backend build/start scripts. Python remains the API runtime.
- Flask loads `.env.local` then `.env` with deployment environment variables taking priority.
- Existing psycopg 3 remains the PostgreSQL driver. Requests use the pooled DATABASE_URL. Schema initialization uses DATABASE_URL_UNPOOLED when supplied.
- The two URLs are configured privately in the Render backend. No database credentials are sent to the browser.
- `.env`, `.env.local`, `.neon`, node_modules and database files are ignored by Git. Tests explicitly force SQLite so local Neon credentials cannot redirect the regression suite into production.

## Data migration

The Neon target was checked to be empty. Ticket writes on Render were paused and verified to return HTTP 503. Using the current Render database's private connection, the startup migration copied and checked every application record before committing. Sessions were excluded, so users sign in again.

Verified destination counts: 56 users, 60 tickets, 59 votes, 24 comments, one demo batch, and 84 ticket history events. Exported application rows match the migration's SHA-256 digest exactly. A PostgreSQL transaction exercised user/ticket/vote/comment/history writes and rolled back its probe records. Client-side TLS was confirmed using libpq's `ssl_in_use` flag.

After verification, Render's pooled/direct URLs were switched together, the temporary target URL was cleared, and READ_ONLY_MODE was set to 0. The resulting deployment became live. A validation request returned HTTP 400 rather than maintenance HTTP 503, confirming writes were re-enabled.

## Build and end-to-end proof

Backend:

```text
npm run build
> python -m py_compile app.py database.py postgres.py migrate_postgres.py
(exit 0)

python -m unittest -q
Ran 38 tests
OK
```

Frontend:

```text
npm run build
vite v8.3.0 building client environment for production...
32 modules transformed.
built in 170ms

npm test
# tests 14
# pass 14
# fail 0

npm run lint
> oxlint
(exit 0)
```

The application was started locally against the pulled Neon variables on port 5056. A frontend build pointing to that API was served with Vite preview on port 5174 (build passed again in 138ms). The browser completed KP-1 student login and displayed seven KP-1-only tickets.

Both local and public API checks passed: health, 36-hostel catalogue, demo sign-in, persisted session creation/revocation, QC-1-only content, HTTP 403 for a student's KP-1 request, staff access to all 36 hostels and 60 tickets, 40 demo reports across 21–27 October, six on 26 October, timestamped history, and CORS. The public warden login was checked in the browser after cutover.

The earlier installation/plugin/authentication failures were resolved by the npx fallback, skipping duplicate agent setup, and the owner's CLI login. No paid service was provisioned. Free-tier usage limits and idle wake-up delays still apply.

See [professor demonstration](PROFESSOR_DEMO.md) and [all demo accounts](DEMO_ACCOUNTS.md).
