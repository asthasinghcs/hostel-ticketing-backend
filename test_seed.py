"""The demo fixture is fictional, append-only, idempotent, and date-consistent."""
from datetime import datetime, timedelta, timezone
import os
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from database import initialize_database
from seed import seed_demo, load_fixture, CAMPUS_TZ
from werkzeug.security import check_password_hash


class DemoSeedTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=os.environ.get('HOSTEL_TEST_TMP'))
        self.path=str(Path(self.tmp.name)/'demo.db')
        self.anchor=datetime(2026,10,27,8,30,tzinfo=timezone.utc)

    def tearDown(self):
        self.tmp.cleanup()

    def test_fixture_has_forty_unique_students_passwords_and_every_hostel(self):
        fixture=load_fixture()
        self.assertTrue(fixture['synthetic'])
        self.assertEqual(len(fixture['students']),40)
        self.assertEqual(len({student['email'] for student in fixture['students']}),40)
        self.assertEqual(len({student['password'] for student in fixture['students']}),40)
        self.assertEqual(len({student['hostel_block'] for student in fixture['students']}),36)
        for student in fixture['students']:
            self.assertRegex(student['email'],r'^[0-9]{6,12}@kiit\.ac\.in$')

    def test_seed_counts_hashes_dates_history_and_repeat_safety(self):
        result=seed_demo(self.path,as_of=self.anchor)
        self.assertEqual(result['ticket_count'],40)
        self.assertEqual(result['date_from'],'2026-10-21')
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0],43)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM tickets').fetchone()[0],40)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM ticket_events').fetchone()[0],64)
            self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
            original=db.execute('SELECT id,created_at,resolved_at FROM tickets ORDER BY id').fetchall()
            for _id,created,resolved in original:
                date=datetime.fromisoformat(created).replace(tzinfo=timezone.utc)
                self.assertLessEqual(date,self.anchor)
                self.assertGreaterEqual(date.astimezone(CAMPUS_TZ).date(),self.anchor.astimezone(CAMPUS_TZ).date()-timedelta(days=6))
                if resolved:
                    self.assertLessEqual(datetime.fromisoformat(resolved).replace(tzinfo=timezone.utc),self.anchor)
                    self.assertGreaterEqual(resolved,created)
            account=load_fixture()['students'][0]
            stored=db.execute('SELECT password FROM users WHERE email=?',(account['email'],)).fetchone()[0]
            self.assertNotEqual(stored,account['password'])
            self.assertTrue(check_password_hash(stored,account['password']))
        again=seed_demo(self.path,append=True,as_of=self.anchor+timedelta(days=1))
        self.assertTrue(again['already_applied'])
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT id,created_at,resolved_at FROM tickets ORDER BY id').fetchall(),original)

    def test_append_preserves_existing_users_and_grievances(self):
        with closing(sqlite3.connect(self.path)) as db:
            initialize_database(db)
            uid=db.execute("INSERT INTO users(name,email,password,role,hostel_block) VALUES('Existing','existing@example.test','unchanged','student','KP-1')").lastrowid
            db.execute("INSERT INTO tickets(user_id,category,description,hostel_block) VALUES(?,'Other','Existing report','KP-1')",(uid,))
            db.commit()
        with self.assertRaisesRegex(ValueError,'Refusing to seed'):
            seed_demo(self.path,as_of=self.anchor)
        seed_demo(self.path,append=True,as_of=self.anchor)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM tickets').fetchone()[0],41)
            self.assertEqual(db.execute('SELECT password FROM users WHERE id=?',(uid,)).fetchone()[0],'unchanged')
            self.assertEqual(db.execute('SELECT description FROM tickets WHERE user_id=?',(uid,)).fetchone()[0],'Existing report')

    def test_collision_rolls_back_whole_demo_batch(self):
        fixture=load_fixture()
        with closing(sqlite3.connect(self.path)) as db:
            initialize_database(db)
            db.execute("INSERT INTO users(name,email,password,role,hostel_block) VALUES('Existing',?,'unchanged','student','KP-1')",(fixture['students'][20]['email'],))
            db.commit()
        with self.assertRaisesRegex(ValueError,'Demo email already exists'):
            seed_demo(self.path,append=True,as_of=self.anchor)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM tickets').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM demo_batches').fetchone()[0],0)

    def test_naive_anchor_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'include a timezone'):
            seed_demo(self.path,as_of=datetime(2026,10,27))


if __name__=='__main__':
    unittest.main()
