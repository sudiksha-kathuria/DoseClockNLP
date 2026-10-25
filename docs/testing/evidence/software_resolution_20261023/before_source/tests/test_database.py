"""Tests use disposable SQLite files, never the household's schedule database."""
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_path = database.DB_PATH
        database.DB_PATH = str(Path(self.tmp.name) / 'test.db')

    def tearDown(self):
        database.DB_PATH = self.old_path
        self.tmp.cleanup()

    def test_pre_account_database_migrates_without_assigning_old_records(self):
        with closing(database.get_db_connection()) as conn, conn:
            conn.execute('''CREATE TABLE medicines (
                id INTEGER PRIMARY KEY, group_id TEXT, medicine_name TEXT,
                time TEXT, days_remaining INTEGER, language TEXT, created_at TEXT,
                last_fired_at TEXT, is_due INTEGER DEFAULT 0, audio_path TEXT)''')
            conn.execute("INSERT INTO medicines VALUES (1, 'old', 'Dummy', '08:00', 2, 'en', '2026-01-01', NULL, 0, NULL)")
        database.init_db()
        with closing(database.get_db_connection()) as conn, conn:
            columns = {r['name'] for r in conn.execute('PRAGMA table_info(medicines)')}
            self.assertIn('user_id', columns)
            self.assertIsNone(conn.execute('SELECT user_id FROM medicines').fetchone()[0])


    def test_taken_is_atomic_and_rejects_repeated_or_wrong_owner_actions(self):
        database.init_db()
        user = database.create_user('demo', 'test-only-password', 'Demo')
        group = database.add_medicine(user['id'], 'Dummy', ['08:00'], 2, 'en')
        medicine = database.get_group(group)[0]
        database.mark_fired(medicine['id'], 'audio/test.mp3')
        self.assertTrue(hasattr(database, 'acknowledge_due'), 'atomic acknowledgement is missing')
        self.assertIsNone(database.acknowledge_due(medicine['id'], user['id'] + 1))
        self.assertIsNotNone(database.acknowledge_due(medicine['id'], user['id']))
        self.assertIsNone(database.acknowledge_due(medicine['id'], user['id']))
        self.assertEqual(len(database.get_dose_history(user['id'])), 1)
        self.assertEqual(database.get_medicine(medicine['id'])['days_remaining'], 1)


if __name__ == '__main__':
    unittest.main()
