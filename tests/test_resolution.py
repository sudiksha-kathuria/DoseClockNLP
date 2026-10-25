"""Multilingual content and occurrence-bound device retries. Disposable fixtures."""
import concurrent.futures
import hashlib
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import database
import tts
from app import app

EXPECTED = {
    'en': "It's time to take your {name}.",
    'hi': 'आपकी दवा {name} लेने का समय हो गया है।',
    'ta': 'உங்கள் {name} மருந்தை எடுத்துக்கொள்ள வேண்டிய நேரம் இது.',
    'te': 'మీ {name} మందు తీసుకునే సమయం అయింది.',
    'kn': 'ನಿಮ್ಮ {name} ಔಷಧಿ ತೆಗೆದುಕೊಳ್ಳುವ ಸಮಯವಾಗಿದೆ.',
    'bn': 'আপনার {name} ওষুধ খাওয়ার সময় হয়েছে।',
}

class ResolutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db, self.old_audio = database.DB_PATH, tts.AUDIO_DIR
        database.DB_PATH = str(Path(self.tmp.name)/'resolution.db')
        tts.AUDIO_DIR = str(Path(self.tmp.name)/'audio')
        database.init_db()
        self.owner = database.create_user('resolution_owner', 'dummy-password', 'Dummy')
        self.other = database.create_user('resolution_other', 'dummy-password', 'Other dummy')
        self.token = database.create_device_token(self.owner['id'], 'Dummy device')
        self.client = app.test_client()
        with self.client.session_transaction() as s: s['user_id'] = self.owner['id']

    def tearDown(self):
        database.DB_PATH, tts.AUDIO_DIR = self.old_db, self.old_audio
        self.tmp.cleanup()

    def due(self, name='Pending A', owner=None, language='en'):
        gid = database.add_medicine(owner or self.owner['id'], name, ['08:00'], 3, language)
        mid = database.get_group(gid)[0]['id']; database.mark_fired(mid, None)
        return mid

    def body(self, mid, action='taken', request_id='resolution-request-001', token=None):
        return {'token':token or self.token, 'action':action, 'id':mid,
            'fired_at':database.get_medicine(mid)['last_fired_at'], 'request_id':request_id}

    def post(self, body, client=None): return (client or self.client).post('/api/device/action', json=body)

    def receipts(self):
        with database.get_db_connection() as c: return c.execute('SELECT COUNT(*) FROM device_action_receipts').fetchone()[0]

    def parallel(self, bodies):
        barrier = threading.Barrier(len(bodies))
        def run(body):
            c = app.test_client(); barrier.wait(); r = self.post(body,c); return r.status_code, r.json
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(bodies)) as pool: return list(pool.map(run,bodies))

    def test_translated_text_preserves_opaque_unicode_name(self):
        name = 'Review {A} / 盐 नाम 10 mg'
        self.assertEqual({code for code,_ in tts.LANGUAGES},set(EXPECTED))
        for lang, template in EXPECTED.items():
            with self.subTest(language=lang): self.assertEqual(tts.build_reminder_text(name,lang),template.format(name=name))

    def test_six_synthesis_calls_use_translated_text_and_matching_language(self):
        name = 'Review dummy'
        class Speech:
            def save(self,path): Path(path).write_bytes(b'unit-provider-fixture')
        with patch('tts.gTTS',side_effect=lambda **kwargs: Speech()) as synth:
            for lang,template in EXPECTED.items():
                relative=tts.get_or_create_audio(name,lang)
                self.assertTrue((Path(tts.AUDIO_DIR)/Path(relative).name).is_file())
                self.assertEqual(synth.call_args.kwargs['text'],template.format(name=name))
                self.assertEqual(synth.call_args.kwargs['lang'],lang)
        self.assertEqual(synth.call_count,6)

    def test_legacy_english_cache_not_reused_for_translated_templates(self):
        directory=Path(tts.AUDIO_DIR);directory.mkdir();name='Review dummy'
        for lang in EXPECTED:
            legacy=f'{lang}_review-dummy_{hashlib.sha1(f"{name}|{lang}".encode()).hexdigest()[:10]}.mp3'
            (directory/legacy).write_bytes(b'old-English-content')
            with self.subTest(language=lang): self.assertIsNone(tts.get_cached_audio(name,lang))
        self.assertEqual(len(list(directory.glob('*.mp3'))),6)

    def test_six_cache_entries_are_distinct_and_reusable_offline(self):
        class Speech:
            def save(self,path): Path(path).write_bytes(b'unit-provider-fixture')
        with patch('tts.gTTS',side_effect=lambda **kw: Speech()):
            paths={lang:tts.get_or_create_audio('Review dummy',lang) for lang in EXPECTED}
        self.assertEqual(len(set(paths.values())),6)
        with patch('tts.gTTS',side_effect=ConnectionError('controlled offline')) as synth:
            for lang,path in paths.items(): self.assertEqual(tts.get_or_create_audio('Review dummy',lang),path)
            synth.assert_not_called()

    def test_synthesis_failures_cleanup_and_can_retry_all_languages(self):
        class Broken:
            def save(self,path): Path(path).write_bytes(b'partial');raise OSError('controlled provider failure')
        class Empty:
            def save(self,path): pass
        class Good:
            def save(self,path): Path(path).write_bytes(b'unit-provider-fixture')
        for lang in EXPECTED:
            for implementation in (Broken,Empty):
                with self.subTest(language=lang,implementation=implementation.__name__):
                    with patch('tts.gTTS',return_value=implementation()):
                        with self.assertRaises(OSError): tts.get_or_create_audio('Failure dummy',lang)
                    self.assertIsNone(tts.get_cached_audio('Failure dummy',lang))
            with patch('tts.gTTS',return_value=Good()): tts.get_or_create_audio('Failure dummy',lang)
        self.assertEqual(len(list(Path(tts.AUDIO_DIR).iterdir())),6)

    def test_invalid_language_rejected_before_provider_or_file_creation(self):
        with patch('tts.gTTS') as synth:
            for lang in ('zz','../en','',None):
                with self.subTest(language=lang), self.assertRaises(ValueError):tts.get_or_create_audio('Dummy',lang)
            synth.assert_not_called()
        self.assertFalse(Path(tts.AUDIO_DIR).exists())

    def test_current_due_audio_does_not_expose_legacy_english_cache(self):
        for lang in EXPECTED:
            mid=self.due(name='Opaque नाम',language=lang)
            database.mark_fired(mid,'audio/legacy-english.mp3')
            row=dict(database.get_medicine(mid))
            response=self.client.get('/check_reminders').json
            self.assertIsNone(response['audio_url'])
            with database.get_db_connection() as c:c.execute('UPDATE medicines SET is_due=0 WHERE id=?',(mid,))
            after=dict(database.get_medicine(mid))
            for field in ('medicine_name','time','language','days_remaining','created_at'):self.assertEqual(row[field],after[field])

    def test_selection_is_authenticated_and_account_scoped(self):
        self.due(owner=self.other['id'])
        self.assertEqual(self.client.post('/api/device/reminder',json={'token':'invalid'}).status_code,401)
        self.assertEqual(self.client.post('/api/device/reminder',json={'token':self.token}).json,{'due':False})
        mid=self.due();r=self.client.post('/api/device/reminder',json={'token':self.token})
        self.assertEqual(r.status_code,200);self.assertEqual(r.json['id'],mid)
        self.assertEqual(r.json['fired_at'],database.get_medicine(mid)['last_fired_at'])

    def test_legacy_idless_taken_and_snooze_requests_fail_closed(self):
        a,b=self.due(),self.due('Pending B')
        for action in ('taken','snooze'):
            self.assertEqual(self.post({'token':self.token,'action':action}).status_code,400)
        self.assertTrue(all(database.get_medicine(mid)['is_due'] for mid in (a,b)))
        self.assertEqual(len(database.get_dose_history(self.owner['id'])),0)

    def test_taken_response_loss_retry_does_not_acknowledge_second_reminder(self):
        a,b=self.due(),self.due('Pending B');body=self.body(a)
        first=self.post(body);retry=self.post(body)
        self.assertEqual([first.status_code,retry.status_code],[200,200]);self.assertEqual(first.json,retry.json)
        self.assertEqual(len(database.get_dose_history(self.owner['id'])),1)
        self.assertEqual(database.get_medicine(b)['is_due'],1);self.assertEqual(self.receipts(),1)

    def test_snooze_retry_does_not_extend_deadline_or_snooze_second_reminder(self):
        a,b=self.due(),self.due('Pending B');body=self.body(a,'snooze')
        self.assertEqual(self.post(body).status_code,200);deadline=database.get_medicine(a)['snoozed_until']
        self.assertEqual(self.post(body).status_code,200)
        self.assertEqual(database.get_medicine(a)['snoozed_until'],deadline)
        self.assertEqual(database.get_medicine(b)['is_due'],1)
        self.assertEqual(len(database.get_dose_history(self.owner['id'])),0)

    def test_same_request_concurrent_retries_have_one_durable_effect(self):
        a,b=self.due(),self.due('Pending B');body=self.body(a)
        results=self.parallel([body,body])
        self.assertEqual([r[0] for r in results],[200,200]);self.assertEqual(results[0][1],results[1][1])
        self.assertEqual(len(database.get_dose_history(self.owner['id'])),1)
        self.assertEqual(self.receipts(),1);self.assertEqual(database.get_medicine(b)['is_due'],1)

    def test_distinct_requests_for_same_occurrence_cannot_both_apply(self):
        a,b=self.due(),self.due('Pending B')
        results=self.parallel([self.body(a,request_id='distinct-request-a'),self.body(a,request_id='distinct-request-b')])
        self.assertEqual(sorted(r[0] for r in results),[200,409])
        self.assertEqual(len(database.get_dose_history(self.owner['id'])),1)
        self.assertEqual(database.get_medicine(b)['is_due'],1)

    def test_request_id_reuse_with_different_target_or_action_conflicts(self):
        a,b=self.due(),self.due('Pending B');body=self.body(a)
        self.assertEqual(self.post(body).status_code,200)
        for changed in ({'id':b,'fired_at':database.get_medicine(b)['last_fired_at']},{'action':'snooze'}):
            self.assertEqual(self.post({**body,**changed}).status_code,409)
        self.assertEqual(database.get_medicine(b)['is_due'],1);self.assertEqual(self.receipts(),1)

    def test_stale_firing_rejected_while_exact_successful_retry_replays_receipt(self):
        for action in ('taken','snooze'):
            with self.subTest(action=action):
                mid=self.due(action);old=self.body(mid,action,'stale-original-'+action)
                self.assertEqual(self.post(old).status_code,200)
                database.mark_fired(mid,None);new=database.get_medicine(mid)['last_fired_at']
                self.assertEqual(self.post(old).status_code,200)
                self.assertEqual(self.post({**old,'request_id':'unused-stale-'+action}).status_code,409)
                self.assertEqual(database.get_medicine(mid)['last_fired_at'],new)
                self.assertEqual(database.get_medicine(mid)['is_due'],1)
        self.assertEqual(len(database.get_dose_history(self.owner['id'])),1)

    def test_database_failure_rolls_back_effect_and_receipt_then_retry_succeeds(self):
        mid=self.due();body=self.body(mid)
        with patch('database._record_device_action',side_effect=sqlite3.OperationalError('controlled disk failure')):
            self.assertEqual(self.post(body).status_code,503)
        self.assertEqual(database.get_medicine(mid)['is_due'],1)
        self.assertEqual(database.get_medicine(mid)['days_remaining'],3)
        self.assertEqual(self.receipts(),0);self.assertEqual(len(database.get_dose_history(self.owner['id'])),0)
        self.assertEqual(self.post(body).status_code,200);self.assertEqual(self.receipts(),1)

    def test_wrong_owner_target_never_mutates_either_account(self):
        mid=self.due(owner=self.other['id']);self.assertEqual(self.post(self.body(mid)).status_code,404)
        self.assertEqual(database.get_medicine(mid)['is_due'],1)
        self.assertEqual(self.receipts(),0)

    def test_receipts_survive_database_restart_and_are_scoped_to_device(self):
        a,b=self.due(),self.due('Pending B');body=self.body(a)
        first=self.post(body);database.init_db();self.assertEqual(self.post(body).json,first.json)
        token=database.create_device_token(self.owner['id'],'Second dummy device')
        self.assertEqual(self.post(self.body(b,token=token)).status_code,200)
        self.assertEqual(self.receipts(),2)

    def test_archived_or_deleted_target_does_not_redirect_to_another_due_row(self):
        for operation in ('delete','edit'):
            a=self.due(operation);body=self.body(a,request_id='stale-'+operation+'-request')
            row=database.get_medicine(a)
            if operation=='delete':database.deactivate_group(row['group_id'])
            else:database.update_group(row['group_id'],'Edited',['09:00'],'en',3)
            b=self.due('Another '+operation)
            self.assertEqual(self.post(body).status_code,409)
            self.assertEqual(database.get_medicine(b)['is_due'],1)

    def test_taken_snooze_race_has_only_one_transition(self):
        a,b=self.due(),self.due('Pending B')
        results=self.parallel([self.body(a,'taken','race-taken-request'),self.body(a,'snooze','race-snooze-request')])
        self.assertEqual(sorted(r[0] for r in results),[200,409]);self.assertEqual(self.receipts(),1)
        row=database.get_medicine(a);logs=database.get_dose_history(self.owner['id'])
        self.assertEqual(len(logs),0 if row['snoozed_until'] else 1)
        self.assertEqual(database.get_medicine(b)['is_due'],1)

    def test_invalid_identity_types_and_missing_fields_are_rejected(self):
        mid=self.due();body=self.body(mid)
        for key in ('id','fired_at','request_id'):
            invalid=[None,[],{},True,'']
            if key=='id':invalid += ['1',-1,1.5,2**80]
            for value in invalid:
                with self.subTest(field=key,value=value):self.assertEqual(self.post({**body,key:value}).status_code,400)
        self.assertEqual(database.get_medicine(mid)['is_due'],1)

    def test_browser_actions_require_generation_and_reject_stale_requests(self):
        mid=self.due();fired=database.get_medicine(mid)['last_fired_at']
        for route in ('/mark_taken','/mark_snooze'):
            self.assertEqual(self.client.post(route,json={'id':mid}).status_code,400)
            self.assertEqual(self.client.post(route,json={'id':mid,'fired_at':'stale'}).status_code,409)
        self.assertEqual(database.get_medicine(mid)['is_due'],1)
        self.assertEqual(self.client.post('/mark_taken',json={'id':mid,'fired_at':fired}).status_code,200)


if __name__=='__main__':unittest.main(verbosity=2)
