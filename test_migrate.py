"""Snapshot safety checks without writing to any production database."""
import base64
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
import zlib
from database import initialize_database
from migrate_postgres import export_snapshot, export_connection, TABLES


class SnapshotTests(unittest.TestCase):
    def test_export_preserves_data_and_excludes_sessions(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('HOSTEL_TEST_TMP')) as folder:
            path=Path(folder)/'source.db'
            with closing(sqlite3.connect(path)) as db:
                initialize_database(db)
                db.execute("INSERT INTO users(name,email,password,role,hostel_block) VALUES('Student','24050001@kiit.ac.in','hash','student','KP-1')")
                db.execute("INSERT INTO sessions VALUES('private-session',1,'2099-01-01')")
                db.execute("INSERT INTO tickets(user_id,category,description,hostel_block) VALUES(1,'Wi-Fi','Network outage','KP-1')")
                db.commit()
            encoded=export_snapshot(path)
            decoded=zlib.decompress(base64.b64decode(encoded))
            snapshot=json.loads(decoded)
            self.assertEqual(set(snapshot['tables']),set(TABLES))
            self.assertNotIn(b'private-session',decoded)
            self.assertEqual(snapshot['tables']['users'][0]['password'],'hash')
            self.assertEqual(snapshot['tables']['tickets'][0]['id'],1)
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0],1)
                db.row_factory = sqlite3.Row
                hosted = json.loads(zlib.decompress(base64.b64decode(export_connection(db))))
                self.assertEqual(hosted, snapshot)

    def test_missing_source_is_not_created(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('HOSTEL_TEST_TMP')) as folder:
            path=Path(folder)/'missing.db'
            with self.assertRaises(sqlite3.OperationalError):
                export_snapshot(path)
            self.assertFalse(path.exists())
