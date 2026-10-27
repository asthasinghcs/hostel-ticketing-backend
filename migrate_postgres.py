"""One-time, private SQLite snapshot transfer into an empty PostgreSQL database.

Export locally; provide the compressed payload as DATABASE_IMPORT_B64 on Render.
No sessions are exported. Never commit the payload or expose it in HTTP routes.
"""
import argparse
from contextlib import closing
import base64
import hashlib
import json
from pathlib import Path
import sqlite3
import zlib

TABLES = ('users', 'tickets', 'votes', 'comments', 'demo_batches', 'ticket_events')


def export_snapshot(path):
    with closing(sqlite3.connect(f'file:{Path(path).resolve().as_posix()}?mode=ro', uri=True)) as source:
        source.row_factory = sqlite3.Row
        source.execute('BEGIN')
        if source.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Source database contains invalid foreign keys.')
        tables = {table: [dict(row) for row in source.execute(f'SELECT * FROM {table} ORDER BY id')]
                  for table in TABLES}
    payload = json.dumps({'version': 1, 'tables': tables}, sort_keys=True, separators=(',', ':')).encode()
    return base64.b64encode(zlib.compress(payload)).decode()


def import_snapshot(db, encoded):
    if getattr(db, 'dialect', '') != 'postgres':
        raise ValueError('Snapshot import requires PostgreSQL.')
    payload = zlib.decompress(base64.b64decode(encoded, validate=True))
    snapshot = json.loads(payload)
    if snapshot.get('version') != 1 or set(snapshot['tables']) != set(TABLES):
        raise ValueError('Unsupported database snapshot.')
    digest = hashlib.sha256(payload).hexdigest()
    db.execute('BEGIN IMMEDIATE')
    try:
        db.execute('SELECT pg_advisory_xact_lock(78043218)')
        db.execute('CREATE TABLE IF NOT EXISTS migration_imports (digest TEXT PRIMARY KEY, imported_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP)')
        if db.execute('SELECT 1 FROM migration_imports WHERE digest=?', (digest,)).fetchone():
            db.commit()
            return False
        if any(db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in (*TABLES, 'sessions')):
            raise ValueError('Refusing to import into a nonempty database.')
        for table in TABLES:
            rows = snapshot['tables'][table]
            allowed = {row['column_name'] for row in db.execute(
                'SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=?', (table,))}
            for row in rows:
                if not set(row).issubset(allowed):
                    raise ValueError('Snapshot has unknown columns.')
                columns = list(row)
                db.execute(f'INSERT INTO {table} ({",".join(columns)}) VALUES ({",".join("?" for _ in columns)})', tuple(row.values()))
            actual = [dict(row) for row in db.execute(f'SELECT * FROM {table} ORDER BY id')]
            if actual != rows:
                raise ValueError(f'Migration verification failed for {table}.')
            if table in db.identity_tables:
                maximum = max((row['id'] for row in rows), default=0)
                db.execute('SELECT setval(pg_get_serial_sequence(?, ?), ?, ?)', (table, 'id', max(maximum, 1), maximum > 0))
        db.execute('INSERT INTO migration_imports (digest) VALUES (?)', (digest,))
        verify_storage(db)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise



def verify_storage(db):
    """Exercise PostgreSQL IDs, relationships, reads and rollback before release."""
    db.execute('SAVEPOINT storage_probe')
    try:
        uid = db.execute("INSERT INTO users(name,email,password,role,hostel_block) VALUES(?,?,?,'student','KP-1')",
                         ('Storage probe', 'storage-probe@invalid.test', 'unused')).lastrowid
        tid = db.execute("INSERT INTO tickets(user_id,category,description,hostel_block) VALUES(?,'Wi-Fi','Storage verification','KP-1')", (uid,)).lastrowid
        db.execute("INSERT INTO votes(ticket_id,user_id) VALUES(?,?)", (tid,uid))
        db.execute("INSERT INTO comments(ticket_id,user_id,text) VALUES(?,?,'Storage verification')", (tid,uid))
        db.execute("INSERT INTO ticket_events(ticket_id,actor_id,event_type,to_status) VALUES(?,?,'created','Open')", (tid,uid))
        row = db.execute("SELECT t.*, owner.name, COUNT(v.id) AS votes FROM tickets t JOIN users owner ON owner.id=t.user_id LEFT JOIN votes v ON v.ticket_id=t.id WHERE t.id=? GROUP BY t.id,owner.name", (tid,)).fetchone()
        if row['votes'] != 1 or row['user_id'] != uid:
            raise ValueError('PostgreSQL storage verification failed.')
    finally:
        db.execute('ROLLBACK TO SAVEPOINT storage_probe')
        db.execute('RELEASE SAVEPOINT storage_probe')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', help='Existing SQLite database')
    parser.add_argument('output', help='Private local output file; never commit it')
    args = parser.parse_args()
    output = Path(args.output)
    with output.open('x', encoding='utf-8') as stream:
        stream.write(export_snapshot(args.source))
    print('Private snapshot exported; account sessions were excluded.')


if __name__ == '__main__':
    main()
