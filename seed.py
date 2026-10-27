"""Load the explicitly synthetic 40-grievance demo safely and reproducibly."""
import argparse
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3

from werkzeug.security import generate_password_hash
from database import initialize_database

ROOT = Path(__file__).resolve().parent
CAMPUS_TZ = timezone(timedelta(hours=5, minutes=30))
FIXTURE_PATH = ROOT / 'demo' / 'grievances.json'


def timestamp(value):
    return value.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


def load_fixture():
    return json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))


def seed_demo(database_path, *, append=False, as_of=None):
    fixture = load_fixture()
    anchor = as_of or datetime.now(timezone.utc)
    if anchor.tzinfo is None:
        raise ValueError('The seed anchor must include a timezone.')
    anchor = anchor.astimezone(timezone.utc).replace(microsecond=0)
    campus_now = anchor.astimezone(CAMPUS_TZ)
    oldest = datetime.combine(campus_now.date() - timedelta(days=6), datetime.min.time(), CAMPUS_TZ)
    window_minutes = max(1, int((anchor - oldest).total_seconds() / 60))
    with closing(sqlite3.connect(database_path, timeout=30)) as db:
        db.row_factory = sqlite3.Row
        initialize_database(db)
        db.execute('BEGIN IMMEDIATE')
        existing = db.execute('SELECT * FROM demo_batches WHERE id=?', (fixture['batch_id'],)).fetchone()
        if existing:
            actual = db.execute('SELECT COUNT(*) FROM tickets WHERE demo_batch_id=?', (fixture['batch_id'],)).fetchone()[0]
            if actual != existing['ticket_count']:
                raise ValueError('The demo batch is incomplete; restore or inspect the database before seeding.')
            return {'already_applied':True, 'batch_id':existing['id'], 'ticket_count':actual, 'anchor_at':existing['anchor_at']}
        if not append and (db.execute('SELECT COUNT(*) FROM users').fetchone()[0] or db.execute('SELECT COUNT(*) FROM tickets').fetchone()[0]):
            raise ValueError('Refusing to seed a populated database. Use --append-demo to add the labelled synthetic batch without replacing records.')
        accounts = fixture['students'] + fixture['staff']
        for account in accounts:
            if db.execute('SELECT 1 FROM users WHERE lower(email)=?', (account['email'].lower(),)).fetchone():
                raise ValueError(f"Demo email already exists; no accounts were changed: {account['email']}")
        ids = {}
        for account in accounts:
            cur = db.execute('INSERT INTO users(name,email,password,role,hostel_block,created_at,demo_batch_id) VALUES(?,?,?,?,?,?,?)',
                (account['name'], account['email'], generate_password_hash(account['password']), account.get('role','student'), account.get('hostel_block'), timestamp(anchor - timedelta(days=8)), fixture['batch_id']))
            ids[account['email']] = cur.lastrowid
        staff = {account['email']:ids[account['email']] for account in fixture['staff']}
        for account in fixture['students']:
            ticket = account['ticket']
            age = max(1, int(window_minutes * ticket['age_weight'] / 10000))
            created = anchor - timedelta(minutes=age)
            progress_at = created + timedelta(seconds=max(1, age * 60 // 3))
            resolved_at = created + timedelta(seconds=max(2, age * 60 * 2 // 3)) if ticket['status']=='Resolved' else None
            uid = ids[account['email']]
            cur = db.execute('INSERT INTO tickets(user_id,category,description,hostel_block,floor,room_no,status,created_at,resolved_at,demo_batch_id) VALUES(?,?,?,?,?,?,?,?,?,?)',
                (uid,ticket['category'],ticket['description'],account['hostel_block'],ticket['floor'],ticket['room_no'],ticket['status'],timestamp(created),timestamp(resolved_at) if resolved_at else None,fixture['batch_id']))
            tid = cur.lastrowid
            db.execute("INSERT INTO ticket_events(ticket_id,actor_id,event_type,to_status,created_at) VALUES(?,?,'created','Open',?)", (tid,uid,timestamp(created)))
            warden_id = staff['hostelcare.demo.kp@gmail.com' if account['hostel_block'].startswith('KP-') else 'hostelcare.demo.qc@gmail.com']
            if ticket['status'] != 'Open':
                db.execute("INSERT INTO ticket_events(ticket_id,actor_id,event_type,from_status,to_status,created_at) VALUES(?,?,'status_changed','Open','In Progress',?)", (tid,warden_id,timestamp(progress_at)))
                db.execute('INSERT INTO comments(ticket_id,user_id,text,created_at) VALUES(?,?,?,?)', (tid,warden_id,'Demo update: the maintenance team has inspected this issue and scheduled the next repair visit.',timestamp(progress_at)))
            if resolved_at:
                db.execute("INSERT INTO ticket_events(ticket_id,actor_id,event_type,from_status,to_status,created_at) VALUES(?,?,'status_changed','In Progress','Resolved',?)", (tid,warden_id,timestamp(resolved_at)))
                db.execute('INSERT INTO comments(ticket_id,user_id,text,created_at) VALUES(?,?,?,?)', (tid,warden_id,'Demo update: the reported fault was repaired and the facility was checked before closing this ticket.',timestamp(resolved_at)))
            # Only synthetic residents of the same hostel can support a synthetic ticket.
            peers = [other for other in fixture['students'] if other['hostel_block']==account['hostel_block'] and other['email']!=account['email']]
            for peer in peers:
                db.execute('INSERT INTO votes(ticket_id,user_id,created_at) VALUES(?,?,?)', (tid,ids[peer['email']],timestamp(created + timedelta(seconds=30))))
        db.execute('INSERT INTO demo_batches(id,created_at,anchor_at,ticket_count) VALUES(?,?,?,?)', (fixture['batch_id'],timestamp(datetime.now(timezone.utc)),timestamp(anchor),len(fixture['students'])))
        db.commit()
    return {'already_applied':False,'batch_id':fixture['batch_id'],'ticket_count':len(fixture['students']),'student_count':len(fixture['students']),'staff_count':len(fixture['staff']),'anchor_at':timestamp(anchor),'date_from':oldest.date().isoformat(),'date_to':campus_now.date().isoformat()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--append-demo', action='store_true', help='Append the labelled demo batch to an existing database, without replacing users or tickets')
    parser.add_argument('--as-of', help='Optional timezone-aware ISO-8601 anchor for reproducible demo dates')
    args = parser.parse_args()
    database_path = os.environ.get('DATABASE_PATH', str(ROOT / 'hostel_ticketing.db'))
    try:
        anchor = datetime.fromisoformat(args.as_of.replace('Z','+00:00')) if args.as_of else None
        result = seed_demo(database_path, append=args.append_demo, as_of=anchor)
    except (ValueError, sqlite3.Error) as error:
        raise SystemExit(str(error)) from None
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
