# SRS validation evidence

The 14-page Software Requirements Specification includes the scope, 34 functional requirements, eight quality requirements, user roles, use cases and ticket states, UI requirements, ER model and schema, API interfaces, validation parameters, testing report, acceptance criteria and traceability.

## Recorded release checks

Execution baseline: 27 October 2026. Documentation finalized: 28 October 2026.

- Backend source: `dac96d4a0f31b980b34cec3665c51b65090836f6`.
- Frontend source: `a2174a626af9179e2962722d5fc0f23c88846eab`.

```text
Backend: python -m unittest -v
Ran 38 tests in 43.983s
OK

Frontend: npm test
# tests 14
# pass 14
# fail 0

Frontend: npm run lint
Exit code: 0

Frontend: npm run build
32 modules transformed
built in 245ms

Boundary API harness
40/40 checks passed
```

Backend regression tests use isolated temporary SQLite databases. Frontend tests exercise filters, dates, session handling and request behavior. The additional 40 boundary checks use Flask's test client with a disposable SQLite database; expected and actual HTTP results appear in [SRS_Validation_Results.json](SRS_Validation_Results.json). These are separate sets of checks, not a claim of 92 unit tests or a coverage percentage.

## Reproduce the boundary checks

Install backend requirements, then run in the backend repository root:

```powershell
python docs/validation/check_srs_validation.py
```

The script clears both database URL variables before importing the app and uses a temporary database. It never uses live Neon storage. Optional variables: `HOSTEL_BACKEND_ROOT` identifies the backend checkout; `HOSTEL_TEST_TMP` selects a writable temporary parent; `SRS_REPORT_PATH` selects the result JSON. The frontend copy requires `HOSTEL_BACKEND_ROOT` to point to the backend checkout.

## Hosted evidence

- [Hosted API results](live-verification.json): 36 hostels; 60 tickets for staff; QC-1 student sees two tickets; requesting KP-1 returns 403; 40 demo tickets across 21-27 October; six tickets on 26 October; authenticated history and CORS passed.
- [Neon storage verification](neon-storage-verification.json): 56 users, 60 tickets, 59 votes, 24 comments, one demo batch and 84 events preserved; import digest matched; transactional write probe rolled back; database TLS confirmed.
- Primary UI: https://hostelgrievance.onrender.com/.

The original live checks used the recorded baseline. Fixed October date windows should be used when reproducing demo counts after October. Live totals may change if users add records.

## Document checks and limits

The final PDF has 14 pages, including cover and contents. Every page was rasterized and visually reviewed for readable diagrams, tables, consistent numbering and overflow. PDF layout was produced by a controlled OOXML-to-PDF renderer from the final Word document; native Office export was unavailable in this environment. The PDF is the checked submission copy. The Word file is editable and pagination may vary by editor.

No controlled load test, complete device/browser matrix, penetration test, full WCAG audit, coverage percentage or timed restore test is claimed. Proposed performance and compatibility targets are labeled as pending in the SRS. Demo identities are fictional test accounts; email syntax validation does not verify mailbox ownership or residence.
