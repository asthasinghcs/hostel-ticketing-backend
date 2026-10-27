"""Behavioral regression tests. All data lives in temporary databases."""
import hashlib
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stderr
import io
from datetime import timedelta
from werkzeug.security import generate_password_hash

_boot = tempfile.TemporaryDirectory(dir=os.environ.get("HOSTEL_TEST_TMP"))
os.environ['DATABASE_PATH'] = str(Path(_boot.name) / 'bootstrap.db')
from app import app, get_db, init_db, timestamp, utcnow


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.staff_hash = generate_password_hash('staffpassword')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get("HOSTEL_TEST_TMP"))
        app.config.update(TESTING=True, DATABASE=str(Path(self.tmp.name) / 'test.db'))
        self.client = app.test_client()
        with app.app_context():
            init_db()
            db = get_db()
            db.executemany('INSERT INTO users (name,email,password,role,hostel_block) VALUES (?,?,?,?,?)', [
                ('Admin', 'admin@example.test', self.staff_hash, 'admin', None),
                ('Warden', 'warden@example.test', self.staff_hash, 'warden', 'KP-1'),
                ('Warden 2', 'warden2@example.test', self.staff_hash, 'warden', 'KP-2'),
            ])
            db.commit()
        self.student = self.signup('one@example.test', 'KP-1')
        self.other = self.signup('two@example.test', 'KP-2')

    def tearDown(self):
        self.tmp.cleanup()

    def signup(self, email, block):
        response = self.client.post('/api/signup', json=dict(name='Student', email=email, password='password123', hostel_block=block))
        self.assertEqual(response.status_code, 201, response.json)
        return response.json

    def login(self, email):
        response = self.client.post('/api/login', json=dict(email=email, password='staffpassword'))
        self.assertEqual(response.status_code, 200)
        return response.json

    def auth(self, session):
        return {'Authorization': 'Bearer ' + session['token']}

    def ticket(self, session=None, **values):
        session = session or self.student
        data = dict(category='Wi-Fi', description='Network is down', hostel_block=session['user']['hostel_block'])
        data.update(values)
        response = self.client.post('/api/tickets', json=data, headers=self.auth(session))
        self.assertEqual(response.status_code, 201, response.json)
        return response.json

    def test_signup_returns_session_and_refresh_identity(self):
        session = self.student
        self.assertEqual(session['user']['role'], 'student')
        self.assertEqual(self.client.get('/api/me', headers=self.auth(session)).json['user'], session['user'])
        with app.app_context():
            stored = get_db().execute('SELECT password FROM users WHERE id=?', (session['user']['id'],)).fetchone()[0]
            token_hash = get_db().execute('SELECT token_hash FROM sessions WHERE user_id=?', (session['user']['id'],)).fetchone()[0]
            self.assertTrue(stored.startswith('scrypt:'))
            self.assertNotEqual(token_hash, session['token'])

    def test_public_signup_cannot_create_staff(self):
        for role in ('admin', 'warden'):
            response = self.client.post('/api/signup', json=dict(name='X', email=f'{role}@test.local', password='password123', hostel_block='KP-1', role=role))
            self.assertEqual(response.status_code, 403)

    def test_every_business_endpoint_requires_authentication(self):
        for method, path in [('get', '/api/tickets'), ('get', '/api/stats'), ('get', '/api/overview'), ('get', '/api/me'), ('post', '/api/tickets'), ('patch', '/api/tickets/1/status'), ('post', '/api/tickets/1/vote'), ('get', '/api/tickets/1/comments'), ('post', '/api/tickets/1/comments')]:
            response = getattr(self.client, method)(path, json={})
            self.assertEqual(response.status_code, 401, path)

    def test_sessions_expire_and_logout_revokes(self):
        headers = self.auth(self.student)
        self.assertEqual(self.client.post('/api/logout', headers=headers).status_code, 200)
        self.assertEqual(self.client.get('/api/me', headers=headers).status_code, 401)
        with app.app_context():
            get_db().execute('UPDATE sessions SET expires_at=?', (timestamp(utcnow() - timedelta(seconds=1)),))
            get_db().commit()
        self.assertEqual(self.client.get('/api/me', headers=self.auth(self.other)).status_code, 401)

    def test_login_invalid_credentials_and_case_insensitive_email(self):
        self.assertEqual(self.client.post('/api/login', json={'email': 'one@example.test', 'password': 'wrong'}).status_code, 401)
        self.assertEqual(self.client.post('/api/login', json={'email': ' ONE@EXAMPLE.TEST ', 'password': 'password123'}).status_code, 200)
        self.assertEqual(self.client.post('/api/signup', json=dict(name='Duplicate', email='ONE@example.test', password='password123', hostel_block='KP-1')).status_code, 409)

    def test_legacy_password_upgraded_without_data_loss(self):
        with app.app_context():
            db = get_db()
            db.execute('UPDATE users SET password=? WHERE id=?', (hashlib.sha256(b'legacy').hexdigest(), self.student['user']['id']))
            db.commit()
        response = self.client.post('/api/login', json=dict(email='one@example.test', password='legacy'))
        self.assertEqual(response.status_code, 200)
        with app.app_context():
            self.assertTrue(get_db().execute('SELECT password FROM users WHERE id=?', (self.student['user']['id'],)).fetchone()[0].startswith('scrypt:'))

    def test_create_ticket_uses_session_identity_and_scopes_block(self):
        ticket = self.ticket(user_id=self.other['user']['id'])
        self.assertEqual(ticket['user_id'], self.student['user']['id'])
        self.assertIsNone(ticket['floor'])
        response = self.client.post('/api/tickets', json=dict(category='Wi-Fi', description='x', hostel_block='KP-2'), headers=self.auth(self.student))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.patch(f"/api/tickets/{ticket['id']}/status", json={'status': 'Resolved'}, headers=self.auth(self.student)).status_code, 403)

    def test_warden_can_manage_all_hostels_and_filter_them(self):
        own = self.ticket()
        other = self.ticket(self.other)
        warden = self.auth(self.login('warden@example.test'))
        self.assertEqual({t['id'] for t in self.client.get('/api/tickets', headers=warden).json}, {own['id'], other['id']})
        self.assertEqual(self.client.get('/api/stats', headers=warden).json['total'], 2)
        self.assertEqual(self.client.get('/api/stats?hostel_block=KP-2', headers=warden).json['total'], 1)
        self.assertEqual(self.client.patch(f"/api/tickets/{other['id']}/status", headers=warden, json={'status': 'Resolved'}).status_code, 200)
        self.assertEqual(self.client.post(f"/api/tickets/{other['id']}/comments", headers=warden, json={'text': 'A cross-hostel staff update.'}).status_code, 201)
        self.assertEqual(self.client.get(f"/api/tickets/{other['id']}/comments", headers=warden).status_code, 200)
        overview = self.client.get('/api/overview', headers=warden).json
        self.assertEqual(overview['stats']['total'], 2)
        self.assertEqual(overview['stats']['resolved'], 1)

    def test_student_reads_are_hostel_scoped_without_a_filter(self):
        own = self.ticket()
        self.ticket(self.other)
        headers = self.auth(self.student)
        self.assertEqual([t['id'] for t in self.client.get('/api/tickets', headers=headers).json], [own['id']])
        self.assertEqual(self.client.get('/api/stats', headers=headers).json['total'], 1)
        overview = self.client.get('/api/overview', headers=headers).json
        self.assertEqual([t['id'] for t in overview['tickets']], [own['id']])
        self.assertEqual(overview['stats']['total'], 1)

    def test_student_cannot_switch_hostel_or_read_guessed_ticket_discussions(self):
        other = self.ticket(self.other)
        headers = self.auth(self.student)
        for path in ('/api/tickets?hostel_block=KP-2', '/api/stats?hostel_block=KP-2', '/api/overview?hostel_block=KP-2', f"/api/tickets/{other['id']}/comments"):
            response = self.client.get(path, headers=headers)
            self.assertEqual(response.status_code, 403, path)
            self.assertNotIn('Network is down', response.get_data(as_text=True))

    def test_landing_hostel_and_portal_never_override_account_permissions(self):
        credentials = dict(email='one@example.test', password='password123', portal='student')
        self.assertEqual(self.client.post('/api/login', json=dict(credentials, hostel_block='KP-2')).status_code, 403)
        self.assertEqual(self.client.post('/api/login', json=dict(credentials, hostel_block='KP-1')).status_code, 200)
        self.assertEqual(self.client.post('/api/login', json=dict(credentials, portal='staff')).status_code, 403)
        staff = dict(email='warden@example.test', password='staffpassword')
        self.assertEqual(self.client.post('/api/login', json=dict(staff, portal='staff')).status_code, 200)
        self.assertEqual(self.client.post('/api/login', json=dict(staff, portal='student', hostel_block='KP-1')).status_code, 403)

    def test_ticket_counts_increase_exactly_and_persist_for_the_correct_hostel(self):
        headers = self.auth(self.student)
        before = self.client.get('/api/overview', headers=headers).json
        self.assertEqual(before['stats']['total'], 0)
        self.ticket(self.other)
        first = self.ticket()
        self.ticket()
        after = self.client.get('/api/overview', headers=headers).json
        self.assertEqual(after['stats']['total'], 2)
        self.assertEqual(after['stats']['my_total'], 2)
        self.assertEqual(after['stats']['open'], 2)
        self.assertEqual(len(after['tickets']), 2)
        # A list filter must not reduce the overview's all-status counters.
        filtered = self.client.get('/api/overview?status=Resolved', headers=headers).json
        self.assertEqual(filtered['tickets'], [])
        self.assertEqual(filtered['stats']['total'], 2)
        fresh = self.client.post('/api/login', json=dict(email='one@example.test', password='password123')).json
        self.assertEqual(self.client.get('/api/overview', headers=self.auth(fresh)).json['stats']['total'], 2)
        warden = self.auth(self.login('warden@example.test'))
        self.client.patch(f"/api/tickets/{first['id']}/status", headers=warden, json={'status':'Resolved'})
        final = self.client.get('/api/overview', headers=headers).json
        self.assertEqual(final['stats']['total'], 2)
        self.assertEqual(final['stats']['open'], 1)
        self.assertEqual(final['stats']['resolved'], 1)
        self.assertEqual(self.client.get('/api/overview', headers=warden).json['stats']['total'], 3)
        self.assertEqual(self.client.get('/api/overview', headers=headers).headers['Cache-Control'], 'no-store')

    def test_admin_can_manage_all_blocks_and_resolution_timestamp(self):
        ticket = self.ticket(self.other)
        headers = self.auth(self.login('admin@example.test'))
        path = f"/api/tickets/{ticket['id']}/status"
        resolved = self.client.patch(path, json={'status': 'Resolved'}, headers=headers).json
        self.assertIsNotNone(resolved['resolved_at'])
        self.assertFalse(resolved['overdue'])
        self.assertEqual(self.client.patch(path, json={'status': 'Resolved'}, headers=headers).json['resolved_at'], resolved['resolved_at'])
        self.assertIsNone(self.client.patch(path, json={'status': 'Open'}, headers=headers).json['resolved_at'])
        self.assertEqual(self.client.get('/api/stats', headers=headers).json['total'], 1)

    def test_votes_cannot_be_duplicated_or_spoofed(self):
        ticket = self.ticket()
        path = f"/api/tickets/{ticket['id']}/vote"
        response = self.client.post(path, headers=self.auth(self.student), json={'user_id': self.other['user']['id']})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json['has_voted'])
        self.assertEqual(response.json['vote_count'], 1)
        self.assertEqual(self.client.post(path, headers=self.auth(self.student), json={}).status_code, 409)
        self.assertEqual(self.client.post(path, headers=self.auth(self.other), json={}).status_code, 403)
        admin = self.auth(self.login('admin@example.test'))
        self.assertEqual(self.client.post(path, headers=admin, json={}).status_code, 403)
        self.client.patch(f"/api/tickets/{ticket['id']}/status", headers=admin, json={'status': 'Resolved'})
        third = self.signup('third@example.test', 'KP-1')
        self.assertEqual(self.client.post(path, headers=self.auth(third), json={}).status_code, 409)

    def test_comment_lifecycle_identity_and_validation(self):
        ticket = self.ticket()
        path = f"/api/tickets/{ticket['id']}/comments"
        response = self.client.post(path, headers=self.auth(self.student), json={'text': '  Please check the router.  ', 'user_id': 1})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['author_role'], 'student')
        self.assertEqual(response.json['text'], 'Please check the router.')
        self.assertEqual(len(self.client.get(path, headers=self.auth(self.student)).json), 1)
        self.assertEqual(self.client.post(path, headers=self.auth(self.student), json={'text': '  '}).status_code, 400)
        self.assertEqual(self.client.post(path, headers=self.auth(self.student), json={'text': 'x' * 2001}).status_code, 400)
        self.assertEqual(self.client.post(path, headers=self.auth(self.other), json={'text': 'x'}).status_code, 403)

    def test_missing_tickets_do_not_create_orphan_records(self):
        headers = self.auth(self.student)
        for suffix in ('vote', 'comments'):
            self.assertEqual(self.client.post(f'/api/tickets/999/{suffix}', headers=headers, json={'text': 'x'}).status_code, 404)
        admin = self.auth(self.login('admin@example.test'))
        self.assertEqual(self.client.patch('/api/tickets/999/status', headers=admin, json={'status': 'Open'}).status_code, 404)
        with app.app_context():
            with self.assertRaises(sqlite3.IntegrityError):
                get_db().execute('INSERT INTO votes(ticket_id,user_id) VALUES(999,999)')

    def test_malformed_input_returns_json_errors(self):
        for data in (None, [], 'hello', 4):
            response = self.client.post('/api/login', json=data)
            self.assertEqual(response.status_code, 400)
            self.assertIn('error', response.json)
        for change in ({'category': 'Invalid'}, {'description': ' '}, {'description': 22}, {'floor': []}):
            payload = dict(category='Wi-Fi', description='Issue', hostel_block='KP-1')
            payload.update(change)
            self.assertEqual(self.client.post('/api/tickets', headers=self.auth(self.student), json=payload).status_code, 400)
        self.assertEqual(self.client.get('/api/tickets?sort=bad', headers=self.auth(self.student)).status_code, 400)
        self.assertEqual(self.client.get('/api/tickets?status=bad', headers=self.auth(self.student)).status_code, 400)

    def test_overdue_filters_stats_and_vote_sort(self):
        ticket = self.ticket()
        self.ticket(self.other)
        with app.app_context():
            get_db().execute('UPDATE tickets SET created_at=? WHERE id=?', (timestamp(utcnow() - timedelta(hours=49)), ticket['id']))
            get_db().commit()
        headers = self.auth(self.student)
        self.client.post(f"/api/tickets/{ticket['id']}/vote", headers=headers, json={})
        result = self.client.get('/api/tickets?sort=votes', headers=headers).json
        self.assertEqual(result[0]['id'], ticket['id'])
        self.assertTrue(result[0]['overdue'])
        self.assertEqual(len(self.client.get('/api/tickets?hostel_block=KP-1&status=Open', headers=headers).json), 1)
        self.assertEqual(self.client.get('/api/stats?hostel_block=KP-1', headers=headers).json['overdue'], 1)

    def test_schema_migration_preserves_existing_records(self):
        self.ticket()
        with app.app_context():
            before = get_db().execute('SELECT COUNT(*) FROM users').fetchone()[0]
            init_db()
            init_db()
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM users').fetchone()[0], before)
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM tickets').fetchone()[0], 1)

    def test_seed_refuses_populated_database(self):
        env = dict(os.environ, DATABASE_PATH=app.config['DATABASE'])
        response = subprocess.run([sys.executable, str(Path(__file__).parent / 'seed.py')], env=env, capture_output=True, text=True)
        self.assertNotEqual(response.returncode, 0)
        self.assertIn('Refusing to seed', response.stderr)
        with app.app_context():
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM users').fetchone()[0], 5)

    def test_staff_cli_provisions_warden_with_descriptive_home_block(self):
        import manage
        argv = ['manage.py', 'create-staff', '--name', 'New Warden', '--email', 'newwarden@example.test', '--role', 'warden', '--block', 'KP-3']
        with patch.object(sys, 'argv', argv), patch('getpass.getpass', side_effect=['staffpassword', 'staffpassword']), patch('builtins.print'):
            manage.main()
        account = self.login('newwarden@example.test')
        self.assertEqual(account['user']['role'], 'warden')
        self.assertEqual(account['user']['hostel_block'], 'KP-3')

    def test_staff_cli_provisions_warden_without_a_block_restriction(self):
        import manage
        argv = ['manage.py', 'create-staff', '--name', 'Campus Warden', '--email', 'campuswarden@example.test', '--role', 'warden']
        with patch.object(sys, 'argv', argv), patch('getpass.getpass', side_effect=['staffpassword', 'staffpassword']), patch('builtins.print'):
            manage.main()
        account = self.login('campuswarden@example.test')
        self.assertIsNone(account['user']['hostel_block'])
        self.ticket()
        self.ticket(self.other)
        self.assertEqual(self.client.get('/api/overview', headers=self.auth(account)).json['stats']['total'], 2)

    def test_staff_cli_cannot_overwrite_existing_student(self):
        import manage
        argv = ['manage.py', 'create-staff', '--name', 'Admin', '--email', 'one@example.test', '--role', 'admin']
        with patch.object(sys, 'argv', argv), patch('getpass.getpass', side_effect=['staffpassword', 'staffpassword']), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            manage.main()
        with app.app_context():
            self.assertEqual(get_db().execute('SELECT role FROM users WHERE id=?', (self.student['user']['id'],)).fetchone()[0], 'student')

    def test_cors_allows_only_configured_frontend(self):
        allowed = self.client.options('/api/tickets', headers={'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'GET', 'Access-Control-Request-Headers': 'Authorization'})
        self.assertEqual(allowed.headers.get('Access-Control-Allow-Origin'), 'http://localhost:5173')
        denied = self.client.options('/api/tickets', headers={'Origin': 'https://untrusted.example', 'Access-Control-Request-Method': 'GET'})
        self.assertIsNone(denied.headers.get('Access-Control-Allow-Origin'))


if __name__ == '__main__':
    unittest.main()
