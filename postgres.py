"""Small PostgreSQL adapter for the application's shared SQL operations."""
import re
import sqlite3


class Row(dict):
    def __getitem__(self, key):
        return list(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


class Cursor:
    def __init__(self, cursor, lastrowid=None):
        self.cursor = cursor
        self.lastrowid = lastrowid

    def fetchone(self):
        row = self.cursor.fetchone()
        return Row(row) if row is not None else None

    def fetchall(self):
        return [Row(row) for row in self.cursor.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())


class Connection:
    dialect = 'postgres'
    identity_tables = {'users', 'tickets', 'votes', 'comments', 'ticket_events'}

    def __init__(self, url):
        import psycopg
        from psycopg.rows import dict_row
        self.driver = psycopg
        self.raw = psycopg.connect(url, autocommit=True, row_factory=dict_row, connect_timeout=15)
        self.in_transaction = False
        self.write_lock = False

    def execute(self, sql, params=()):
        statement = sql.strip()
        upper = statement.upper()
        if upper in ('BEGIN', 'BEGIN IMMEDIATE'):
            self.write_lock = upper == 'BEGIN IMMEDIATE'
            self.raw.execute('BEGIN' if self.write_lock else 'BEGIN ISOLATION LEVEL REPEATABLE READ')
            self.in_transaction = True
            return Cursor(self.raw.cursor())
        if upper.startswith(('INSERT ', 'UPDATE ', 'DELETE ')) and not self.in_transaction:
            self.raw.execute('BEGIN')
            self.in_transaction = True
        if self.write_lock and re.fullmatch(r'SELECT \* FROM tickets WHERE id=\?', statement, re.I):
            statement += ' FOR UPDATE'
        match = re.match(r'INSERT\s+INTO\s+(\w+)', statement, re.I)
        returns_id = bool(match and match[1].lower() in self.identity_tables and 'RETURNING' not in upper)
        if returns_id:
            statement = statement.rstrip(';') + ' RETURNING id'
        try:
            cur = self.raw.execute(statement.replace('?', '%s'), params)
            inserted = cur.fetchone()['id'] if returns_id else None
            return Cursor(cur, inserted)
        except self.driver.IntegrityError as error:
            raise sqlite3.IntegrityError(str(error)) from error

    def executemany(self, sql, rows):
        for row in rows:
            self.execute(sql, row)

    def executescript(self, script):
        self.raw.execute(script)

    def commit(self):
        self.raw.commit()
        self.in_transaction = self.write_lock = False

    def rollback(self):
        self.raw.rollback()
        self.in_transaction = self.write_lock = False

    def close(self):
        self.rollback()
        self.raw.close()
