"""Shared SQLite initialization; adds schema without dropping existing records."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def initialize_database(connection):
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
    for table in ("users", "tickets"):
        columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        if "demo_batch_id" not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN demo_batch_id TEXT")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON tickets(created_at)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_tickets_demo ON tickets(demo_batch_id)")
    # Existing creation dates are known; earlier status changes are not invented.
    connection.execute("""INSERT INTO ticket_events (ticket_id, actor_id, event_type, to_status, created_at)
        SELECT t.id, t.user_id, 'created', 'Open', t.created_at FROM tickets t
        WHERE NOT EXISTS (SELECT 1 FROM ticket_events e WHERE e.ticket_id=t.id AND e.event_type='created')""")
    connection.commit()
