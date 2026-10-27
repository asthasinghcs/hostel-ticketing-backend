# Professor demonstration — HostelCare

Open https://hostel-ticketing-frontend-17du.onrender.com/ . These are synthetic project-demo accounts, not real student identities or functioning email inboxes. Passwords below are intentionally public test credentials.

## Quick logins

| Demonstration | Landing-page portal | Hostel to select | Email | Password |
| --- | --- | --- | --- | --- |
| KP student | Student | KP → KP-1 | 24054001@kiit.ac.in | `Demo!KP1.01a` |
| QC student | Student | QC → QC-1 | 24054026@kiit.ac.in | `Demo!QC1.26a` |
| Warden | Warden & admin | No hostel selection at login | hostelcare.demo.kp@gmail.com | `Demo!Staff.KP.42` |
| Administrator | Warden & admin | No hostel selection at login | hostelcare.demo.admin@gmail.com | `Demo!Admin.Campus.91` |

KP-1 student, QC-1 student, and warden logins were checked against the public API on 27 October 2026. The baseline was seven visible KP-1 tickets, two QC-1 tickets, and 60 tickets across all 36 hostels for the warden. Counts can grow as new reports are submitted.

## Five-minute walkthrough

1. Sign in as the KP-1 student. Show the KP-1 workspace and its grievances. This student can access only KP-1, enforced by the backend.
2. Sign out. Select Student → KP-2 and try the same KP-1 account. Login rejects the mismatched hostel. Choose KP-1 to sign in successfully.
3. Optionally raise a clearly labelled demonstration ticket. Show that Tickets raised and Open increase; a list filter does not change the hostel-wide total. The new ticket is a real saved demo record, so subsequent totals will include it.
4. Sign out and sign in as the QC-1 student. Show QC-1 grievances instead of KP-1 grievances.
5. Sign out and select Warden & admin. Sign in with the warden account. Show All hostels and the directory: 25 KP hostels and 11 QC hostels. Staff can manage every hostel.
6. For the fixed 40-report sample, enter From `2026-10-21` and To `2026-10-27`, then Apply dates. The original fixture contains 40 labelled demo grievances in that range. Future newly raised tickets can change this total.
7. Open Daily activity, select 26 October, and show its six original demo reports. Open a ticket's Discussion and Date-wise ticket history to show timestamped creation/status changes.
8. If demonstrating a status change, choose an Open ticket as the warden and set it to In Progress or Resolved. The change is saved and creates a dated history event.

The date fixture stays fixed; use explicit dates when presenting after October 2026. Last 7 days always follows the current date.

## What is in GitHub?

Both frontend and backend repositories contain this guide, `docs/PROJECT.md`, and `docs/DEMO_ACCOUNTS.md` (all 40 student logins and three staff logins). The backend also tracks the synthetic grievance fixture, a concrete dated sample, seed/migration code, schemas and tests. The application source is on main.

Live database files, backups, sessions and hosting connection passwords are excluded from Git. A fresh checkout needs a database and the documented seed command to recreate the synthetic sample; GitHub stores the fixture, not a live database.

## Hosting

The public website and backend run on Render. See `docs/PROJECT.md` for the currently verified database provider and deployment status. While the free-hosting migration is pending, the active Render database expires on 26 November 2026. Do not treat migration as complete until the live verification is recorded there. A free backend can take longer to respond after inactivity; open it before the presentation.
