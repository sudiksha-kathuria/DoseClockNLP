"""Review 3 regressions. Disposable DB/cache; no physical hardware assertions."""
import concurrent.futures
import re
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import database
import scheduler
import tts
from app import app


class Review3Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db, self.old_audio = database.DB_PATH, tts.AUDIO_DIR
        database.DB_PATH = str(Path(self.tmp.name) / 'review.db')
        tts.AUDIO_DIR = str(Path(self.tmp.name) / 'audio')
        database.init_db()
        self.owner = database.create_user('review_owner', 'dummy-password', 'Review Owner')
        self.other = database.create_user('review_other', 'dummy-password', 'Review Other')
        self.client = self.client_for(self.owner['id'])
        self.warm = patch('scheduler.prepare_audio'); self.warm.start()

    def tearDown(self):
        self.warm.stop()
        database.DB_PATH, tts.AUDIO_DIR = self.old_db, self.old_audio
        self.tmp.cleanup()

    def client_for(self, uid):
        c = app.test_client()
        with c.session_transaction() as session: session['user_id'] = uid
        return c

    def medicine(self, times=('08:00',), days=3, owner=None, name='Review dummy'):
        gid = database.add_medicine(owner or self.owner['id'], name, list(times), days, 'en')
        return gid, list(database.get_group(gid))

    def test_signup_login_logout_and_invalid_credentials(self):
        c = app.test_client()
        self.assertEqual(c.post('/signup', data={'username':' NEW_USER ', 'display_name':'New User', 'password':'dummy-password'}).status_code, 302)
        self.assertIsNotNone(database.get_user_by_username('new_user'))
        self.assertEqual(c.post('/logout').status_code, 302)
        self.assertEqual(c.get('/check_reminders').status_code, 401)
        self.assertIn(b'Wrong username or password', c.post('/login', data={'username':'new_user','password':'wrong'}).data)
        self.assertEqual(c.get('/check_reminders').status_code, 401)
        self.assertEqual(c.post('/login', data={'username':'new_user','password':'dummy-password'}).status_code, 302)
        self.assertEqual(c.get('/clock').status_code, 200)

    def test_signup_duplicate_and_short_password_rejected(self):
        c=app.test_client()
        for values,message in [({'username':'review_owner','display_name':'Another','password':'dummy-password'},b'already taken'),({'username':'too_short','display_name':'Short','password':'123'},b'at least 4')]:
            self.assertIn(message,c.post('/signup',data=values).data)
        self.assertIsNone(database.get_user_by_username('too_short'))

    def test_authenticated_routes_and_account_isolation(self):
        gid,rows=self.medicine(owner=self.other['id'],name='Other private medicine')
        database.mark_fired(rows[0]['id'],None)
        self.assertFalse(self.client.get('/check_reminders').json['due'])
        for route in ['/', '/clock','/logs','/dashboard','/export']:
            self.assertNotIn(b'Other private medicine',self.client.get(route).data)
        for route in ['/mark_taken','/mark_snooze']:
            self.assertEqual(self.client.post(route,json={'id':rows[0]['id']}).status_code,404)
        self.assertEqual(self.client.post('/delete_medicine',json={'id':gid}).status_code,404)
        self.assertEqual(database.get_medicine(rows[0]['id'])['days_remaining'],3)

    def test_creation_multiple_times_and_audio_warming(self):
        r=self.client.post('/add_medicine',json={'medicine_name':'New audio label','times':['08:00','20:00'],'days':3,'language':'hi'})
        self.assertEqual(r.status_code,200)
        rows=database.get_active_medicines(self.owner['id'])
        self.assertEqual([x['time'] for x in rows],['08:00','20:00'])
        self.assertEqual(len({x['group_id'] for x in rows}),1)
        self.warm_mock_called('New audio label','hi')

    def warm_mock_called(self,*args):
        scheduler.prepare_audio.assert_called_with(*args)

    def test_invalid_creation_fields_rejected(self):
        base={'medicine_name':'Dummy','times':['08:00'],'days':2,'language':'en'}
        for field,value in [('medicine_name',''),('times',[]),('days',0),('days',-1),('language','zz')]:
            self.assertEqual(self.client.post('/add_medicine',json={**base,field:value}).status_code,400,(field,value))
        self.assertEqual(len(database.get_active_medicines(self.owner['id'])),0)

    def test_invalid_time_values_rejected(self):
        for times in [['25:00'],['08:99'],['8:00'],['08:00','08:00'],'08:00',[123]]:
            self.assertEqual(self.client.post('/add_medicine',json={'medicine_name':'Dummy','times':times,'days':2,'language':'en'}).status_code,400,times)
        self.assertEqual(len(database.get_active_medicines(self.owner['id'])),0)

    def test_non_object_json_rejected(self):
        for route in ['/add_medicine','/delete_medicine','/mark_taken','/mark_snooze','/api/device/action']:
            self.assertEqual(self.client.post(route,json=['unexpected']).status_code,400,route)

    def test_wrong_json_field_types_rejected(self):
        token=database.create_device_token(self.owner['id'],'Dummy simulator')
        self.assertEqual(self.client.post('/api/device/action',json={'token':['invalid'],'action':'taken'}).status_code,400)
        self.assertEqual(self.client.post('/api/device/action',json={'token':token,'action':[]}).status_code,400)
        self.assertEqual(self.client.post('/add_medicine',json={'medicine_name':123,'times':['08:00'],'days':2,'language':'en'}).status_code,400)

    def test_take_logs_exactly_once_and_updates_last_course_slot(self):
        gid,rows=self.medicine(times=('08:00','20:00'),days=2)
        for i,row in enumerate(rows):
            database.mark_fired(row['id'],None)
            response=self.client.post('/mark_taken',json={'id':row['id']})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json['days_remaining'],2 if i==0 else 1)
            self.assertEqual(self.client.post('/mark_taken',json={'id':row['id']}).status_code,409)
        self.assertEqual(len(database.get_dose_history(self.owner['id'])),2)
        self.assertEqual({r['days_remaining'] for r in database.get_group(gid)},{1})

    def test_actual_concurrent_taken_requests_log_once(self):
        _,rows=self.medicine();mid=rows[0]['id'];database.mark_fired(mid,None)
        barrier=threading.Barrier(2)
        def take(_):
            c=self.client_for(self.owner['id']);barrier.wait()
            return c.post('/mark_taken',json={'id':mid}).status_code
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool: statuses=list(pool.map(take,range(2)))
        self.assertEqual(sorted(statuses),[200,409])
        self.assertEqual(len(database.get_dose_history(self.owner['id'])),1)

    def test_stale_firing_generation_is_rejected(self):
        _,rows=self.medicine();mid=rows[0]['id'];database.mark_fired(mid,None)
        stale=database.get_medicine(mid)['last_fired_at'];database.mark_fired(mid,None)
        self.assertEqual(self.client.post('/mark_taken',json={'id':mid,'fired_at':stale}).status_code,409)
        self.assertEqual(len(database.get_dose_history(self.owner['id'])),0)
        self.assertEqual(self.client.get('/check_reminders').json['fired_at'],database.get_medicine(mid)['last_fired_at'])

    def test_deleting_due_medicine_clears_alarm_and_preserves_history(self):
        gid,rows=self.medicine();mid=rows[0]['id'];database.mark_fired(mid,None)
        self.client.post('/mark_taken',json={'id':mid});database.mark_fired(mid,None)
        self.assertEqual(self.client.post('/delete_medicine',json={'id':gid}).status_code,200)
        self.assertFalse(self.client.get('/check_reminders').json['due'])
        self.assertEqual(len(database.get_dose_history(self.owner['id'])),1)
        self.assertEqual(len(database.get_active_medicines(self.owner['id'])),0)

    def test_edit_after_taken_preserves_historical_details(self):
        gid,rows=self.medicine(name='Original dummy');mid=rows[0]['id']
        database.mark_fired(mid,None);database.acknowledge_due(mid,self.owner['id'])
        before=dict(database.get_dose_history(self.owner['id'])[0])
        r=self.client.post('/medicine/'+gid+'/edit',data={'medicine_name':'Edited dummy','times':['09:00','21:00'],'language':'hi','days_remaining':4})
        self.assertEqual(r.status_code,302)
        after=dict(database.get_dose_history(self.owner['id'])[0])
        self.assertEqual(before,after)
        summary=database.get_group_summary(gid,self.owner['id'])
        self.assertEqual(summary['times'],['09:00','21:00'])
        self.assertEqual(summary['medicine_name'],'Edited dummy')
        self.assertEqual(len(database.get_group(gid)),2)

    def test_existing_account_history_survives_archive_schema_migration(self):
        gid, rows = self.medicine(name='Legacy history dummy')
        database.mark_fired(rows[0]['id'], None)
        database.acknowledge_due(rows[0]['id'], self.owner['id'])
        token = database.create_device_token(self.owner['id'], 'Legacy dummy token')
        before = dict(database.get_dose_history(self.owner['id'])[0])
        # Reconstruct the immediately preceding schema in this disposable DB.
        with database.get_db_connection() as conn:
            conn.execute('ALTER TABLE medicines DROP COLUMN is_archived')
        database.init_db()
        self.assertEqual(dict(database.get_dose_history(self.owner['id'])[0]), before)
        self.assertEqual(database.get_user_id_for_token(token), self.owner['id'])
        self.assertEqual(database.get_group_summary(gid, self.owner['id'])['times'], ['08:00'])
        self.assertEqual(database.get_medicine(rows[0]['id'])['is_archived'], 0)

    def test_restart_database_retains_accounts_tokens_logs_and_snooze(self):
        _,rows=self.medicine(times=('08:00','20:00'));a,b=rows
        token=database.create_device_token(self.owner['id'],'Restart dummy')
        database.mark_fired(a['id'],None);database.acknowledge_due(a['id'],self.owner['id'])
        database.mark_fired(b['id'],None);scheduler.schedule_snooze(b['id'],self.owner['id'])
        deadline=database.get_medicine(b['id'])['snoozed_until']
        database.init_db()
        self.assertIsNotNone(database.verify_user('review_owner','dummy-password'))
        self.assertEqual(database.get_user_id_for_token(token),self.owner['id'])
        self.assertEqual(database.get_medicine(b['id'])['snoozed_until'],deadline)
        self.assertEqual(len(database.get_dose_history(self.owner['id'])),1)

    def test_scheduler_scheduled_time_overdue_and_same_day_guard(self):
        _,rows=self.medicine(times=('08:00','20:00'))
        with database.get_db_connection() as conn:conn.execute("UPDATE medicines SET created_at='2026-01-01T00:00:00'")
        now=datetime(2026,10,23,8,0,0)
        with patch('scheduler.datetime') as clock:
            clock.now.return_value=now;clock.combine.side_effect=datetime.combine;clock.strptime.side_effect=datetime.strptime;clock.fromisoformat.side_effect=datetime.fromisoformat
            scheduler._check_due_reminders()
            self.assertEqual(database.get_medicine(rows[0]['id'])['is_due'],1)
            self.assertEqual(database.get_medicine(rows[1]['id'])['is_due'],0)
            # mark_fired uses database's real clock: set this unit-test fixture explicitly.
            with database.get_db_connection() as conn:conn.execute('UPDATE medicines SET is_due=0,last_fired_at=? WHERE id=?',(now.isoformat(),rows[0]['id']))
            scheduler._check_due_reminders()
            self.assertEqual(database.get_medicine(rows[0]['id'])['is_due'],0)

    def test_scheduler_multiple_simultaneous_and_restart_recovery(self):
        ids=[self.medicine(name='Simultaneous '+str(i))[1][0]['id'] for i in range(2)]
        with database.get_db_connection() as conn:conn.execute("UPDATE medicines SET created_at='2026-01-01T00:00:00'")
        with patch('scheduler.datetime') as clock:
            clock.now.return_value=datetime(2026,10,23,9,0);clock.combine.side_effect=datetime.combine;clock.strptime.side_effect=datetime.strptime;clock.fromisoformat.side_effect=datetime.fromisoformat
            scheduler._check_due_reminders()
        self.assertTrue(all(database.get_medicine(i)['is_due']==1 for i in ids))
        self.assertEqual(self.client.post('/mark_taken',json={'id':ids[0]}).status_code,200)
        self.assertEqual(self.client.get('/check_reminders').json['id'],ids[1])

    def test_repeated_snooze_unit_clock_and_no_taken_logs(self):
        _,rows=self.medicine();mid=rows[0]['id'];now=datetime(2026,10,23,9,0)
        database.mark_fired(mid,None)
        for _ in range(2):
            with patch('scheduler.datetime') as clock:
                clock.now.return_value=now
                self.assertEqual(self.client.post('/mark_snooze',json={'id':mid}).status_code,200)
                deadline=now+timedelta(seconds=300)
                self.assertEqual(datetime.fromisoformat(database.get_medicine(mid)['snoozed_until']),deadline)
                clock.fromisoformat.side_effect=datetime.fromisoformat;clock.now.return_value=deadline
                scheduler._check_due_reminders()
                self.assertEqual(database.get_medicine(mid)['is_due'],1)
            now=deadline
        self.assertEqual(len(database.get_dose_history(self.owner['id'])),0)

    def test_pairing_missing_invalid_token_and_account_isolation(self):
        r=self.client.post('/pair_device',data={'name':'Review simulated ESP32'})
        token=re.search(r'id="paired-token"[^>]*value="([^"]+)"',r.get_data(as_text=True)).group(1)
        self.assertEqual(len(token),32);self.assertIn('no-store',r.headers['Cache-Control'])
        self.assertNotIn(token,self.client.get('/logs').get_data(as_text=True))
        for payload in [{},{'token':'invalid','action':'taken'}]:self.assertEqual(self.client.post('/api/device/action',json=payload).status_code,401)
        _,rows=self.medicine(owner=self.other['id']);database.mark_fired(rows[0]['id'],None)
        self.assertEqual(self.client.post('/api/device/action',json={'token':token,'action':'taken'}).status_code,404)
        self.assertEqual(database.get_medicine(rows[0]['id'])['is_due'],1)

    def test_device_multiple_due_selection_is_documented_not_replay_safe(self):
        ids=[self.medicine(name='Pending '+str(i))[1][0]['id'] for i in range(2)]
        for mid in ids:database.mark_fired(mid,None)
        token=database.create_device_token(self.owner['id'],'Simulated switch')
        for _ in ids:self.assertEqual(self.client.post('/api/device/action',json={'token':token,'action':'taken'}).status_code,200)
        self.assertEqual(len(database.get_dose_history(self.owner['id'])),2)
        self.assertEqual(self.client.post('/api/device/action',json={'token':token,'action':'taken'}).status_code,404)

    def test_tts_failure_is_atomic_and_visual_alarm_remains(self):
        _,rows=self.medicine()
        class BrokenSpeech:
            def save(self,path):Path(path).write_bytes(b'partial');raise OSError('controlled synthesis failure')
        with patch('tts.gTTS',return_value=BrokenSpeech()):
            with self.assertRaises(OSError):tts.get_or_create_audio('Failure dummy','en')
        self.assertEqual(list(Path(tts.AUDIO_DIR).glob('*.mp3')),[])
        scheduler.fire_reminder(rows[0]['id'])
        self.assertTrue(self.client.get('/check_reminders').json['due'])
        self.assertIsNone(self.client.get('/check_reminders').json['audio_url'])

    def test_background_synthesis_failure_is_observed(self):
        self.warm.stop()
        with patch('tts.get_or_create_audio',side_effect=RuntimeError('controlled offline')) as generate:
            with self.assertLogs('scheduler',level='WARNING') as logs:
                scheduler.prepare_audio('Unique failure label','en')
                import time
                until=time.monotonic()+3
                while ('Unique failure label','en') in scheduler._audio_pending and time.monotonic()<until:time.sleep(.01)
            generate.assert_called_once()
            self.assertTrue(any('visual alarm remains active' in x for x in logs.output))
        self.warm.start()

    def test_tts_cache_reused_when_synthesis_unavailable(self):
        Path(tts.AUDIO_DIR).mkdir()
        path=Path(tts.AUDIO_DIR)/tts._cache_filename('Cached dummy','en')
        path.write_bytes(b'ID3dummy-cache-fixture')
        with patch('tts.gTTS',side_effect=ConnectionError('offline')) as synth:
            self.assertEqual(tts.get_or_create_audio('Cached dummy','en'),'audio/'+path.name)
            synth.assert_not_called()
        # This unit fixture checks control flow only; real MP3 validity is checked separately.


if __name__=='__main__':unittest.main(verbosity=2)
