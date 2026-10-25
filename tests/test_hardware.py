"""Switch Hub pairing and actions use a disposable database and generated tokens."""
import re
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import database
import scheduler
from app import app


class HardwareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_path = database.DB_PATH
        database.DB_PATH = str(Path(self.tmp.name) / 'hardware.db')
        database.init_db()
        self.owner = database.create_user('owner', 'test-only', 'Owner')
        self.other = database.create_user('other', 'test-only', 'Other')
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session['user_id'] = self.owner['id']
        response = self.client.post('/pair_device', data={'name': 'Bedside switch'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.token = re.search(r'id="paired-token"[^>]*value="([^"]+)"', response.get_data(as_text=True)).group(1)
        group = database.add_medicine(self.owner['id'], 'Switch test', ['08:00'], 2, 'en')
        self.mid = database.get_group(group)[0]['id']

    def tearDown(self):
        database.DB_PATH = self.old_path
        self.tmp.cleanup()

    def action(self, action, token=None):
        return self.client.post('/api/device/action', json=self.action_body(action,token))

    def action_body(self, action, token=None):
        return {'token':self.token if token is None else token, 'action':action,
                'id':self.mid,'fired_at':database.get_medicine(self.mid)['last_fired_at'] or 'not-fired',
                'request_id':uuid.uuid4().hex}

    def test_pairing_token_is_owned_and_displayed_once(self):
        self.assertEqual(database.get_user_id_for_token(self.token), self.owner['id'])
        self.assertNotIn(self.token, self.client.get('/logs').get_data(as_text=True))
        self.assertEqual(app.test_client().post('/pair_device').status_code, 401)

    def test_invalid_token_action_and_no_due_statuses(self):
        self.assertEqual(self.action('taken', token='invalid-token').status_code, 401)
        self.assertEqual(self.action('unknown').status_code, 400)
        self.assertFalse(self.client.post('/api/device/reminder',json={'token':self.token}).json['due'])
        self.assertEqual(self.action('taken').status_code, 409)

    def test_hardware_taken_logs_once(self):
        database.mark_fired(self.mid, None)
        body = self.action_body('taken')
        response = self.client.post('/api/device/action',json=body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'success': True, 'medicine_name': 'Switch test'})
        self.assertEqual(self.client.post('/api/device/action',json=body).status_code, 200)
        self.assertEqual(self.action('taken').status_code, 409)
        self.assertEqual(len(database.get_dose_history(self.owner['id'])), 1)
        self.assertEqual(database.get_medicine(self.mid)['days_remaining'], 1)

    def test_hardware_snooze_survives_a_scheduler_restart(self):
        database.mark_fired(self.mid, None)
        now = datetime.now()
        with patch('database.datetime') as clock:
            clock.now.return_value = now
            self.assertEqual(self.action('snooze').status_code, 200)
        row = database.get_medicine(self.mid)
        deadline = datetime.fromisoformat(row['snoozed_until'])
        self.assertEqual(deadline, now + timedelta(minutes=5))
        self.assertEqual(row['is_due'], 0)
        with patch('scheduler.datetime') as clock:
            clock.now.return_value = deadline - timedelta(seconds=1)
            clock.fromisoformat.side_effect = datetime.fromisoformat
            scheduler._check_due_reminders()
            self.assertEqual(database.get_medicine(self.mid)['is_due'], 0)
            clock.now.return_value = deadline
            scheduler._check_due_reminders()
            self.assertEqual(database.get_medicine(self.mid)['is_due'], 1)

    def test_token_cannot_answer_another_users_reminder(self):
        group = database.add_medicine(self.other['id'], 'Other account', ['08:00'], 1, 'en')
        other_mid = database.get_group(group)[0]['id']
        database.mark_fired(other_mid, None)
        body={**self.action_body('taken'),'id':other_mid,'fired_at':database.get_medicine(other_mid)['last_fired_at']}
        self.assertEqual(self.client.post('/api/device/action',json=body).status_code, 404)
        self.assertEqual(database.get_medicine(other_mid)['is_due'], 1)

    def test_overlapping_device_action_returns_conflict(self):
        database.mark_fired(self.mid, None)
        body=self.action_body('taken')
        database.snooze_due(self.mid,(datetime.now()+timedelta(minutes=5)).isoformat(),self.owner['id'])
        self.assertEqual(self.client.post('/api/device/action',json=body).status_code, 409)
        self.assertEqual(len(database.get_dose_history(self.owner['id'])),0)

    def test_audio_failure_does_not_block_hardware(self):
        with patch('tts.get_or_create_audio', side_effect=RuntimeError('offline')):
            scheduler.fire_reminder(self.mid)
        self.assertEqual(self.action('taken').status_code, 200)


if __name__ == '__main__':
    unittest.main()
